#!/usr/bin/env python3
"""Qualify the source captures against each scenario's own contract (a gate).

``CAPTURED`` records an HTTP observation, including an unexpected one: a
create the source answered 500 for is captured just as faithfully as one it
answered 201 for, and replaying either against the destination compares
nothing about what the scenario was for. The five-scenario review
(2026-09-14) listed what a capture has to SHOW before it may count as
coverage -- the 201 with an absolute Location under the source's base, the
created owner present in the list afterwards and absent before, the 400
whose errors header names the rejected field with the list unchanged -- and
put a person in charge of checking it. That is a sign-off, and the project
rule is a gate with an audit trail instead.

So each derived scenario carries a ``qualify`` block naming those
observations, and this producer checks every capture against it, reading the
retained bodies by digest. Nothing here decides what the source SHOULD have
answered: the contract is the scenario's, the answer is the capture's, and a
capture that cannot be checked (no capture, no retained body, a digest that
does not match, a truncated list) is INCONCLUSIVE, never a pass. The parity
receipt treats anything but PASS here as "capture not qualified".

Writes verification/source-oracles/scenarios/_qualification.json. Exit 0 only
when every scenario the corpus lists is PASS; 1 otherwise; 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib, normalize_body, origin_of  # noqa: E402
from _scenarios import CorpusError, QUALIFICATION, QUALIFICATION_SCHEMA, SCENARIO_ORACLES, corpus_digest, load_corpus, scenario_slug  # noqa: E402

ensure_hermes_lib()
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

PRODUCER = "qualify-source-captures.py"
KNOWN_CHECKS = ("expect_status", "location", "after_contains_body", "before_lacks_body", "after_adds_one_body", "after_equals_before",
                "errors_header_names_field", "after_effect_status", "cors_allow_origin", "cors_expose_headers",
                "cors_allow_method", "cors_allow_headers")


class Inconclusive(Exception):
    """Evidence that cannot be checked; the reason is the message."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _header(headers: Any, name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    for k, v in headers.items():
        if str(k).lower() == name.lower():
            return None if v is None else str(v)
    return None


def _tokens(value: str | None) -> set[str]:
    return {t.strip().lower() for t in str(value or "").split(",") if t.strip()}


def _body_path(root: Path, scenario_id: str, recorded: str) -> Path | None:
    p = Path(recorded)
    if p.is_file():
        return p
    if (root / recorded).is_file():
        return root / recorded
    alt = root / SCENARIO_ORACLES / "bodies" / scenario_slug(scenario_id) / p.name
    return alt if alt.is_file() else None


def retained_body(root: Path, scenario_id: str, row: dict[str, Any], what: str) -> bytes:
    """The retained bytes of a capture row, verified against the digests the
    capture recorded: the file digest (retained_sha256), the complete-body
    digest when the body is complete (raw_body_sha256) and the row's parity
    digest (body_sha256, canonical JSON for JSON) recomputed from the bytes.
    Anything that does not add up is INCONCLUSIVE, not a body."""
    ev = row.get("evidence") if isinstance(row, dict) else None
    if not isinstance(ev, dict) or not ev.get("body_file"):
        raise Inconclusive("%s has no retained body (a capture that predates retention cannot be qualified)" % what)
    p = _body_path(root, scenario_id, str(ev["body_file"]))
    if p is None:
        raise Inconclusive("%s retained body %s is absent" % (what, ev["body_file"]))
    if not ev.get("retained_sha256") or not ev.get("raw_body_sha256"):
        # a retained file nobody bound by digest is bytes of unknown origin
        raise Inconclusive("%s retained body not digest-bound (no retained_sha256/raw_body_sha256 on the evidence row)" % what)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != ev["retained_sha256"]:
        raise Inconclusive("%s retained body digest %s is not the recorded %s" % (what, sha[:12], str(ev["retained_sha256"])[:12]))
    if ev.get("truncated"):
        raise Inconclusive("%s retained body is truncated (%s of %s bytes); a partial list proves neither presence nor absence"
                           % (what, ev.get("retained_bytes"), ev.get("body_bytes")))
    if sha != ev["raw_body_sha256"]:
        raise Inconclusive("%s retained body is not the complete response (digest %s vs raw %s)" % (what, sha[:12], str(ev["raw_body_sha256"])[:12]))
    want = str(row.get("body_sha256") or ev.get("body_sha256") or "")
    if want and normalize_body(raw, "")[1] != want:
        raise Inconclusive("%s retained body does not normalize to the recorded body_sha256 %s" % (what, want[:12]))
    return raw


