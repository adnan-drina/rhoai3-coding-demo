#!/usr/bin/env python3
"""L2 mint oracles — refs path-sha, Hermes task_id, SR-13 discriminating exit.

Operator E-20260815T010500Z: a mint that accepts the banked defective bodies
is not ready. Each oracle must refuse its historical instance and pass a
corrected body (SR-6 both ways).

  1. refs — sha256(resolve(path)) equals the stamped digest. `pending` is
     legal only for creation-time ack keys (brief_identity_ack,
     m1_findings_ack). Harvest/dest-inventory hex must resolve at mint.
  2. task_id — body.task_id is a Hermes card id (`t_<hex>`). After create,
     it must equal the card just minted. Do not require t_* in
     check-kanban-body pre-create (assembler stamps story_id first).
  3. discriminating exit — the test proving this card's AC lives in this
     write-set. A test-shaped `mvn … test` must name `proves` test source(s)
     in this body's `files_writable` (L2a). `true` and a test cmd with no
     named proving test refuse. `mvn verify` is test-shaped (runs tests).
     `test-compile` is not. curl / scripts are not card exits — live
     acceptance is M4/M5. An unrelated dest `src/test` file must not flip
     the oracle. Compile-shaped cmds are unchanged. Golden must not require
     mvn on PATH.

Usage:
  python3 assert-mint-oracles.py . --body evidence/bodies/m3-s-003.json
  python3 assert-mint-oracles.py . --body PATH --skip-task-id
  python3 assert-mint-oracles.py . --body PATH --expect-task-id t_aabbccdd
  python3 assert-mint-oracles.py DEST --corpus DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from specimen_agnostic import (  # noqa: E402
    exit_cmd_discriminating_errors,
    minted_task_id_errors,
    refs_path_sha_errors,
)

EXIT_CODES = """Exit codes:
  0  pass — every enabled oracle holds (single body) or every corpus
     body fails at least one oracle
  1  BLOCK — single body fails an oracle, or a corpus body passes all
  2  usage / harness defect
"""


def load_body(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw.get("body"), dict):
        return raw["body"]
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: body is not an object")
    return raw


def evaluate_body(
    root: Path,
    body: dict,
    *,
    check_refs: bool,
    check_task_id: bool,
    check_exit: bool,
    expect_task_id: str | None,
) -> list[str]:
    errs: list[str] = []
    if check_refs:
        refs = body.get("refs") if isinstance(body.get("refs"), list) else []
        errs.extend(refs_path_sha_errors(root, refs))
    if check_task_id:
        errs.extend(minted_task_id_errors(body, expect_task_id=expect_task_id))
    if check_exit:
        errs.extend(exit_cmd_discriminating_errors(root, body))
    return errs


def iter_corpus(corpus: Path) -> list[Path]:
    if not corpus.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(corpus.glob("*.json")):
        if path.name.endswith(".sha256.json"):
            continue
        out.append(path)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="destination / product root (pre-story tree lives here)",
    )
    ap.add_argument("--body", help="single M3 body JSON")
    ap.add_argument(
        "--corpus",
        help="directory of body JSON files — fail if any body passes all "
        "enabled oracles (banked-defective entry gate)",
    )
    ap.add_argument(
        "--expect-task-id",
        help="post-bind: body.task_id must equal this Hermes card id",
    )
    ap.add_argument(
        "--skip-task-id",
        action="store_true",
        help="pre-create: assembler still stamps task_id=story_id",
    )
    ap.add_argument(
        "--skip-refs",
        action="store_true",
        help="isolate task_id / discriminating-exit (host corpus without harvest)",
    )
    ap.add_argument(
        "--skip-exit",
        action="store_true",
        help="isolate refs / task_id",
    )
    args = ap.parse_args()
    if bool(args.body) == bool(args.corpus):
        print(
            "assert-mint-oracles: pass exactly one of --body or --corpus",
            file=sys.stderr,
        )
        return 2
    if args.skip_task_id and args.expect_task_id:
        print(
            "assert-mint-oracles: --skip-task-id and --expect-task-id conflict",
            file=sys.stderr,
        )
        return 2

    root = Path(args.root).resolve()
    check_refs = not args.skip_refs
    check_task_id = not args.skip_task_id
    check_exit = not args.skip_exit
    if not (check_refs or check_task_id or check_exit):
        print(
            "assert-mint-oracles: all oracles skipped",
            file=sys.stderr,
        )
        return 2

    if args.body:
        body_path = Path(args.body)
        if not body_path.is_file():
            body_path = root / args.body
        if not body_path.is_file():
            print(f"FAIL: body missing {args.body}", file=sys.stderr)
            return 1
        try:
            body = load_body(body_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"FAIL: {body_path}: {exc}", file=sys.stderr)
            return 1
        errs = evaluate_body(
            root,
            body,
            check_refs=check_refs,
            check_task_id=check_task_id,
            check_exit=check_exit,
            expect_task_id=args.expect_task_id,
        )
        if errs:
            for e in errs:
                print(f"FAIL: mint-oracles {body_path}: {e}", file=sys.stderr)
            return 1
        print(f"OK: mint-oracles {body_path.name}")
        return 0

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        corpus = root / args.corpus
    paths = iter_corpus(corpus)
    if not paths:
        print(f"FAIL: mint-oracles corpus empty: {args.corpus}", file=sys.stderr)
        return 1
    passed: list[str] = []
    refused = 0
    for path in paths:
        try:
            body = load_body(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"FAIL: mint-oracles corpus {path}: {exc}", file=sys.stderr)
            return 1
        errs = evaluate_body(
            root,
            body,
            check_refs=check_refs,
            check_task_id=check_task_id,
            check_exit=check_exit,
            expect_task_id=None,
        )
        if errs:
            refused += 1
            print(f"REFUSED: {path.name} ({errs[0]})", file=sys.stderr)
        else:
            passed.append(path.name)
            print(
                f"FAIL: mint-oracles corpus {path.name} passed all enabled oracles",
                file=sys.stderr,
            )
    if passed:
        print(
            f"FAIL: mint-oracles corpus accepted {len(passed)}/{len(paths)} "
            f"(a mint that accepts defective bodies is not ready)",
            file=sys.stderr,
        )
        return 1
    print(f"OK: mint-oracles corpus refused n={refused}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
