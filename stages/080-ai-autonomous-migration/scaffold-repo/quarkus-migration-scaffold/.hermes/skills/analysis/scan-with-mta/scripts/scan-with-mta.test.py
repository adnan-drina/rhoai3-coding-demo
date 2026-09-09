#!/usr/bin/env python3
"""scan-with-mta selftest: receipt provenance (pinned vs kantra), --source refused, canary, frozen input intact."""
from __future__ import annotations

import hashlib
import json
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
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


def main() -> int:
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
    print("OK: scan-with-mta (kantra provisional; 8.2-line pin admits a measured 8.2 binary; 8.1/unmeasured/frozen-digest-mismatch refused; --source refused; canary missing refuses; transformed input refuses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
