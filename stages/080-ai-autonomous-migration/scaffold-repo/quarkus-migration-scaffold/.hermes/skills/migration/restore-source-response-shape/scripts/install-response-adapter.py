#!/usr/bin/env python3
"""Install (or check) a source-preserving response adapter (ADR-019).

  install-response-adapter.py --root . --adapter cors
  install-response-adapter.py --root . --adapter media-type
  install-response-adapter.py --root . --adapter cors --check      # verify, write nothing
  install-response-adapter.py --root . --adapter cors --print      # show the rendering, write nothing
  install-response-adapter.py --root . --adapter cors --operator-step ADR-019 --reason "..."

AUTHORITY. An adapter is installed on a recorded obligation, never on a
request: the current work list must carry the capability's own obligation
(PARITY_CORS for ``cors``, PARITY_CONTENT_TYPE for ``media-type``) naming this
contract, and when a loop card is issued both the adapter path and the
configuration file must already be in its write set. A CORS obligation never
authorizes the media-type adapter, and the reverse. The only other authority is
a named Operator step (``--operator-step <ADR> --reason``), recorded as such in
the receipt.

WHAT IT WRITES. The adapter file, byte-for-byte from the harness template, at
the path the naming contract fixes (absent or identical only), and one marked
block of explicit rows in src/main/resources/application.properties rendered
from the evidence: the frozen source's CORS policy (M1's structural model and
the source's security configuration) or the decided media-type parameter (the
recorded Content-Type differences). Rows of the capability's own family
elsewhere in the file are replaced and listed in the receipt,
evidence/response-adapters/<adapter>.json. Re-running changes nothing.

Exit 0 on success; 1 with ``REFUSE: <CODE> ...`` otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _lib() -> None:
    for parent in Path(__file__).resolve().parents:
        lib = parent / "lib"
        if (lib / ".hermes-lib").is_file():
            if str(lib) not in sys.path:
                sys.path.insert(0, str(lib))
            return
    raise SystemExit("REFUSE: HARNESS_LIB_MISSING no .hermes/lib above %s" % __file__)


_lib()

import response_adapters as ra  # noqa: E402

WORKLIST = Path("evidence") / "planning" / "worklist.json"
ISSUED = Path("verification") / "loop" / "issued.json"


def _load(p: Path) -> dict:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def obligations(root: Path, kind: str) -> list[dict]:
    """The current work list's obligations for THIS capability."""
    want = ra.CONTRACTS[kind]
    out = []
    for it in _load(root / WORKLIST).get("items") or []:
        if not isinstance(it, dict):
            continue
        owed = it.get("owed") if isinstance(it.get("owed"), dict) else {}
        if str(it.get("rule_id") or "") == want["rule_id"] and str(owed.get("contract") or "") == want["contract"]:
            out.append(it)
    return out


def authority(root: Path, kind: str, args: argparse.Namespace) -> tuple[dict, list[dict], str]:
    """(the authority row, the obligations, why there is none)."""
    if args.operator_step:
        if len(str(args.reason or "").strip()) < 12:
            return {}, [], "an Operator step names its reason (--reason)"
        return {"kind": "operator-step", "adr": args.operator_step, "reason": args.reason.strip()}, obligations(root, kind), ""
    rows = obligations(root, kind)
    if not rows:
        return {}, [], ("the work list %s carries no %s obligation under %s; this adapter is installed on a recorded "
                        "obligation (or a named Operator step), never on a request"
                        % (WORKLIST, ra.CONTRACTS[kind]["rule_id"], ra.CONTRACTS[kind]["contract"]))
    issued = _load(root / ISSUED)
    card = ""
    if issued:
        ws = set(issued.get("write_set") or [])
        need = [p for p in (ra.adapter_path(kind), ra.APP_PROPERTIES) if p not in ws]
        if need:
            return {}, rows, ("the issued card %s does not have %s in its write set; the sealed scope is what authorizes "
                              "the edit, so it has to name them before the files move"
                              % (issued.get("cluster") or "?", ", ".join(need)))
        card = str(issued.get("task_id") or issued.get("cluster") or "")
    return {"kind": "obligation", "items": sorted(str(i.get("id")) for i in rows), "card": card}, rows, ""


def decision_for(kind: str, rows: list[dict], args: argparse.Namespace) -> dict | None:
    if kind != ra.MEDIA_TYPE:
        return None
    if args.parameter or args.media_type:
        if not args.operator_step:
            raise ra.Refuse("MEDIA_TYPE_UNDECIDED", "--parameter/--media-type are an Operator step's; a worker installs "
                                                    "the parameter its obligation decided")
        name, _, value = str(args.parameter or "").partition("=")
        if not name or not value or not args.media_type:
            raise ra.Refuse("MEDIA_TYPE_UNDECIDED", "--parameter NAME=VALUE and --media-type TYPE are both required")
        return {"parameter": name.strip().lower(), "value": value.strip(),
                "media_types": sorted({m.strip().lower() for m in args.media_type})}
    diffs = []
    for it in rows:
        diffs.extend((it.get("owed") or {}).get("differences") or [])
    return ra.media_type_decision(diffs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--adapter", required=True, choices=ra.KINDS)
    ap.add_argument("--check", action="store_true", help="verify the installation against the rendering; write nothing")
    ap.add_argument("--print", dest="show", action="store_true", help="print the rendering; write nothing")
    ap.add_argument("--operator-step", default="", help="an Operator application under this ADR")
    ap.add_argument("--reason", default="")
    ap.add_argument("--parameter", default="", help="Operator step, media-type only: NAME=VALUE")
    ap.add_argument("--media-type", action="append", default=[], help="Operator step, media-type only")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    kind = args.adapter
    try:
        auth, rows, why = authority(root, kind, args)
        if not auth and not (args.show or args.check):
            print("REFUSE: ADAPTER_UNAUTHORIZED %s" % why, file=sys.stderr)
            return 1
        decision = decision_for(kind, rows, args)
        props, basis = ra.rows_for(root, kind, decision)
        if args.show:
            print(json.dumps({"adapter": ra.contract(kind), "basis": basis,
                              "properties": [{"key": k, "value": v} for k, v in props]}, indent=2, sort_keys=True))
            return 0
        if args.check:
            problems = ra.verify(root, kind, props)
            if problems:
                print("REFUSE: ADAPTER_NOT_INSTALLED %s" % "; ".join(problems[:6]), file=sys.stderr)
                return 1
            print("OK: %s is installed exactly as rendered (%d row(s))" % (ra.CONTRACTS[kind]["contract"], len(props)))
            return 0
        receipt = ra.install(root, kind, props, basis=basis, authority=auth)
    except ra.Refuse as exc:
        print("REFUSE: %s" % exc, file=sys.stderr)
        return 1
    problems = ra.verify(root, kind, props)
    if problems:
        print("REFUSE: ADAPTER_NOT_INSTALLED %s" % "; ".join(problems[:6]), file=sys.stderr)
        return 1
    print("OK: %s installed at %s (%s); %d row(s) in %s, %d replaced; receipt %s"
          % (ra.CONTRACTS[kind]["contract"], ra.adapter_path(kind),
             "unchanged" if not receipt["changed"] else "changed " + ", ".join(receipt["changed"]),
             len(props), ra.APP_PROPERTIES, len(receipt["replaced"]), (ra.RECEIPT_DIR / ("%s.json" % kind)).as_posix()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
