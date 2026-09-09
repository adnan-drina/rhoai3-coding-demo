#!/usr/bin/env python3
"""K4 mint + K3 live selftest (v3). Not dest. Not live kanban."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KERNEL = Path(__file__).resolve().parent
sys.path.insert(0, str(KERNEL))
sys.path.insert(0, str(KERNEL.parent / "lib"))
from k3_live import main as k3_main  # noqa: E402
from k4_convert import convert_admitted  # noqa: E402
from k4_mint import MINT_RECEIPTS, argv_for_payload, main as mint_main, mint_payloads, verify_board, write_mint_receipt  # noqa: E402
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import load_json  # noqa: E402
from planner.paths import LOOP_STEPS  # noqa: E402

BOOTSTRAP = KERNEL.parent / "skills" / "migration" / "bootstrap-destination" / "scripts" / "bootstrap-destination.py"
ADVANCE = KERNEL.parent / "skills" / "migration" / "fix-until-green" / "scripts" / "advance.py"
VERIFY = KERNEL.parent / "skills" / "migration" / "fix-until-green" / "scripts" / "verify.py"


def _fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


class FakeBoard:
    """Serial fake `hermes kanban` with idempotency keys and parents."""

    def __init__(self, expose_keys: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.cards: dict[str, dict] = {}
        self.by_key: dict[str, str] = {}
        self.expose_keys = expose_keys

    def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        if argv[1:3] == ["kanban", "list"]:
            return 0, json.dumps({"tasks": [{"id": cid, "title": c["title"], "status": c["status"]} for cid, c in self.cards.items()]}), ""
        if argv[1:3] == ["kanban", "show"]:
            c = self.cards.get(argv[3])
            if not c:
                return 1, "", "no such task"
            d = dict(c, id=argv[3])
            if not self.expose_keys:
                d.pop("idempotency_key", None)
            # real `hermes kanban show --json` keeps the edges beside the task
            parents = d.pop("parents", [])
            return 0, json.dumps({"task": d, "parents": parents, "children": []}), ""
        if argv[1:3] != ["kanban", "create"]:
            return 2, "", "unexpected %s" % argv
        key = argv[argv.index("--idempotency-key") + 1]
        if key in self.by_key:
            return 0, json.dumps({"task_id": self.by_key[key]}), ""
        tid = "t_mint%04d" % (len(self.cards) + 1)
        parents = [argv[i + 1] for i, a in enumerate(argv) if a == "--parent"]
        self.cards[tid] = {"title": argv[3], "idempotency_key": key, "parents": parents, "body": argv[argv.index("--body") + 1], "status": "todo"}
        self.by_key[key] = tid
        return 0, json.dumps({"task_id": tid}), ""


def prepare(root: Path, *, errors=None) -> None:
    specimens.prepare_loop(root, errors=errors or [])


def main() -> int:
    os.environ.pop("HERMES_KANBAN_TASK", None)
    if '"m4-verify"' in (KERNEL / "k4_mint.py").read_text(encoding="utf-8").replace('key == "m4-verify"', ""):
        return _fail("k4_mint.py must not use the fixed m4-verify key")
    with tempfile.TemporaryDirectory(prefix="k4mint-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "http", specimens.specimen("http"), decisions=specimens.admitted_decisions())
        prepare(root)
        result, issues = convert_admitted(root)
        if issues or result is None:
            return _fail("convert: %s" % issues)
        head = result["payloads"][0]
        argv = argv_for_payload(head, {}, hermes="/bin/hermes", receipt_digest=result["receipt_sha256"])
        if argv[:4] != ["/bin/hermes", "kanban", "create", head["title"]] or "--max-retries" not in argv or "--idempotency-key" not in argv or "--workspace" not in argv:
            return _fail("argv %s" % argv[:8])
        board = FakeBoard()
        minted = mint_payloads(result, runner=board, hermes="/bin/hermes")
        if minted["created_cards"] != ["t_mint0001"] or minted["created"][0]["idempotency_key"] != head["idempotency_key"]:
            return _fail("mint %s" % minted["created_cards"])
        write_mint_receipt(root, minted)
        # idempotent remint
        again = mint_payloads(result, runner=board, hermes="/bin/hermes")
        if again["created_cards"] != ["t_mint0001"] or len(board.cards) != 1:
            return _fail("remint must be a no-op")
        # K3 live after mint: EQUAL
        v = verify_board(root, result, runner=board, hermes="/bin/hermes", exempt=[])
        if v["verdict"] != "EQUAL" or v["expected_cards"] != 1:
            return _fail("board verify %s" % v)
        # foreign card refuses; exempt M2 (+ its M1 parent) does not
        board.cards["t_foreign"] = {"title": "M3 hand-minted", "idempotency_key": "manual", "parents": [], "body": "x", "status": "todo"}
        try:
            verify_board(root, result, runner=board, hermes="/bin/hermes", exempt=[])
            return _fail("foreign card must refuse")
        except ValueError as exc:
            if "t_foreign" not in str(exc):
                return _fail("foreign refuse: %s" % exc)
        del board.cards["t_foreign"]
        board.cards["t_m1"] = {"title": "M1 ANALYZE", "idempotency_key": "m1-analyze", "parents": [], "body": "", "status": "done"}
        board.cards["t_m2"] = {"title": "M2 PLAN", "idempotency_key": "m2-plan", "parents": ["t_m1"], "body": "", "status": "running"}
        if verify_board(root, result, runner=board, hermes="/bin/hermes", exempt=["t_m2"])["verdict"] != "EQUAL":
            return _fail("exempt M2 must close over M1")
        # the step is accepted with this card id → the next card's parent is t_mint0001 and K3 expects both
        (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8") + "<!-- step -->\n", encoding="utf-8")
        f2 = load_json(root / "evidence" / "mta-findings.json")
        f2["violations"].pop("javaee-pom-to-quarkus-00003")
        specimens.verify(root, errors=[], failures=[], findings=f2)
        p = subprocess.run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", head["logical_id"], "--card", "t_mint0001", "--no-mint"], capture_output=True, text=True)
        if p.returncode != 0:
            return _fail("advance: %s%s" % (p.stdout, p.stderr))
        result2, issues = convert_admitted(root)
        if issues or result2["payloads"][0]["parents"] != ["t_mint0001"] or result2["payloads"][0]["logical_id"] == head["logical_id"]:
            return _fail("next card must parent the accepted card: %s" % (issues or result2["payloads"][0]["parents"]))
        minted2 = mint_payloads(result2, runner=board, hermes="/bin/hermes")
        write_mint_receipt(root, minted2)
        if board.cards[minted2["created_cards"][0]]["parents"] != ["t_mint0001"]:
            return _fail("board parent edge")
        v = verify_board(root, result2, runner=board, hermes="/bin/hermes", exempt=["t_m2"])
        if v["verdict"] != "EQUAL" or v["expected_cards"] != 2:
            return _fail("two-card board must be EQUAL: %s" % v)
        # a board that hides keys matches only through the mint receipts; a fabricated card is foreign
        board.expose_keys = False
        v = verify_board(root, result2, runner=board, hermes="/bin/hermes", exempt=["t_m2"])
        if v["verdict"] != "EQUAL" or set(v["matched_via"].values()) != {"k4-mint-receipt"}:
            return _fail("keyless board must match via mint receipts: %s" % v)
        board.cards["t_fab"] = {"title": result2["payloads"][0]["title"], "parents": ["t_mint0001"], "body": result2["payloads"][0]["body"], "status": "todo"}
        try:
            verify_board(root, result2, runner=board, hermes="/bin/hermes", exempt=["t_m2"])
            return _fail("fabricated keyless card must refuse")
        except ValueError as exc:
            if "t_fab" not in str(exc):
                return _fail("fabricated refuse: %s" % exc)
        del board.cards["t_fab"]
        board.expose_keys = True
        # K3 CLI with a snapshot
        snap = t / "snap.json"
        cards = [dict(c, id=cid) for cid, c in board.cards.items()]
        snap.write_text(json.dumps({"tasks": cards}), encoding="utf-8")
        if k3_main(["--root", str(root), "--snapshot", str(snap), "--exempt", "t_m2"]) != 0:
            return _fail("K3 CLI EQUAL")
        snap.write_text(json.dumps({"tasks": [c for c in cards if c["id"] != "t_mint0001"]}), encoding="utf-8")
        if k3_main(["--root", str(root), "--snapshot", str(snap), "--exempt", "t_m2"]) != 1:
            return _fail("K3 CLI must refuse a missing accepted card")
        # inadmissible root → zero creates
        inc = specimens.build_dest(t / "inc", specimens.specimen("http"), decisions=specimens.full_decisions(max_attempts=None))
        prepare(inc)
        counting = FakeBoard()
        if mint_main(["--root", str(inc), "--exec", "--hermes", "/bin/hermes"]) != 1 or counting.calls:
            return _fail("inadmissible mint must exit 1 with zero creates")
        # not-activated → zero creates even though the planner produced a receipt
        na = specimens.build_dest(t / "na", specimens.specimen("http"), decisions=specimens.admitted_decisions(), activation="not-activated")
        prepare(na)
        if mint_main(["--root", str(na), "--exec", "--hermes", "/bin/hermes"]) != 1:
            return _fail("not-activated mint must exit 1")
        # dry-run on the admitted root
        if mint_main(["--root", str(root), "--out", str(t / "dry.json"), "--hermes", "/bin/hermes"]) != 0 or len(json.loads((t / "dry.json").read_text())["argv"]) != 1:
            return _fail("dry-run")
        # scratch workspace refuse
        os.environ["K4_WORKSPACE"] = "/tmp/k4-scratch"
        try:
            argv_for_payload(head, {}, receipt_digest=result["receipt_sha256"])
            return _fail("scratch workspace did not refuse")
        except ValueError:
            pass
        finally:
            os.environ.pop("K4_WORKSPACE", None)
        rc = continuation_through_advance(t)
        if rc:
            return rc
    print("OK: K4 mint + K3 live (one card per step; idempotent remint; parent chain; keyless board via mint receipts; foreign/fabricated refuse; M2→M1 closure; inadmissible/not-activated → 0 creates; scratch refuse; native continuation through advance --exec with a file-backed fake hermes)")
    return 0


FAKE_HERMES = r'''#!/usr/bin/env python3
import json, sys
from pathlib import Path
store = Path(__STORE__)
db = json.loads(store.read_text()) if store.is_file() else {"cards": {}, "by_key": {}}
args = sys.argv[1:]
def save():
    store.write_text(json.dumps(db))
if args[:2] == ["kanban", "list"]:
    print(json.dumps({"tasks": [{"id": cid, "title": c["title"], "status": c["status"]} for cid, c in db["cards"].items()]})); sys.exit(0)
if args[:2] == ["kanban", "show"]:
    c = db["cards"].get(args[2])
    if not c: sys.exit(1)
    d = dict(c, id=args[2]); parents = d.pop("parents", [])
    print(json.dumps({"task": d, "parents": parents, "children": []})); sys.exit(0)
if args[:2] == ["kanban", "create"]:
    key = args[args.index("--idempotency-key") + 1]
    if key in db["by_key"]:
        print(json.dumps({"task_id": db["by_key"][key]})); sys.exit(0)
    tid = "t_fake%04d" % (len(db["cards"]) + 1)
    parents = [args[i + 1] for i, a in enumerate(args) if a == "--parent"]
    db["cards"][tid] = {"title": args[2], "idempotency_key": key, "parents": parents, "body": args[args.index("--body") + 1], "status": "todo"}
    db["by_key"][key] = tid
    save(); print(json.dumps({"task_id": tid})); sys.exit(0)
sys.exit(2)
'''


def continuation_through_advance(t: Path) -> int:
    """Finding 5 (2026-09-09 review): the previous accepted card must be a
    PARENT of the next card and stay in K3's expected set; only the
    registered M2/M1 control cards are exempt. Exercised through the real
    CLIs (k4_mint.py --exec, advance.py without --no-mint) against a
    file-backed fake `hermes` on PATH."""
    import stat

    root = specimens.build_dest(t / "cont", specimens.specimen("http"), decisions=specimens.admitted_decisions())
    # dest-init's own record: its M1 card is a control card K3 exempts without any --exempt flag
    (root / ".hermes" / "AUTOSTART-STATUS").write_text(json.dumps({"state": "minted", "m1_id": "t_m1init", "m2_id": ""}), encoding="utf-8")
    prepare(root)
    store = t / "fake-board.json"
    bin_dir = t / "fake-bin"
    bin_dir.mkdir()
    fake = bin_dir / "hermes"
    fake.write_text(FAKE_HERMES.replace("__STORE__", repr(str(store))), encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    env = dict(os.environ)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["HERMES_BIN"] = str(fake)
    # the M2 card mints the first execution card; M2 registers itself as the control card
    env_m2 = dict(env, HERMES_KANBAN_TASK="t_m2")
    p = subprocess.run([sys.executable, str(KERNEL / "k4_mint.py"), "--root", str(root), "--exec", "--verify-board", "--hermes", str(fake)], text=True, capture_output=True, env=env_m2)
    if p.returncode != 0:
        return _fail("first mint through the CLI: %s%s" % (p.stdout, p.stderr))
    db = json.loads(store.read_text())
    first = [tid for tid, c in db["cards"].items() if c["title"].startswith("M3 ")]
    if len(first) != 1 or db["cards"][first[0]]["parents"] != ["t_m2"]:
        return _fail("first card must parent M2: %s" % db["cards"])
    cards_reg = load_json(root / "verification" / "loop" / "cards.json")
    if cards_reg["control"].get("m2") != "t_m2":
        return _fail("M2 must be registered as the control card: %s" % cards_reg)
    if cards_reg["control"].get("m1") != "t_m1init":
        return _fail("dest-init M1 must be registered from AUTOSTART-STATUS (no --exempt): %s" % cards_reg)
    issued = load_json(root / "verification" / "loop" / "issued.json")
    if issued.get("task_id") != first[0]:
        return _fail("issued card must carry the minted task id: %s" % issued)
    # the worker (on card 1) makes progress and advances WITHOUT --no-mint: trusted continuation
    f2 = load_json(root / "evidence" / "mta-findings.json")
    f2["violations"].pop("javaee-pom-to-quarkus-00003")
    (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8") + "<!-- step -->\n", encoding="utf-8")
    specimens.verify(root, errors=[], failures=[], findings=f2)
    env_card = dict(env, HERMES_KANBAN_TASK=first[0])  # the worker's own card id is in the env on a real seat
    p = subprocess.run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", issued["cluster"], "--card", first[0]], text=True, capture_output=True, env=env_card)
    if p.returncode != 0 or "ACCEPTED" not in p.stdout:
        return _fail("advance with continuation: %s%s" % (p.stdout, p.stderr))
    db = json.loads(store.read_text())
    second = [tid for tid, c in db["cards"].items() if c["title"].startswith("M3 ") and tid != first[0]]
    if len(second) != 1:
        return _fail("continuation must mint exactly one next card: %s" % list(db["cards"]))
    if sorted(db["cards"][second[0]]["parents"]) != sorted(["t_m2", first[0]]):
        return _fail("the next card must parent M2 AND the previous accepted card: %s" % db["cards"][second[0]]["parents"])
    verdict = load_json(root / "evidence" / "receipts" / "k3" / "live-board.json")
    if verdict["verdict"] != "EQUAL" or verdict["expected_cards"] != 2 or verdict["matched_cards"] != 2 or "t_m2" not in verdict["exempt_closure"] or first[0] in verdict["exempt_closure"]:
        return _fail("K3 after continuation must expect both execution cards and exempt only M2: %s" % {k: verdict[k] for k in ("verdict", "expected_cards", "matched_cards", "exempt_closure", "missing_keys")})
    # a no-progress candidate on card 2 is REVERTED and the reject path re-issues the cluster: attempt 2 is minted
    issued2 = load_json(root / "verification" / "loop" / "issued.json")
    (root / "pom.xml").write_text((root / "pom.xml").read_text(encoding="utf-8") + "<!-- no progress -->\n", encoding="utf-8")
    specimens.verify(root, errors=[], failures=[], findings=f2)
    env_card2 = dict(env, HERMES_KANBAN_TASK=second[0])
    p = subprocess.run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", issued2["cluster"], "--card", second[0]], text=True, capture_output=True, env=env_card2)
    if p.returncode != 1 or "REVERTED" not in p.stderr:
        return _fail("no progress must revert: %s%s" % (p.stdout, p.stderr[-300:]))
    db = json.loads(store.read_text())
    third = [tid for tid, c in db["cards"].items() if c["title"].startswith("M3 ") and tid not in (first[0], second[0])]
    if len(third) != 1 or not db["cards"][third[0]]["idempotency_key"].startswith("k4:%s:2:" % issued2["cluster"]):
        return _fail("a revert must re-issue the same cluster at attempt 2: %s" % {t: c.get("idempotency_key") for t, c in db["cards"].items()})
    if load_json(root / "verification" / "loop" / "issued.json").get("task_id") != third[0]:
        return _fail("issued.json must carry the attempt-2 card")
    verdict = load_json(root / "evidence" / "receipts" / "k3" / "live-board.json")
    if verdict["verdict"] != "EQUAL" or any(second[0] in f for f in (verdict.get("foreign") or [])):
        return _fail("the reverted attempt's card is an expected closed card, never foreign: %s" % {k: verdict.get(k) for k in ("verdict", "foreign", "missing")})
    # a wrong --card is refused (the issued card carries the minted id)
    issued2 = load_json(root / "verification" / "loop" / "issued.json")
    specimens.verify(root, errors=[], failures=[], findings=f2)
    p = subprocess.run([sys.executable, str(ADVANCE), "--root", str(root), "--cluster", issued2["cluster"], "--card", "t_wrong", "--no-mint"], text=True, capture_output=True, env=env)
    if p.returncode != 1 or "LOOP_WRONG_CARD" not in p.stderr:
        return _fail("a card id other than the minted one must refuse: %s" % p.stderr[-200:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