def _objects(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            out.extend(_objects(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_objects(v))
    return out


def _count(raw: bytes, body: dict[str, Any], what: str) -> int:
    """How many objects in a retained JSON body carry every key/value of the
    request body (compared as JSON values, at any depth)."""
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Inconclusive("%s retained body is not JSON" % what)
    return sum(1 for obj in _objects(parsed) if all(k in obj and obj[k] == v for k, v in body.items()))


def _contains(raw: bytes, body: dict[str, Any], what: str) -> bool:
    return _count(raw, body, what) > 0


def _request_body(root: Path, sc: dict[str, Any]) -> dict[str, Any]:
    if not sc.get("body_file"):
        raise Inconclusive("the scenario sends no body, so nothing can be looked for in the read-back")
    p = root / str(sc["body_file"])
    if not p.is_file():
        raise Inconclusive("body_file %s is absent" % sc["body_file"])
    body = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise Inconclusive("body_file %s is not a JSON object" % sc["body_file"])
    return body


def _rows(cap: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {str(r.get("id")): r for r in (cap.get(key) or []) if isinstance(r, dict)}


def qualify_scenario(root: Path, sc: dict[str, Any], cap: dict[str, Any] | None, corpus_sha: str) -> dict[str, Any]:
    sid = str(sc["id"])
    q = sc.get("qualify")
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool | None, detail: str) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    if not isinstance(q, dict) or not q:
        return {"verdict": "INCONCLUSIVE", "reason": "no qualification contract (the scenario carries no qualify block)", "checks": []}
    if cap is None:
        return {"verdict": "INCONCLUSIVE", "reason": "no capture", "checks": []}
    if str(cap.get("status")) != "CAPTURED":
        return {"verdict": "INCONCLUSIVE", "reason": "capture status %s: %s" % (cap.get("status"), cap.get("reason") or ""), "checks": []}
    if str(cap.get("corpus_sha256") or "") != corpus_sha:
        return {"verdict": "INCONCLUSIVE", "reason": "capture bound to corpus %s, this is %s" % (str(cap.get("corpus_sha256"))[:12], corpus_sha[:12]), "checks": []}
    resp = cap.get("response") or {}
    headers = resp.get("headers")
    req_headers = (cap.get("request") or {}).get("headers") or sc.get("headers") or {}
    before, after = _rows(cap, "before"), _rows(cap, "effects")
    for name, want in q.items():
        try:
            if name == "expect_status":
                allowed = [int(x) for x in (want if isinstance(want, list) else [want])]
                record(name, int(resp.get("status") or 0) in allowed, "status %s, expected one of %s" % (resp.get("status"), allowed))
            elif name == "location":
                if want != "absolute-under-base":
                    raise Inconclusive("unknown location rule %r" % want)
                if not isinstance(headers, dict):
                    raise Inconclusive("the capture recorded no header map")
                loc = _header(headers, "Location")
                base = str((cap.get("source") or {}).get("base_url") or "")
                base_origin = origin_of(base)
                base_path = urllib.parse.urlsplit(base).path.rstrip("/")
                if not base_origin:
                    raise Inconclusive("the capture records no source.base_url to judge Location against")
                parts = urllib.parse.urlsplit(loc or "")
                absolute = bool(parts.scheme and parts.netloc)
                ok = absolute and origin_of(loc or "") == base_origin and (parts.path == base_path or parts.path.startswith(base_path + "/") if base_path else True)
                record(name, ok, "Location %r%s; base %s" % (loc, "" if absolute else " is not absolute", base))
            elif name == "after_contains_body":
                body = _request_body(root, sc)
                if not after:
                    raise Inconclusive("the capture recorded no after-effects")
                missing = [eid for eid, row in sorted(after.items()) if not _contains(retained_body(root, sid, row, "after %s" % eid), body, "after %s" % eid)]
                record(name, not missing, "the request body %s %s" % ("is absent from" if missing else "is present in", ", ".join(missing) or ", ".join(sorted(after))))
            elif name == "before_lacks_body":
                body = _request_body(root, sc)
                if not before:
                    raise Inconclusive("the capture recorded no before read-backs")
                present = [eid for eid, row in sorted(before.items()) if _contains(retained_body(root, sid, row, "before %s" % eid), body, "before %s" % eid)]
                record(name, not present, "the request body %s before the request (%s)" % ("was already present" if present else "was absent", ", ".join(present) or ", ".join(sorted(before))))
            elif name == "after_adds_one_body":
                # the read-back afterwards holds exactly one more object matching
                # the body than before: a document's example is often a seeded
                # row verbatim, so absence before is not something a derived
                # create can promise, while "one more" always is
                body = _request_body(root, sc)
                if not before or not after or set(before) != set(after):
                    raise Inconclusive("before and after read-backs do not pair up")
                counts = {}
                for eid in sorted(before):
                    nb = _count(retained_body(root, sid, before[eid], "before %s" % eid), body, "before %s" % eid)
                    na = _count(retained_body(root, sid, after[eid], "after %s" % eid), body, "after %s" % eid)
                    counts[eid] = (nb, na)
                bad = ["%s: %d matching before, %d after" % (eid, nb, na) for eid, (nb, na) in counts.items() if na != nb + 1]
                record(name, not bad, "; ".join(bad) or "; ".join("%s: %d matching before, %d after" % (eid, nb, na) for eid, (nb, na) in counts.items()))
            elif name == "after_equals_before":
                if not before or not after or set(before) != set(after):
                    raise Inconclusive("before and after read-backs do not pair up")
                diff = [eid for eid in sorted(before) if before[eid].get("body_sha256") != after[eid].get("body_sha256") or before[eid].get("status") != after[eid].get("status")]
                record(name, not diff, "read-backs %s" % ("changed: " + ", ".join(diff) if diff else "unchanged: " + ", ".join(sorted(before))))
            elif name == "errors_header_names_field":
                if not isinstance(headers, dict):
                    raise Inconclusive("the capture recorded no header map")
                val = _header(headers, "errors")
                record(name, bool(val) and str(want) in str(val), "errors header %s" % (repr(val)[:160] if val else "absent"))
            elif name == "after_effect_status":
                if not isinstance(want, dict):
                    raise Inconclusive("after_effect_status must map effect id to status")
                bad = []
                for eid, status in sorted(want.items()):
                    row = after.get(str(eid))
                    if row is None:
                        raise Inconclusive("effect %s was not captured" % eid)
                    if int(row.get("status") or 0) != int(status):
                        bad.append("%s answered %s, expected %s" % (eid, row.get("status"), status))
                record(name, not bad, "; ".join(bad) or "effects answered as the contract names")
            elif name == "cors_allow_origin":
                if not isinstance(headers, dict):
                    raise Inconclusive("the capture recorded no header map")
                sent = _header(req_headers, "Origin")
                got = _header(headers, "Access-Control-Allow-Origin")
                record(name, bool(sent) and got in (sent, "*"), "Access-Control-Allow-Origin %r for Origin %r" % (got, sent))
            elif name in ("cors_expose_headers", "cors_allow_headers"):
                if not isinstance(headers, dict):
                    raise Inconclusive("the capture recorded no header map")
                hdr = "Access-Control-Expose-Headers" if name == "cors_expose_headers" else "Access-Control-Allow-Headers"
                got = _tokens(_header(headers, hdr))
                need = {str(x).strip().lower() for x in (want or [])}
                record(name, need <= got, "%s %r covers %s" % (hdr, _header(headers, hdr), sorted(need)) if need <= got else "%s %r lacks %s" % (hdr, _header(headers, hdr), sorted(need - got)))
            elif name == "cors_allow_method":
                if not isinstance(headers, dict):
                    raise Inconclusive("the capture recorded no header map")
                got = _tokens(_header(headers, "Access-Control-Allow-Methods"))
                record(name, str(want).lower() in got, "Access-Control-Allow-Methods %r, need %s" % (_header(headers, "Access-Control-Allow-Methods"), want))
            else:
                raise Inconclusive("unknown qualification check %r" % name)
        except Inconclusive as exc:
            record(name, None, str(exc))
    if any(c["ok"] is False for c in checks):
        verdict = "FAIL"
    elif any(c["ok"] is None for c in checks):
        verdict = "INCONCLUSIVE"
    else:
        verdict = "PASS"
    reason = "; ".join("%s: %s" % (c["check"], c["detail"]) for c in checks if c["ok"] is not True)[:400]
    return {"verdict": verdict, "reason": reason, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        corpus = load_corpus(root)
    except CorpusError as exc:
        print("REFUSE: QUALIFY_CAPTURES %s" % exc, file=sys.stderr)
        return 1
    corpus_sha = corpus_digest(corpus)
    bundle_p = root / EVIDENCE_BUNDLE
    bundle_sha = digest(load_json(bundle_p)) if bundle_p.is_file() else ""
    results: dict[str, dict[str, Any]] = {}
    for sc in corpus.get("scenarios") or []:
        sid = str(sc["id"])
        cp = root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json")
        cap = None
        if cp.is_file():
            try:
                cap = load_json(cp)
            except (OSError, ValueError) as exc:
                results[sid] = {"verdict": "INCONCLUSIVE", "reason": "capture unreadable: %s" % exc, "checks": []}
                continue
        results[sid] = qualify_scenario(root, sc, cap, corpus_sha)
    not_passed = sorted(sid for sid, r in results.items() if r["verdict"] != "PASS")
    verdict = "PASS" if results and not not_passed else "FAIL" if any(r["verdict"] == "FAIL" for r in results.values()) else "INCONCLUSIVE"
    out = root / QUALIFICATION
    write_canonical(out, {
        "schema": QUALIFICATION_SCHEMA, "producer": PRODUCER, "at": _now(),
        "corpus_sha256": corpus_sha, "evidence_bundle_sha256": bundle_sha,
        "scenarios": dict(sorted(results.items())), "total": len(results), "not_passed": len(not_passed), "verdict": verdict,
    })
    for sid in not_passed:
        print("  - %s %s: %s" % (sid, results[sid]["verdict"], results[sid]["reason"]), file=sys.stderr)
    if verdict == "PASS":
        print("OK: %d capture(s) qualified against the corpus %s → %s" % (len(results), corpus_sha[:12], out.relative_to(root)))
        return 0
    print("REFUSE: qualification %s (%d of %d not qualified) → %s" % (verdict, len(not_passed), len(results), out.relative_to(root)), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
