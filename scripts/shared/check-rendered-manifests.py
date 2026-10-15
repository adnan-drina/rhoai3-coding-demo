#!/usr/bin/env python3
"""Offline GitOps checks a plain render does not catch.

1. Duplicate mapping keys in any YAML under gitops/stages: Kustomize keeps the last one, so an earlier block
   (for example a second `labels:` in a kustomization) disappears without an error.
2. Retention through transformation: every argocd.argoproj.io/sync-options value a source object declares must
   survive in that object's render (a kustomization commonAnnotations writer replaces it, dropping Delete=false).

Usage: check-rendered-manifests.py [repo-root]   Exit 1 on any finding."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage_apps import load_yaml_stream  # noqa: E402  (Ruby's YAML, as the stage helper uses; no PyYAML needed)

SYNC = "argocd.argoproj.io/sync-options"

# Walks Psych's parse tree: a mapping whose keys repeat is reported with the key and line.
DUPLICATES_RB = r"""
require "psych"
def walk(node, out)
  if node.is_a?(Psych::Nodes::Mapping)
    seen = {}
    node.children.each_slice(2) do |k, _|
      next unless k.is_a?(Psych::Nodes::Scalar)
      out << "duplicate key #{k.value.inspect} at line #{k.start_line + 1}" if seen[k.value]
      seen[k.value] = true
    end
  end
  (node.children || []).each { |c| walk(c, out) }
end
ARGV.each do |f|
  begin
    out = []
    walk(Psych.parse_stream(File.read(f)), out)
    out.each { |m| puts "#{f}: #{m}" }
  rescue Psych::SyntaxError
  end
end
"""


def duplicate_keys(root):
    files = [str(f) for f in sorted((root / "gitops/stages").rglob("*.yaml"))
             if "{{" not in f.read_text() and "{%" not in f.read_text()]  # scaffolder skeletons are templates
    r = subprocess.run(["ruby", "-e", DUPLICATES_RB] + files, capture_output=True, text=True, timeout=300)
    if r.returncode:
        return ["duplicate-key scan failed: " + r.stderr.strip()[:200]]
    return [line.replace(str(root) + "/", "") for line in r.stdout.splitlines()]


def dropped_sync_options(root):
    findings = []
    for k in sorted(root.glob("gitops/stages/*/*/kustomization.yaml")):
        comp = k.parent
        r = subprocess.run(["oc", "kustomize", str(comp)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            findings.append("%s: render failed" % comp.relative_to(root))
            continue
        rendered = {}
        for d in load_yaml_stream(r.stdout):
            if d:
                m = d["metadata"]
                rendered.setdefault((d["kind"], m["name"]), []).append((m.get("namespace"), (m.get("annotations") or {}).get(SYNC, "")))
        for f in comp.rglob("*.yaml"):
            text = f.read_text()
            if SYNC not in text or "{{" in text or "{%" in text:
                continue
            try:
                docs = load_yaml_stream(text)
            except Exception:  # syntax errors surface in the render
                continue
            for d in docs:
                if not isinstance(d, dict) or not isinstance(d.get("metadata"), dict) or "kind" not in d:
                    continue
                want = (d["metadata"].get("annotations") or {}).get(SYNC)
                if not want:
                    continue
                for ns, got in rendered.get((d["kind"], d["metadata"].get("name")), []):
                    if d["metadata"].get("namespace") in (None, ns):
                        missing = set(want.split(",")) - set(got.split(","))
                        if missing:
                            findings.append("%s: %s/%s loses %s in the render (rendered %r)" % (
                                comp.relative_to(root), d["kind"], d["metadata"]["name"], ",".join(sorted(missing)), got))
    return findings


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2])
    findings = duplicate_keys(root) + dropped_sync_options(root)
    for f in findings:
        print("FAIL " + f)
    print("PASS no duplicate YAML keys; every declared sync option survives its render" if not findings else
          "FAIL %d rendered-manifest finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
