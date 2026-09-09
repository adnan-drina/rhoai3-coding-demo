#!/usr/bin/env python3
"""Write evidence/producers/mta.json — full provenance of one MTA CLI run.

Records: exact binary (path, realpath, sha256, size), install-prefix
provider/analyzer artifacts (path + sha256), product pin from
.hermes/pins.json, arguments and mode, targets, bundled and custom
ruleset digests, input digest, exit status, output digest, canary result,
and whether the run is ADMISSIBLE (pinned MTA CLI 8.2 artifact) or a
provisional kantra fallback.

Admissibility rule (SAD §2, §5.1): .hermes/pins.json `mta_cli` pins the
product line (`version`, e.g. "8.2"). Admissible iff that pin exists, the
executed binary is not a kantra alias, its measured `--version` starts
with the pinned line, and — when the pin also carries `artifact_sha256`
(frozen by an Operator from a measured receipt) — the binary's sha256
equals it. The measured sha256 is always recorded as provenance. A kantra
alias, an unpinned binary, a version outside the pinned line, or a digest
mismatch is provisional and non-admissible.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path


def _ensure_hermes_lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("FAIL: .hermes/lib marker missing")


_ensure_hermes_lib()
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import producer_receipt  # noqa: E402
from planner.pins import load_pins, pin  # noqa: E402

PROVIDER_GLOBS = ("*provider*", "*analyzer*", "jdtls/**/plugins/*.jar", "rulesets/**/*.yaml", "rulesets/**/*.yml")


def _tree_digest(root: Path, patterns: tuple[str, ...] = ("*.yaml", "*.yml")) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    if not root or not root.is_dir():
        return "", 0
    files: list[Path] = []
    for pat in patterns:
        files.extend(p for p in root.rglob(pat) if p.is_file())
    for p in sorted(set(files)):
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        n += 1
    return (h.hexdigest() if n else ""), n


def _provider_artifacts(prefix: Path) -> list[dict]:
    out: list[dict] = []
    if not prefix.is_dir():
        return out
    seen: set[Path] = set()
    for pat in PROVIDER_GLOBS:
        for p in sorted(prefix.glob(pat)):
            if not p.is_file() or p in seen or p.suffix in (".yaml", ".yml"):
                continue
            seen.add(p)
            out.append({"path": str(p.relative_to(prefix)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
            if len(out) >= 64:
                return out
    return out


def _canary_fired(findings_path: Path, canary_id: str) -> bool | None:
    if not canary_id or not findings_path.is_file():
        return None
    doc = load_json(findings_path)
    if not isinstance(doc, dict):
        return False
    # MTA 8.x files a zero-effort rule under insights; older exports under violations
    for key in ("violations", "insights"):
        section = doc.get(key)
        v = section.get(canary_id) if isinstance(section, dict) else None
        if isinstance(v, dict) and v.get("incidents"):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root")
    ap.add_argument("--cli", required=True)
    ap.add_argument("--status", default="ok", choices=["ok", "failed"])
    ap.add_argument("--exit-status", type=int, default=0)
    ap.add_argument("--targets", default="")
    ap.add_argument("--rules-dir", default="")
    ap.add_argument("--canary-id", default="")
    ap.add_argument("--input", required=True)
    ap.add_argument("--findings", default="")
    ap.add_argument("--argv-file", default="")
    ap.add_argument("--mode", default="containerless")
    ap.add_argument("--cli-version", default="", help="measured `<cli> --version` first line")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    freeze = load_json(producer_receipt(root, "freeze")) if producer_receipt(root, "freeze").is_file() else {}
    source_digest = str(freeze.get("source_digest") or "")
    cli = Path(args.cli)
    real = Path(os.path.realpath(cli)) if cli.exists() else cli
    bin_sha = sha256_file(real) if real.is_file() else ""
    prefix = real.parent
    pins = load_pins(root)
    mta_pin = pin(pins, "mta_cli")
    pinned_sha = str(mta_pin.get("artifact_sha256") or "")
    pinned_line = str(mta_pin.get("version") or "")
    pin_status = "pinned" if pinned_line and str(mta_pin.get("status") or "").lower() != "unpinned" else "unpinned"
    product_pin = str(mta_pin.get("product_version") or pinned_line or "8.2")
    measured = str(args.cli_version or "").strip()
    measured_num = re.search(r"\d+(?:\.\d+)+", measured)
    measured_num = measured_num.group(0) if measured_num else ""
    is_kantra = real.name.startswith("kantra") or "kantra" in str(prefix) or measured.lower().startswith("kantra")
    reasons: list[str] = []
    if pin_status != "pinned":
        reasons.append("mta_cli is unpinned in .hermes/pins.json; provisional, non-admissible")
    if is_kantra:
        reasons.append("executed binary is a kantra alias (%s); provisional, non-admissible" % real.name)
    if not measured_num:
        reasons.append("binary version could not be measured (--cli-version empty); provisional, non-admissible")
    elif pinned_line and not (measured_num == pinned_line or measured_num.startswith(pinned_line + ".")):
        reasons.append("measured version %s is outside the pinned line %s; provisional, non-admissible" % (measured_num, pinned_line))
    if pinned_sha and bin_sha != pinned_sha:
        reasons.append("binary sha256 %s does not match the frozen artifact_sha256 %s; provisional, non-admissible" % (bin_sha[:12] or "none", pinned_sha[:12]))
    if not bin_sha:
        reasons.append("binary sha256 could not be measured")
    admissible = not reasons
    provenance = "mta-cli-%s-artifact" % product_pin if admissible else ("kantra-fallback" if is_kantra else "unpinned-binary" if pin_status != "pinned" else "non-admissible-binary")
    bundled_root = prefix / "rulesets"
    bundled_digest, bundled_count = _tree_digest(bundled_root)
    custom_digest, custom_count = _tree_digest(Path(args.rules_dir)) if args.rules_dir else ("", 0)
    argv_list = Path(args.argv_file).read_text(encoding="utf-8").splitlines() if args.argv_file and Path(args.argv_file).is_file() else []
    if any(a == "--source" for a in argv_list):
        print("FAIL: MTA_SOURCE_FLAG argv contains --source (AD-003 amendment A)", file=sys.stderr)
        return 1
    findings = Path(args.findings) if args.findings else None
    canary = _canary_fired(findings, args.canary_id) if findings else None
    receipt = {
        "schema": "rhoai3.producer-receipt/v1",
        "producer": "mta",
        "status": args.status,
        "tool": {
            "name": "mta-cli",
            "version": pinned_line if admissible else None,
            "version_measured": measured,
            "pin_status": pin_status,
            "artifact_sha256": bin_sha or None,
            "product_version_pin": product_pin,
            "binary_path": str(cli),
            "binary_realpath": str(real),
            "binary_bytes": real.stat().st_size if real.is_file() else 0,
            "install_prefix": str(prefix),
            "provider_artifacts": _provider_artifacts(prefix),
            "admissible": admissible,
            "provenance": provenance,
        },
        "inputs": {"analysis_root": str(Path(args.input).resolve()), "digest": source_digest, "source_digest": source_digest},
        "input": {"analysis_root": str(Path(args.input).resolve()), "digest": source_digest},
        "outputs": [{"path": str(findings.relative_to(root)) if findings and findings.is_file() and findings.is_relative_to(root) else str(findings or ""), "sha256": sha256_file(findings) if findings and findings.is_file() else ""}] if findings else [],
        "reasons": reasons,
        "mode": args.mode,
        "argv": argv_list,
        "targets": sorted({t for t in args.targets.split(",") if t}),
        "custom_rules_dir": args.rules_dir,
        "custom_rules_digest": custom_digest,
        "custom_rules_count": custom_count,
        "bundled_rules_digest": bundled_digest,
        "bundled_rules_count": bundled_count,
        "exit_status": args.exit_status,
        "output_digest": sha256_file(findings) if findings and findings.is_file() else "",
        "canary": {"rule_id": args.canary_id, "fired": canary},
    }
    write_canonical(producer_receipt(root, "mta"), receipt)
    print("OK: mta receipt status=%s provenance=%s admissible=%s canary=%s" % (args.status, provenance, admissible, canary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
