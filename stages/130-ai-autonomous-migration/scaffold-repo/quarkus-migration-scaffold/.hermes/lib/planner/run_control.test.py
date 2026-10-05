#!/usr/bin/env python3
"""run_control selftest (B8, B10, B4 under the release review's R1 and R3).

A GOVERNED run (its initial-commit run-budget.json declares run_control):
  * is authorized by the platform's read-only contract, never by pins.json:
    git checkout/reset/stash of the pins and a forged `activated` change nothing
  * refuses a missing contract, an empty one, a malformed one, a missing
    control directory, a foreign run id or scaffolding commit -- and an
    environment variable pointing at another, valid directory is ignored
  * binds the M1 bundle digest exactly once (write-once file, same digest ok,
    another refused) for the run the platform authorized
  * refuses a harness file changed, deleted or added since the recorded
    release (bytecode caches excepted) until the Operator records a rebase
  * refuses a missing pinned profile, a runtime profile that differs from it
    (named field, digests recomputed from content) and a generated config
    that does not carry it on the provider and every auto auxiliary slot
  * cannot be re-blessed: the module has no writer for any pin, so a lost
    record stays a refusal across any number of re-reads
A LEGACY run (no run_control in its declaration) keeps pins.json and no gaps.
Run under two run names.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner import pins as pins_mod, run_control  # noqa: E402

BUNDLE = "b" * 64


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


PROFILE = {"default_model": "m-1", "profiles": {"m-1": {"provider": "p1", "mode": "non-thinking", "context_length": 1000,
           "max_tokens": 100, "request_body": {"temperature": 0.7, "presence_penalty": 1.5},
           "quota": {"max_requests_per_window": 200, "window_seconds": 3600, "max_output_tokens": 300}}}}
AUX = dict(PROFILE["profiles"]["m-1"]["request_body"], max_tokens=300)


def _config(profile: dict, aux_body: dict | None) -> str:
    prof = profile["profiles"][profile["default_model"]]
    lines = ["model:", "  default: %s" % profile["default_model"], "  provider: %s" % prof["provider"],
             "  context_length: %d" % prof["context_length"], "  max_tokens: %d" % prof["max_tokens"],
             "providers:", "  %s:" % prof["provider"], "    extra_body:"]
    lines += ["      %s: %s" % (k, v) for k, v in prof["request_body"].items()]
    lines += ["auxiliary:", "  compression:", "    provider: auto"]
    if aux_body is not None:
        lines += ["    extra_body:"] + ["      %s: %s" % (k, v) for k, v in aux_body.items()]
    lines += ["  title_generation:", "    enabled: false"]
    return "\n".join(lines) + "\n"


def _governed(td: Path, run: str) -> tuple[Path, Path, Path, Path]:
    root, control, state, managed = td / "projects" / "modernized", td / "control", td / "state", td / "managed"
    for d in (root / ".hermes/lib", root / ".hermes/kernel", root / ".hermes/skills/x", control, managed):
        d.mkdir(parents=True)
    (root / ".hermes/lib/a.py").write_text("A = 1\n", encoding="utf-8")
    (root / ".hermes/kernel/k.py").write_text("K = 1\n", encoding="utf-8")
    (root / ".hermes/skills/x/SKILL.md").write_text("# x\n", encoding="utf-8")
    (root / ".hermes/pins.json").write_text(json.dumps({"pins": {"planner": {"activation": "not-activated"}}}), encoding="utf-8")
    (root / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run,
        "run_control": {"contract": run_control.CONTRACT_SCHEMA, "root": str(control), "state": str(state)}}), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "scaffold")
    initial = _git(root, "rev-parse", "HEAD")
    (control / "contract.json").write_text(json.dumps({"schema": run_control.CONTRACT_SCHEMA, "run_id": run,
        "scaffold_commit": initial, "activation": "pilot", "authorized_by": "provision-migration-run:tr-1",
        "authorization": {"event": "scaffolding push", "scaffold_commit": initial}}), encoding="utf-8")
    (control / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
    eff = dict(PROFILE, digest=run_control.profile_digest(PROFILE))
    (managed / "model-profile.json").write_text(json.dumps(eff), encoding="utf-8")
    (managed / "config.yaml").write_text(_config(PROFILE, AUX), encoding="utf-8")
    (managed / ".env").write_text("MAAS_API_KEY=x\nRHOAI3_REQUEST_BUDGET=200/3600\nRHOAI3_REQUEST_LEDGER=/l/requests.log\n", encoding="utf-8")
    return root, control, state, managed


def _case(run: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        root, control, state, managed = _governed(td, run)
        os.environ["HERMES_MANAGED_DIR"] = str(managed)
        try:
            gaps = run_control.run_gaps(root)
            if gaps:
                return _fail("an intact governed run has no gaps (%s): %s" % (run, gaps))
            p = pins_mod.load_pins(root)
            if pins_mod.planner_activation(p) != "pilot" or not any("sha256" in g for g in pins_mod.activation_gaps(p, BUNDLE)):
                return _fail("the platform authorizes a pilot, unbound until M1: %s" % pins_mod.activation_gaps(p, BUNDLE))
            if pins_mod.pilot_bind_gaps(p):
                return _fail("the platform authorization is bindable: %s" % pins_mod.pilot_bind_gaps(p))
            ok, msg = run_control.bind(root, BUNDLE, "M1")
            b = state / "binding.json"
            if not ok or stat.S_IMODE(b.stat().st_mode) & 0o222 or pins_mod.activation_gaps(pins_mod.load_pins(root), BUNDLE):
                return _fail("the M1 binding is written once, read-only, and admits the bundle: %s" % msg)
            ok2, msg2 = run_control.bind(root, "c" * 64, "again")
            if ok2 or "never rewritten" not in msg2 or not run_control.bind(root, BUNDLE, "same")[0]:
                return _fail("a second binding to another digest is refused; the same digest is idempotent: %s" % msg2)
            # the v12 incident and a forged activation: pins.json is not read at all
            for how in (["checkout", "--", ".hermes/pins.json"], ["reset", "--hard", "-q"], ["stash", "-q"]):
                (root / ".hermes/pins.json").write_text(json.dumps({"pins": {"planner": {"activation": "activated"}}}), encoding="utf-8")
                subprocess.run(["git", "-C", str(root), *how], capture_output=True)
                pp = pins_mod.load_pins(root)
                if pins_mod.planner_activation(pp) != "pilot" or pins_mod.activation_gaps(pp, BUNDLE):
                    return _fail("git %s / a forged pins.json change nothing for a governed run" % how[0])
            # release drift and the Operator's recorded rebase
            (root / ".hermes/lib/a.py").write_text("A = 2\n", encoding="utf-8")
            (root / ".hermes/skills/x/new.py").write_text("X = 1\n", encoding="utf-8")
            (root / ".hermes/lib/__pycache__").mkdir()
            (root / ".hermes/lib/__pycache__/a.cpython-311.pyc").write_bytes(b"\0")
            g = run_control.release_gaps(root)
            if not g or not g[0].startswith("HARNESS_RELEASE_MISMATCH") or ".hermes/lib/a.py" not in g[0] or "new.py" not in g[0] or "pyc" in g[0]:
                return _fail("a changed and an added harness file are drift, a bytecode cache is not: %s" % g)
            _git(root, "add", ".hermes/lib/a.py", ".hermes/skills/x/new.py")
            _git(root, "commit", "-q", "-m", "assisted harness install")
            if not run_control.release_gaps(root):
                return _fail("a committed harness change is still drift until the Operator records it")
            (control / "release-rebase.json").write_text(json.dumps({"commit": _git(root, "rev-parse", "HEAD"),
                                                                    "reason": "assisted install"}), encoding="utf-8")
            if run_control.release_gaps(root):
                return _fail("the Operator's recorded rebase is the release: %s" % run_control.release_gaps(root))
            # profile drift, digests from content, and the generated config
            eff = json.loads((managed / "model-profile.json").read_text())
            eff["profiles"]["m-1"]["request_body"]["presence_penalty"] = 0.0   # the stored digest is left untouched
            (managed / "model-profile.json").write_text(json.dumps(eff), encoding="utf-8")
            g = run_control.profile_gaps(root)
            if not g or "presence_penalty: expected 1.5, got 0.0" not in g[0]:
                return _fail("a runtime profile changed under an unchanged stored digest is refused: %s" % g)
            (managed / "model-profile.json").write_text(json.dumps(dict(PROFILE, digest="x")), encoding="utf-8")
            (managed / "config.yaml").write_text(_config(PROFILE, None), encoding="utf-8")
            g = run_control.profile_gaps(root)
            if not g or "auxiliary.compression.extra_body" not in g[0]:
                return _fail("a generated config whose compression slot lacks the profile is refused: %s" % g)
            (managed / "config.yaml").write_text(_config(PROFILE, PROFILE["profiles"]["m-1"]["request_body"]), encoding="utf-8")
            g = run_control.profile_gaps(root)
            if not g or "auxiliary.compression.extra_body.max_tokens: expected 300, got null" not in g[0]:
                return _fail("an auxiliary slot without the quota output bound is refused (R2): %s" % g)
            (managed / "config.yaml").write_text(_config(PROFILE, AUX), encoding="utf-8")
            (managed / ".env").write_text("MAAS_API_KEY=x\n", encoding="utf-8")
            g = run_control.run_gaps(root)
            if not g or "request pacer is not configured" not in g[0]:
                return _fail("a runtime without the pinned request allowance is refused (R2): %s" % g)
            (managed / ".env").write_text("RHOAI3_REQUEST_BUDGET=200/3600\nRHOAI3_REQUEST_LEDGER=/l/requests.log\n", encoding="utf-8")
            # V15-1: a token-mode profile needs the token settings, and no request ceiling
            tok = json.loads(json.dumps(PROFILE))
            tok["profiles"]["m-1"]["quota"] = {"accounting_mode": "token", "token_allowance_per_window": 51000000,
                                               "reservation_tokens": 262144, "window_seconds": 3600, "max_output_tokens": 300}
            (control / "profile.json").write_text(json.dumps(tok), encoding="utf-8")
            (managed / "model-profile.json").write_text(json.dumps(tok), encoding="utf-8")
            g = run_control.run_gaps(root)
            if not g or "token accounting is not configured" not in g[0] or "RHOAI3_REQUEST_BUDGET=200/3600 is set" not in g[0]:
                return _fail("a token-mode profile with request-mode settings is refused (V15-1): %s" % g)
            (managed / ".env").write_text("RHOAI3_ACCOUNTING_MODE=token\nRHOAI3_TOKEN_BUDGET=51000000/3600\n"
                                          "RHOAI3_TOKEN_RESERVATION=262144\nRHOAI3_REQUEST_LEDGER=/l/requests.log\n", encoding="utf-8")
            g = run_control.run_gaps(root)
            if g:
                return _fail("a token-mode profile with its token settings passes (V15-1): %s" % g)
            (control / "profile.json").unlink()
            for _ in range(2):   # no re-bless: re-reading never recreates a lost pin
                g = run_control.run_gaps(root)
                if not g or "pinned profile" not in g[0]:
                    return _fail("a lost pinned profile stays a refusal: %s" % g)
            if [n for n in dir(run_control) if n.startswith(("record_", "write_", "rebase_"))]:
                return _fail("run_control has no writer for any pin: %s" % [n for n in dir(run_control) if n.startswith(("record_", "write_", "rebase_"))])
            (control / "profile.json").write_text(json.dumps(PROFILE), encoding="utf-8")
            # the contract: missing, empty, malformed, foreign, redirected, whole directory
            cpath = control / "contract.json"
            good = cpath.read_text()
            for label, text, code in (("missing", None, "RUN_CONTROL_MISSING"), ("empty", "", "RUN_CONTROL_MISSING"),
                                      ("malformed", json.dumps({"schema": "x"}), "RUN_CONTROL_MALFORMED"),
                                      ("foreign run", good.replace('"%s"' % run, '"%s-other"' % run), "RUN_ACTIVATION_FOREIGN"),
                                      ("foreign commit", json.dumps(dict(json.loads(good), scaffold_commit="f" * 40)), "RUN_ACTIVATION_FOREIGN")):
                if text is None:
                    cpath.unlink()
                else:
                    cpath.write_text(text, encoding="utf-8")
                for name, gaps in (("activation", pins_mod.activation_gaps(pins_mod.load_pins(root), BUNDLE)),
                                   ("run gaps", run_control.run_gaps(root))):
                    if not gaps or not gaps[0].startswith(code):
                        return _fail("a %s contract refuses (%s, %s): %s" % (label, name, run, gaps))
                cpath.write_text(good, encoding="utf-8")
            os.environ["RHOAI3_RUN_CONTROL_DIR"] = str(control)
            control.rename(td / "moved")
            gaps = run_control.run_gaps(root)
            os.environ.pop("RHOAI3_RUN_CONTROL_DIR", None)
            if not gaps or not gaps[0].startswith("RUN_CONTROL_MISSING"):
                return _fail("a missing control directory refuses, and no environment variable redirects it: %s" % gaps)
            (td / "moved").rename(control)
        finally:
            os.environ.pop("HERMES_MANAGED_DIR", None)
    # a genuine legacy run: declared without run control, pins.json answers
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "legacy"
        (root / ".hermes").mkdir(parents=True)
        (root / ".hermes/pins.json").write_text(json.dumps({"pins": {"planner": {"activation": "activated"}}}), encoding="utf-8")
        (root / "run-budget.json").write_text(json.dumps({"schema": "rhoai3.run-budget/v2", "run_id": run}), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "legacy scaffold")
        if run_control.in_use(root) or run_control.run_gaps(root) or run_control.runtime_gaps(root, Path(d) / "absent") or pins_mod.planner_activation(pins_mod.load_pins(root)) != "activated":
            return _fail("a legacy run keeps pins.json and has no run-control gaps (%s)" % run)
    return 0


def _runtime_case(run: str) -> int:
    with tempfile.TemporaryDirectory() as d:
        td = Path(d)
        root, _control, _state, _managed = _governed(td, run)
        stamp = td / "080.pins"
        tree = "4" * 40
        pins = json.loads((root / ".hermes/pins.json").read_text())
        if run_control.runtime_gaps(root, stamp)[0].split(":")[0] != "HERMES_RUNTIME_UNPINNED":
            return _fail("a governed harness without a runtime pin refuses")
        pins["pins"]["hermes_agent"] = {"patched_tree": tree}
        (root / ".hermes/pins.json").write_text(json.dumps(pins), encoding="utf-8")
        for body in (None, "hermes=v0.20.5\n", "hermes.patched_tree=%s\n" % ("5" * 40)):
            if body is not None:
                stamp.write_text(body, encoding="utf-8")
            g = run_control.runtime_gaps(root, stamp)
            if not g or not g[0].startswith("HERMES_RUNTIME_UNPATCHED"):
                return _fail("a missing stamp, an unpatched image and another tree refuse: %r -> %s" % (body, g))
        stamp.write_text("hermes=v0.20.5\nhermes.patched_tree=%s\n" % tree, encoding="utf-8")
        if run_control.runtime_gaps(root, stamp):
            return _fail("the pinned patched tree is accepted: %s" % run_control.runtime_gaps(root, stamp))
    return 0


def main() -> int:
    if _runtime_case("spring-petclinic-rest-legacy-v13") or _runtime_case("orders-service-v2"):
        return 1
    if _case("spring-petclinic-rest-legacy-v13") or _case("orders-service-v2"):
        return 1
    print("OK: run_control (a governed run is authorized only by the platform's read-only contract -- checkout, reset, "
          "stash and forged pins change nothing; missing, empty, malformed, foreign, moved and env-redirected records "
          "refuse; the M1 binding is write-once; harness drift refuses until a recorded rebase; a runtime profile or "
          "generated config that differs from the pinned profile refuses, digests recomputed from content; nothing "
          "re-blesses a lost pin; an image without the pinned patched Hermes tree refuses; a legacy run keeps pins.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
