#!/usr/bin/env python3
"""scan-with-mta selftest: receipt provenance (pinned vs kantra), --source refused, canary, frozen input intact."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
RECEIPT = HERE / "emit-mta-receipt.py"
CANARY = HERE / "assert-mta-canary.py"
INTACT = HERE / "assert-frozen-input-intact.py"
ANALYZE = HERE / "mta-analyze-legacy.sh"
RESCAN = HERE / "mta-rescan-destination.sh"
FLOOR = HERE / "assert-mta-rescan.py"
NORMALIZE = HERE / "normalize-findings.py"
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import specimens  # noqa: E402
from planner.canonical import load_json, product_tree_sha256  # noqa: E402
from planner.paths import LOOP_STEPS, MTA_FINDINGS, MTA_RESCAN_FINDINGS  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def _git(root: Path, *args: str, date: str = "") -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@local", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@local")
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    p = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True, env=env)
    if p.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def _floor(root: Path, *args: str) -> tuple[int, str]:
    p = _run([sys.executable, str(FLOOR), str(root), *args])
    return p.returncode, p.stdout + p.stderr


def rescan_floor() -> int:
    """WC-5 over the destination rescan record (v9 t_caf2ad51, 2026-09-22).

    The floor digested evidence/mta-findings.json -- the legacy M1 scan -- by
    default, compared it with the M1 snapshot of that same file, and refused
    every run whose rescans lived under verification/mta-rescan/. What it
    judges now is the destination rescan record: analyzer_ran, the digest of
    the tree it scanned against the tree on disk, its stamp against the last
    M3 completion (the last recorded loop commit, dated by git)."""
    m1_at = "2026-09-14T07:42:37Z"
    m3_at = "2026-09-22T07:40:00Z"
    rescan_at = "2026-09-22T07:53:57Z"
    with tempfile.TemporaryDirectory(prefix="mta-floor-") as tmp:
        root = Path(tmp).resolve() / "dest"
        (root / "src" / "main" / "java").mkdir(parents=True)
        (root / "src" / "main" / "java" / "A.java").write_text("class A {}\n", encoding="utf-8")
        (root / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "fix-until-green: t_last accepted", date=m3_at)
        sha = _git(root, "rev-parse", "HEAD")
        # the legacy M1 scan and its snapshot (what the floor used to digest)
        legacy = root / MTA_FINDINGS
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps({"schema": "rhoai3.mta-findings/v1-provisional", "normalized_at": m1_at,
                                      "execution_evidence": {"analyzer_ran": True, "cli": "/opt/mta-cli/mta-cli", "rule_set": ["quarkus"],
                                                             "input_digest": "frozen:" + "a" * 64},
                                      "violations": {}}), encoding="utf-8")
        rc, blob = _floor(root, "--snapshot-m1", "--findings", str(legacy))
        if rc != 0 or not (root / "evidence" / "derived" / "m1-findings-digest.json").is_file():
            return _fail("--snapshot-m1 must write the M1 snapshot: %s" % blob)
        # the loop record: the last step carries the commit git dates at m3_at
        steps = root / LOOP_STEPS
        steps.parent.mkdir(parents=True, exist_ok=True)
        steps.write_text(json.dumps({"schema": "rhoai3.loop-steps/v1", "attempts": {}, "rewinds": [], "rejected": [],
                                     "steps": [{"card": "", "cluster": "bootstrap", "verdict": "baseline", "commit": sha},
                                               {"card": "t_last", "cluster": "c:1", "attempt": 1, "verdict": "accepted", "commit": sha}]}),
                         encoding="utf-8")
        rescan = root / MTA_RESCAN_FINDINGS
        rescan.parent.mkdir(parents=True, exist_ok=True)

        def write_rescan(**over) -> None:
            ev = {"analyzer_ran": True, "cli": "/opt/mta-cli/mta-cli", "rule_set": ["quarkus"],
                  "input_digest": "destination:" + sha, "tree_sha256": product_tree_sha256(root), "git_head": sha}
            doc = {"schema": "rhoai3.mta-findings/v1-provisional", "normalized_at": rescan_at, "execution_evidence": ev, "violations": {}}
            for k, v in over.items():
                if k in ev:
                    ev[k] = v
                else:
                    doc[k] = v
            rescan.write_text(json.dumps(doc), encoding="utf-8")

        # (a) the v9 shape: a rescan of this tree, after the last step -> PASS
        write_rescan()
        rc, blob = _floor(root)
        if rc != 0 or "PASS" not in blob or sha[:12] not in blob or rescan_at not in blob or m3_at not in blob:
            return _fail("a rescan of this tree newer than the last M3 step must PASS naming the facts: %s" % blob)
        # (b) older than the last step -> FAIL naming both times
        write_rescan(normalized_at="2026-09-22T07:39:00Z")
        rc, blob = _floor(root)
        if rc != 1 or "2026-09-22T07:39:00Z" not in blob or m3_at not in blob or "not newer than the last M3 completion" not in blob or "t_last" not in blob:
            return _fail("a rescan older than the last M3 step must FAIL naming both times and the step: %s" % blob)
        # (c) the digest of another tree -> FAIL
        write_rescan(tree_sha256="0" * 64)
        rc, blob = _floor(root)
        if rc != 1 or "rescan is of another tree" not in blob or "000000000000" not in blob:
            return _fail("a rescan of another tree must FAIL: %s" % blob)
        # (c2) this tree edited after the rescan -> the same refusal
        write_rescan()
        (root / "src" / "main" / "java" / "B.java").write_text("class B {}\n", encoding="utf-8")
        rc, blob = _floor(root)
        if rc != 1 or "rescan is of another tree" not in blob:
            return _fail("a tree edited after the rescan must FAIL: %s" % blob)
        (root / "src" / "main" / "java" / "B.java").unlink()
        # (c3) a record that does not say which tree it scanned -> FAIL
        write_rescan(tree_sha256="")
        rc, blob = _floor(root)
        if rc != 1 or "carries no execution_evidence.tree_sha256" not in blob:
            return _fail("a rescan without a tree digest must FAIL: %s" % blob)
        # (d) no rescan record -> FAIL naming the writer
        rescan.unlink()
        rc, blob = _floor(root)
        if rc != 1 or "no destination rescan record" not in blob or "mta-rescan-destination.sh" not in blob:
            return _fail("no rescan record must FAIL naming the writer: %s" % blob)
        # (e) the legacy path given explicitly, a copy of M1 -> the WC-5 refusal
        rc, blob = _floor(root, "--findings", "evidence/mta-findings.json")
        if rc != 1 or "input_digest equals M1 snapshot" not in blob or "a copy of M1 without a new analyzer run is not a rescan (WC-5)" not in blob:
            return _fail("the legacy path must be refused as a copy of M1: %s" % blob)
        # (e2) a copy of M1 placed at the rescan path -> the same refusal
        rescan.write_bytes(legacy.read_bytes())
        rc, blob = _floor(root)
        if rc != 1 or "a copy of M1 without a new analyzer run is not a rescan (WC-5)" not in blob:
            return _fail("a copy of M1 at the rescan path must be refused: %s" % blob)
        # (f) analyzer_ran false -> FAIL
        write_rescan(analyzer_ran=False)
        rc, blob = _floor(root)
        if rc != 1 or "analyzer_ran is not true" not in blob:
            return _fail("analyzer_ran false must FAIL: %s" % blob)
        # (g) the writer records the tree: normalize-findings carries tree_sha256 + git_head when given
        raw = root / "verification" / "mta-rescan" / "raw.json"
        raw.write_text(json.dumps([{"name": "rs", "violations": {}, "unmatched": [], "skipped": [], "errors": {}}]), encoding="utf-8")
        p = _run([sys.executable, str(NORMALIZE), str(raw), "/opt/mta-cli/mta-cli", "quarkus", "destination:" + sha,
                  str(raw.with_name("raw-coverage.json")), "", "f" * 64, sha])
        doc = load_json(raw)
        if p.returncode != 0 or doc["execution_evidence"].get("tree_sha256") != "f" * 64 or doc["execution_evidence"].get("git_head") != sha:
            return _fail("normalize-findings must record tree_sha256 and git_head: %s %s" % (p.stderr, doc.get("execution_evidence")))
        sh = RESCAN.read_text(encoding="utf-8")
        if "product_tree_sha256" not in sh or '"${TREE_SHA256}" "${DEST_DIGEST}"' not in sh:
            return _fail("mta-rescan-destination.sh must record the digest of the tree it scans")
        # (h) the loop record names a commit git cannot date -> a defect, not a pass
        write_rescan()
        steps.write_text(json.dumps({"schema": "rhoai3.loop-steps/v1", "attempts": {}, "rewinds": [], "rejected": [],
                                     "steps": [{"card": "t_x", "verdict": "accepted", "commit": "0" * 40}]}), encoding="utf-8")
        rc, blob = _floor(root)
        if rc != 1 or "git cannot date" not in blob:
            return _fail("an undatable loop commit must FAIL as a defect: %s" % blob)
    return 0


def main() -> int:
    if rescan_floor() != 0:
        return 1
    sh = ANALYZE.read_text(encoding="utf-8")
    for needle in ("assert-frozen-input-intact.py", "emit-mta-receipt.py", "assert-mta-canary.py", "--rules", "analysis_copy", "NEVER pass --source"):
        if needle not in sh:
            return _fail("mta-analyze-legacy.sh must carry %r" % needle)
    if "legacy-at-3.json" in sh or "harvest_referent" in sh:
        return _fail("mta-analyze-legacy.sh must not read the derived Boot 3 manifest")
    for ln in sh.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("echo ") or "die " in s:
            continue
        if "--source" in s:
            return _fail("mta-analyze-legacy.sh must not pass --source: %r" % s)
    if "mta-cli" not in sh.split("ensure_cli()")[1].split("_try_resolved_clis")[0]:
        return _fail("ensure_cli must probe the pinned MTA CLI first")
    if "--root" not in sh:
        return _fail("mta-analyze-legacy.sh must honor --root so isolated rehearsal does not write dest evidence")
    if not RESCAN.is_file():
        return _fail("missing mta-rescan-destination.sh")

    with tempfile.TemporaryDirectory(prefix="mta-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "dest", specimens.specimen("http"), decisions=specimens.full_decisions())
        kantra = t / "kantra" / "kantra"
        kantra.parent.mkdir()
        kantra.write_bytes(b"#!/bin/sh\necho kantra\n")
        (t / "kantra" / "java-external-provider").write_bytes(b"\x7fELF")
        argv_file = t / "argv.txt"
        argv_file.write_text("\n".join([str(kantra), "analyze", "--input", "/analysis", "--target", "quarkus", "--rules", "x"]), encoding="utf-8")
        findings = root / "evidence" / "mta-findings.json"
        p = _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--targets", "quarkus,jakarta-ee9", "--rules-dir", str(root / ".hermes" / "planning" / "mta-rules"), "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file)])
        if p.returncode != 0:
            return _fail("kantra receipt: %s%s" % (p.stdout, p.stderr))
        rec = load_json(root / "evidence" / "producers" / "mta.json")
        if rec["tool"]["admissible"] is not False or rec["tool"]["provenance"] != "kantra-fallback" or not rec["reasons"]:
            return _fail("kantra must be provisional: %s" % rec["tool"])
        if rec["canary"]["fired"] is not True or rec["custom_rules_count"] < 1 or not rec["tool"]["provider_artifacts"]:
            return _fail("receipt provenance fields: %s" % {k: rec[k] for k in ("canary", "custom_rules_count")})
        if rec["input"]["digest"] != load_json(root / "evidence" / "producers" / "freeze.json")["source_digest"]:
            return _fail("input digest must be the frozen source digest")
        # canary check passes on this receipt
        if _run([sys.executable, str(CANARY), str(root)]).returncode != 0:
            return _fail("canary must pass when fired")
        # MTA 8.x files the zero-effort canary under insights (measured live 2026-09-09: 176 incidents, no violation)
        doc = load_json(findings)
        canary_rule = doc["violations"].pop("rhoai3-canary-00001")
        doc["insights"] = {"rhoai3-canary-00001": canary_rule}
        findings.write_text(json.dumps(doc), encoding="utf-8")
        _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--targets", "quarkus", "--rules-dir", str(root / ".hermes" / "planning" / "mta-rules"), "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file)])
        if load_json(root / "evidence" / "producers" / "mta.json")["canary"]["fired"] is not True or _run([sys.executable, str(CANARY), str(root)]).returncode != 0:
            return _fail("a canary filed under insights must count as fired")
        sys.path.insert(0, str(root / ".hermes" / "lib"))
        from planner.evidence import derive_obligations  # noqa: E402
        obligations, fired, _raw = derive_obligations(doc, {}, "rhoai3-canary-00001")
        if not fired or any(o.get("rule_id") == "rhoai3-canary-00001" for o in obligations):
            return _fail("insight canary: fired=%s, must never be an obligation" % fired)
        doc["violations"]["rhoai3-canary-00001"] = doc["insights"].pop("rhoai3-canary-00001")
        findings.write_text(json.dumps(doc), encoding="utf-8")
        # a real mta-cli binary on the pinned 8.2 line → admissible; measured sha recorded
        mta = t / "mta" / "mta-cli"
        mta.parent.mkdir()
        mta.write_bytes(b"#!/bin/sh\necho mta-cli 8.2.1\n")
        (t / "mta" / "java-external-provider").write_bytes(b"\x7fELF")
        argv_file.write_text("\n".join([str(mta), "analyze", "--input", "/analysis", "--target", "quarkus", "--rules", "x"]), encoding="utf-8")
        common = [sys.executable, str(RECEIPT), str(root), "--cli", str(mta), "--input", "/analysis", "--targets", "quarkus", "--rules-dir", str(root / ".hermes" / "planning" / "mta-rules"), "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file)]
        golden_pin = load_json(GOLDEN / ".hermes" / "pins.json")["pins"]["mta_cli"]
        if golden_pin.get("version") != "8.2":
            return _fail("golden pins.mta_cli must pin the 8.2 line: %s" % golden_pin)
        frozen = golden_pin.get("artifact_sha256")
        if frozen is not None and not (isinstance(frozen, str) and len(frozen) == 64 and all(c in "0123456789abcdef" for c in frozen) and str(golden_pin.get("artifact") or "").strip()):
            return _fail("a frozen golden artifact_sha256 must be a real sha256 with its artifact provenance named (never fabricated): %s" % golden_pin)
        # the fake 8.2 binary below cannot match a frozen digest: test the line rule on an unfrozen copy
        golden_pin = dict(golden_pin, artifact_sha256=None)
        pins = load_json(root / ".hermes" / "pins.json")
        pins["pins"]["mta_cli"] = dict(golden_pin)
        (root / ".hermes" / "pins.json").write_text(json.dumps(pins, indent=2), encoding="utf-8")
        sha = hashlib.sha256(mta.read_bytes()).hexdigest()
        p = _run(common + ["--cli-version", "mta-cli 8.2.1"])
        rec = load_json(root / "evidence" / "producers" / "mta.json")
        if p.returncode != 0 or rec["tool"]["admissible"] is not True or rec["tool"]["provenance"] != "mta-cli-8.2-artifact" or rec["tool"]["version"] != "8.2" or rec["tool"]["artifact_sha256"] != sha or rec["tool"]["version_measured"] != "mta-cli 8.2.1":
            return _fail("8.2-line binary under the 8.2 pin must be admissible with measured provenance: %s" % rec["tool"])
        # version outside the pinned line → non-admissible
        _run(common + ["--cli-version", "mta-cli 8.1.0"])
        rec = load_json(root / "evidence" / "producers" / "mta.json")
        if rec["tool"]["admissible"] is not False or not any("outside the pinned line" in r for r in rec["reasons"]):
            return _fail("8.1 binary under the 8.2 pin must be refused: %s" % rec["reasons"])
        # unmeasurable version → non-admissible
        _run(common)
        if load_json(root / "evidence" / "producers" / "mta.json")["tool"]["admissible"] is not False:
            return _fail("unmeasured version must be refused")
        # frozen digest: match admits, mismatch refuses
        pins["pins"]["mta_cli"]["artifact_sha256"] = sha
        (root / ".hermes" / "pins.json").write_text(json.dumps(pins, indent=2), encoding="utf-8")
        _run(common + ["--cli-version", "mta-cli 8.2.1"])
        if load_json(root / "evidence" / "producers" / "mta.json")["tool"]["admissible"] is not True:
            return _fail("frozen digest match must be admissible")
        pins["pins"]["mta_cli"]["artifact_sha256"] = "0" * 64
        (root / ".hermes" / "pins.json").write_text(json.dumps(pins, indent=2), encoding="utf-8")
        _run(common + ["--cli-version", "mta-cli 8.2.1"])
        rec = load_json(root / "evidence" / "producers" / "mta.json")
        if rec["tool"]["admissible"] is not False or not any("frozen artifact_sha256" in r for r in rec["reasons"]):
            return _fail("frozen digest mismatch must be refused: %s" % rec["reasons"])
        # kantra under the 8.2 pin stays provisional even when it claims 8.2
        pins["pins"]["mta_cli"] = dict(golden_pin)
        (root / ".hermes" / "pins.json").write_text(json.dumps(pins, indent=2), encoding="utf-8")
        argv_file.write_text("\n".join([str(kantra), "analyze", "--input", "/analysis", "--target", "quarkus", "--rules", "x"]), encoding="utf-8")
        _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--targets", "quarkus", "--rules-dir", str(root / ".hermes" / "planning" / "mta-rules"), "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file), "--cli-version", "kantra 8.2.0"])
        rec = load_json(root / "evidence" / "producers" / "mta.json")
        if rec["tool"]["admissible"] is not False or rec["tool"]["provenance"] != "kantra-fallback":
            return _fail("kantra must stay provisional under the 8.2 pin: %s" % rec["tool"])
        p = _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--targets", "quarkus", "--rules-dir", str(root / ".hermes" / "planning" / "mta-rules"), "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file)])
        # --source refused
        argv_file.write_text("\n".join([str(kantra), "analyze", "--source", "springboot"]), encoding="utf-8")
        p = _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--argv-file", str(argv_file)])
        if p.returncode != 1 or "MTA_SOURCE_FLAG" not in p.stderr:
            return _fail("--source must be refused: %s" % p.stderr)
        # canary missing
        doc = load_json(findings)
        doc["violations"].pop("rhoai3-canary-00001")
        findings.write_text(json.dumps(doc), encoding="utf-8")
        argv_file.write_text(str(kantra), encoding="utf-8")
        _run([sys.executable, str(RECEIPT), str(root), "--cli", str(kantra), "--input", "/analysis", "--canary-id", "rhoai3-canary-00001", "--findings", str(findings), "--argv-file", str(argv_file)])
        p = _run([sys.executable, str(CANARY), str(root)])
        if p.returncode != 1 or "CANARY_MISSING" not in p.stderr:
            return _fail("removed canary must refuse: %s" % p.stderr)
        # frozen input intact: real freeze + copy
        legacy = t / "legacy"
        (legacy / "src" / "main" / "java").mkdir(parents=True)
        (legacy / "src" / "main" / "java" / "A.java").write_text("class A {}\n", encoding="utf-8")
        (legacy / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        dest2 = t / "dest2"
        dest2.mkdir()
        freeze = GOLDEN / ".hermes" / "skills" / "analysis" / "freeze-migration-input" / "scripts" / "freeze-migration-input.py"
        copy = dest2 / ".derived" / "frozen-input"
        if _run([sys.executable, str(freeze), "--source", str(legacy), "--root", str(dest2), "--copy-to", str(copy)]).returncode != 0:
            return _fail("freeze for intact test")
        if _run([sys.executable, str(INTACT), str(dest2)]).returncode != 0:
            return _fail("intact copy must pass")
        (copy / "src" / "main" / "java" / "A.java").write_text("class A { int x; }\n", encoding="utf-8")
        p = _run([sys.executable, str(INTACT), str(dest2)])
        if p.returncode != 1 or "FROZEN_INPUT" not in p.stderr:
            return _fail("transformed copy must refuse before analysis: %s" % p.stderr)
    print("OK: scan-with-mta (rescan floor judges verification/mta-rescan/findings.json: tree digest + stamp after the last M3 commit, a copy of M1 refused; kantra provisional; 8.2-line pin admits a measured 8.2 binary; 8.1/unmeasured/frozen-digest-mismatch refused; --source refused; canary missing refuses; transformed input refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
