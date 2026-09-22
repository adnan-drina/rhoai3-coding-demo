#!/usr/bin/env python3
"""capture-source-oracles selftest with a local stub HTTP server.

- HTTP capture from the "source"; parity PASS against an identical "destination"; FAIL against a diverging one
- non-HTTP capture from an observation file; parity PASS / FAIL on normalized observations
- missing oracle → INCONCLUSIVE; parity receipt refuses until every entry point passes
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
from planner import pipeline, specimens  # noqa: E402
from planner.canonical import digest, load_json, write_canonical  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import slug  # noqa: E402

CAPTURE = HERE / "capture-source-oracles.py"
COMPARE = HERE / "compare-runtime-parity.py"
RECEIPT = HERE / "compose-parity-receipt.py"
COMPARE_SCENARIO = HERE / "compare-scenario-parity.py"
QUALIFY_CAPTURES = HERE / "qualify-source-captures.py"


class Stub(BaseHTTPRequestHandler):
    payloads: dict[str, object] = {}

    def do_GET(self):  # noqa: N802
        body = json.dumps(self.payloads.get(self.path, {"path": self.path})).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


def serve(payloads: dict[str, object]) -> tuple[HTTPServer, str]:
    handler = type("H", (Stub,), {"payloads": payloads})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True)


# --------------------------------------------------------------------------
# the security mode of a capture (ADR-014)
# --------------------------------------------------------------------------
class Guarded(BaseHTTPRequestHandler):
    """A source that answers only an authenticated read -- the enabled mode's
    behaviour, which is what makes it a different capture from the disabled
    one's."""

    expected = ""

    def do_GET(self):  # noqa: N802
        if self.headers.get("Authorization") != type(self).expected:
            body = b'{"error":"unauthorized"}'
            self.send_response(401)
        else:
            body = b'{"owners":[]}'
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


# Every key the capture receipt and a scenario capture carried BEFORE modes
# were bound. The disabled mode must still produce exactly these, so the
# regression control is "what is left after removing the new keys", not a
# reading of the new code.
_LEGACY_RECEIPT_KEYS = {"schema", "producer", "at", "status", "reason", "evidence_bundle_sha256", "corpus_sha256",
                        "receipt_sha256", "receipt_note", "captured", "requested", "scenarios", "reads", "source"}
_LEGACY_CAPTURE_KEYS = {"schema", "scenario", "entry_point", "receipt_sha256", "evidence_bundle_sha256", "corpus_sha256",
                        "source", "initial_state", "normalization", "asserted_headers_extra", "reset_before", "status",
                        "reason", "request", "response", "before", "effects"}
_NEW_RECEIPT_KEYS = {"security_mode", "security_variant", "fixture", "source_config", "credential_refs", "reads_note"}
_NEW_CAPTURE_KEYS = {"security_mode", "security_variant", "asserted_headers_scenario"}


def _load_producer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("capture_scenarios_mode", HERE / "capture-source-scenarios.py")
    producer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(producer)
    return producer


SWITCH_KEY = "acme.security.enable"
SWITCH_ON = "enabled"
SWITCH_OFF = "disabled"


def _decided_security(refs: list[str], invalid: str = "") -> dict:
    """A ``decisions.yaml`` security section: the source's own switch by KEY,
    and each identity by the NAME of the variable holding its credential."""
    sec: dict = {
        "adr": "ADR-001",
        "switch": {"key": SWITCH_KEY, "disabled_value": SWITCH_OFF, "enabled_value": SWITCH_ON},
        "identities": [{"name": "identity-%d" % i, "credential_ref": ref} for i, ref in enumerate(refs)],
    }
    if invalid:
        sec["invalid_credential_ref"] = invalid
    return sec


def _mode_root(td: Path, name: str, scenario: dict, security_mode: str = "disabled",
               security: dict | None = None) -> tuple[Path, str]:
    """A tree the scenario producer can run against: admitted, frozen source
    receipt, and a one-scenario corpus OF THAT MODE.

    The corpus is written at the mode's own path, because that is where the
    producer of that mode reads it: an enabled-mode capture replays the
    enabled corpus's probes, never the anonymous requests beside them."""
    from planner.canonical import write_canonical
    from planner.paths import producer_receipt
    from _scenarios import corpus_path
    decisions = specimens.admitted_decisions()
    if security is not None:
        decisions["security"] = security
    root = specimens.build_dest(td / name, specimens.specimen("http"), decisions=decisions)
    specimens.prepare_loop(root)
    pipeline.admit(root)
    frozen = root / "frozen"
    frozen.mkdir(exist_ok=True)
    (frozen / "pom.xml").write_text("<project/>", encoding="utf-8")
    write_canonical(producer_receipt(root, "freeze"), {"analysis_copy": str(frozen), "source_digest": "fixture"})
    ep = sorted(str(e["id"]) for e in load_json(root / "evidence" / "planning" / "evidence-bundle.json")["entry_points"])[0]
    sc = dict(scenario, entry_point=ep)
    write_canonical(root / corpus_path(security_mode), {
        "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
        "initial_state": {"reset": "restart the service", "dataset": "seeded"}, "scenarios": [sc]})
    return root, ep


def _fake_runtime(base_url: str):
    """The producer's runtime, without maven and a JVM: it records the
    configuration it was constructed with and answers at ``base_url``."""
    class FakeRuntime:
        instances: list = []

        def __init__(self, copy, port, base_path, timeout, java, mvn, log_dir, source_config=None):
            self.source_config = dict(source_config or {})
            self.base_url = base_url
            self.jar = Path("fixture.jar")
            self.starts = 0
            FakeRuntime.instances.append(self)

        def start(self) -> str:
            self.starts += 1
            return ""

        def stop(self) -> None:
            return None

    FakeRuntime.instances = []
    return FakeRuntime


def _all_bytes(where: Path) -> bytes:
    out = b""
    for p in sorted(where.rglob("*")):
        if p.is_file():
            out += p.read_bytes()
    return out


def _security_mode_capture_case() -> int:
    """The enabled-mode capture: a credential by REFERENCE, a recorded mode,
    and a directory of its own.

    ADR-014 requires the frozen source to be captured separately with its
    security switch disabled and enabled, with mode identity preventing
    cross-mode reuse, and evidence that stores credential REFERENCES and never
    a password or an Authorization value. v9's captures had neither: taken at
    the source's default setting, carrying no mode at all. The controls are
    that the capture authenticates (the stub answers 401 without it), that the
    secret appears NOWHERE in the tree it wrote, that a credential passed as
    configuration is refused before the source starts, and that the disabled
    mode's paths and records are what they were."""
    import base64
    import contextlib
    import io
    import os
    from unittest.mock import patch
    from planner.canonical import canonical_bytes, load_json as _load, sha256_bytes
    from _scenarios import request_of, scenario_oracles_dir, scenario_slug

    producer = _load_producer()
    secret = "sup3r-s3cret-passw0rd"
    user = "an-identity-the-policy-allows"
    ref = "TEST_SOURCE_CREDENTIAL"
    token = base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    guarded = type("G", (Guarded,), {"expected": "Basic %s" % token})
    srv = HTTPServer(("127.0.0.1", 0), guarded)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base_url = "http://127.0.0.1:%d" % srv.server_address[1]
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    try:
        with tempfile.TemporaryDirectory(prefix="secmode-capture-") as tmp:
            t = Path(tmp).resolve()
            authenticated = {"id": "sc:read-owners", "method": "GET", "path": "/api/owners", "body_absent": True,
                             "reset_before": False, "effects": [], "normalization": [],
                             "identity": {"kind": "basic", "credential_ref": ref}}
            root, ep = _mode_root(t, "enabled", authenticated, "enabled")
            fake = _fake_runtime(base_url)
            with patch.object(producer, "SourceRuntime", fake):
                # no --no-reads: the enabled mode skips the reads on its own,
                # because the read oracles are not mode-scoped
                rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                    "--source-config", "acme.security.enable=true",
                                    "--credential-ref", ref])
            if rc != 0:
                return _fail("an enabled-mode capture with a declared credential must capture: rc=%s" % rc)
            if not fake.instances or fake.instances[0].source_config != {"acme.security.enable": "true"}:
                return _fail("the source is started with the configuration the caller named: %s"
                             % (fake.instances[0].source_config if fake.instances else None))
            # ... and the real runtime hands it to the process it starts,
            # through both channels it already configures the source with
            started: list = []
            real = producer.SourceRuntime(root, 9966, "", 1, "java", "mvn", root, source_config={"acme.security.enable": "true"})
            real.jar = Path("app.jar")
            with patch.object(producer.subprocess, "Popen", lambda argv, **kw: started.append(argv) or type("P", (), {"poll": lambda self: None, "pid": 0})()):
                with patch.object(producer, "_wait_ready", lambda *a, **k: (True, "")):
                    real.start()
            argv = started[0] if started else []
            if "-Dacme.security.enable=true" not in argv or "--acme.security.enable=true" not in argv:
                return _fail("the runtime starts the source with the named configuration: %s" % argv)
            out = root / scenario_oracles_dir("enabled") / (scenario_slug("sc:read-owners") + ".json")
            if not out.is_file():
                return _fail("the enabled mode writes into its own directory: %s" % scenario_oracles_dir("enabled"))
            if (root / scenario_oracles_dir("disabled")).exists():
                return _fail("an enabled-mode capture writes nothing into the disabled mode's directory")
            cap = _load(out)
            if cap["status"] != "CAPTURED" or cap["response"]["status"] != 200:
                return _fail("the capture must be authenticated (the source answers 401 otherwise): %s %s"
                             % (cap["status"], cap.get("response")))
            if cap.get("security_mode") != "enabled":
                return _fail("every capture file says which mode it is of: %s" % cap.get("security_mode"))
            if cap["request"]["identity"] != {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": ref}:
                return _fail("the request records the credential REFERENCE: %s" % cap["request"]["identity"])
            receipt = _load(root / scenario_oracles_dir("enabled") / "_capture.json")
            if (receipt.get("security_mode") != "enabled" or receipt.get("source_config") != {"acme.security.enable": "true"}
                    or receipt.get("credential_refs") != [ref]):
                return _fail("the capture receipt records the mode, the configuration and the references: %s"
                             % {k: receipt.get(k) for k in ("security_mode", "source_config", "credential_refs")})
            if receipt.get("reads") is not False or "not mode-scoped" not in str(receipt.get("reads_note") or ""):
                return _fail("the read oracles are not mode-scoped, so the receipt says they were not captured: %s" % receipt.get("reads_note"))
            # the control ADR-014 names: the secret is not in the evidence
            written = _all_bytes(root / "verification")
            for forbidden, what in ((secret, "the password"), (token, "the Authorization value"), (user, "the account name")):
                if forbidden.encode("utf-8") in written:
                    return _fail("%s was written into the evidence; only the reference may be" % what)
            if ref.encode("utf-8") not in written:
                return _fail("the reference itself must be recorded, or nobody can tell which credential was used")

            # a credential passed as CONFIGURATION would be recorded verbatim
            root2, _ = _mode_root(t, "conflict", authenticated, "enabled")
            errors = io.StringIO()
            with patch.object(producer, "SourceRuntime", side_effect=AssertionError("the source must not start")):
                with contextlib.redirect_stderr(errors):
                    rc = producer.main(["--root", str(root2), "--security-mode", "enabled",
                                        "--source-config", "acme.datasource.password=%s" % secret,
                                        "--credential-ref", ref, "--no-reads"])
            text = errors.getvalue()
            if rc != 1 or "FAIL: SOURCE_SCENARIOS" not in text or "acme.datasource.password" not in text:
                return _fail("a --source-config value equal to a credential must refuse and name the key: rc=%s %s" % (rc, text))
            if secret in text:
                return _fail("the refusal must name the key, never the value")

            # ... and the disabled mode is exactly what it was
            anonymous = {"id": "sc:read-owners", "method": "GET", "path": "/api/owners", "body_absent": True,
                         "reset_before": False, "effects": [], "normalization": []}
            root3, _ = _mode_root(t, "disabled", anonymous)
            with patch.object(producer, "SourceRuntime", _fake_runtime(base_url)):
                rc = producer.main(["--root", str(root3), "--no-reads"])
            legacy_out = root3 / "verification" / "source-oracles" / "scenarios" / (scenario_slug("sc:read-owners") + ".json")
            if rc != 0 or not legacy_out.is_file():
                return _fail("the disabled mode keeps the path it has always had: rc=%s" % rc)
            dcap = _load(legacy_out)
            drec = _load(root3 / "verification" / "source-oracles" / "scenarios" / "_capture.json")
            if set(dcap) - _NEW_CAPTURE_KEYS != _LEGACY_CAPTURE_KEYS:
                return _fail("a disabled-mode capture gained or lost a key: %s" % sorted(set(dcap) - _NEW_CAPTURE_KEYS ^ _LEGACY_CAPTURE_KEYS))
            if set(drec) - _NEW_RECEIPT_KEYS != _LEGACY_RECEIPT_KEYS:
                return _fail("the disabled-mode receipt gained or lost a key: %s" % sorted(set(drec) - _NEW_RECEIPT_KEYS ^ _LEGACY_RECEIPT_KEYS))
            if drec["security_mode"] != "disabled" or drec["source_config"] != {} or drec["credential_refs"] != []:
                return _fail("the default mode is recorded as itself: %s" % {k: drec.get(k) for k in ("security_mode", "source_config", "credential_refs")})
            # the request digest of an identity-less scenario has not moved:
            # recomputed the way it was computed before credential_ref existed
            sc = _load(root3 / "verification" / "scenarios" / "corpus.json")["scenarios"][0]
            before = sha256_bytes(canonical_bytes({
                "method": "GET", "path": "/api/owners", "headers": {},
                "identity": {"kind": "none", "user_env": "", "password_env": ""},
                "body_sha256": "", "body_absent": True}))
            if request_of(root3, sc)["request_sha256"] != before or dcap["request"]["request_sha256"] != before:
                return _fail("adding credential_ref must not move the digest of a scenario that names none")
    finally:
        srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


class GuardedStore(BaseHTTPRequestHandler):
    """A source with its security switch ON, holding a collection: every
    request it cannot authenticate is refused with 401, the authenticated
    ones are answered. A refused DELETE changes nothing -- which is precisely
    what a read-back has to be able to SEE."""

    expected = ""
    owners: list = []
    seen: list = []

    def _answer(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authenticated(self) -> bool:
        type(self).seen.append((self.command, self.path, bool(self.headers.get("Authorization"))))
        return self.headers.get("Authorization") == type(self).expected

    def do_GET(self):  # noqa: N802
        if not self._authenticated():
            return self._answer(401, {"error": "unauthorized"})
        return self._answer(200, list(type(self).owners))

    def do_DELETE(self):  # noqa: N802
        if not self._authenticated():
            return self._answer(401, {"error": "unauthorized"})
        type(self).owners = [o for o in type(self).owners if str(o["id"]) != self.path.rsplit("/", 1)[-1]]
        return self._answer(204, None)

    def log_message(self, *a):  # noqa: D102
        return


def _effects_identity_capture_case() -> int:
    """The read-backs of a REFUSED request are taken as the identity the
    policy accepts.

    v9 (2026-09-15): the capture probed a scenario's effects with that
    scenario's own identity, so the before and after read-backs of an
    anonymous write were two more 401s and the state they were supposed to
    show could not be seen at all. The controls: the anonymous DELETE is
    still anonymous (the source refuses it, and the capture records the
    refusal as the first response), the read-backs beside it answered 200
    because they carried the accepted identity, the capture says by NAME
    which identity that was, and no credential -- nor the header built from
    one -- is anywhere in what it wrote."""
    import base64
    import os
    from unittest.mock import patch
    from planner.canonical import load_json as _load
    from _scenarios import capture_receipt_path, scenario_oracles_dir, scenario_slug

    producer = _load_producer()
    secret, user, ref = "an0ther-s3cret", "an-identity-the-policy-allows", "TEST_EFFECTS_CREDENTIAL"
    token = "Basic %s" % base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    sid = "sc:auth-anonymous-delete-owners-1"
    scenario = {"id": sid, "method": "DELETE", "path": "/api/owners/1", "body_absent": True,
                "reset_before": False, "normalization": [], "identity": {"kind": "none"},
                "effects": [{"id": "eff:owners-after-denied-delete", "method": "GET", "path": "/api/owners"}],
                "effects_identity": {"kind": "basic", "credential_ref": ref},
                "asserted_headers": ["WWW-Authenticate"],
                "qualify": {"intent": "negative", "expect_status_class": "4xx", "after_equals_before": True}}
    handler = type("G", (GuardedStore,), {"expected": token, "owners": [{"id": 1, "lastName": "Franklin"}], "seen": []})
    srv, base_url = _serve_handler(handler)
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    try:
        with tempfile.TemporaryDirectory(prefix="effects-identity-") as tmp:
            t = Path(tmp).resolve()
            root, _ = _mode_root(t, "effects", scenario, "enabled")
            with patch.object(producer, "SourceRuntime", _fake_runtime(base_url)):
                rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                    "--source-config", "%s=%s" % (SWITCH_KEY, SWITCH_ON), "--credential-ref", ref])
            cap = _load(root / scenario_oracles_dir("enabled") / (scenario_slug(sid) + ".json"))
            if rc != 0 or cap["status"] != "CAPTURED":
                return _fail("the capture must complete: rc=%s %s %s" % (rc, cap["status"], cap.get("reason")))
            if cap["response"]["status"] != 401 or cap["request"]["identity"]["kind"] != "none":
                return _fail("the request itself stays the anonymous one the source refuses: %s %s"
                             % (cap["request"]["identity"], cap["response"]["status"]))
            before, after = cap["before"][0], cap["effects"][0]
            if before["status"] != 200 or after["status"] != 200:
                return _fail("the read-backs are taken as an identity the source answers: %s %s" % (before, after))
            if before["body_sha256"] != after["body_sha256"]:
                return _fail("the refused DELETE deleted nothing, and the read-backs show it: %s vs %s"
                             % (before["body_sha256"], after["body_sha256"]))
            if cap.get("effects_identity") != {"kind": "basic", "user_env": "", "password_env": "", "credential_ref": ref}:
                return _fail("the capture records WHOSE read-backs these are, by reference: %s" % cap.get("effects_identity"))
            if ("DELETE", "/api/owners/1", False) not in handler.seen or ("GET", "/api/owners", True) not in handler.seen:
                return _fail("the write went anonymously and the read-backs authenticated: %s" % handler.seen)
            written = _all_bytes(root / "verification")
            for forbidden, what in ((secret, "the password"), (token, "the Authorization value"), (user, "the account name")):
                if forbidden.encode("utf-8") in written:
                    return _fail("%s reached the evidence; only the reference may" % what)
            if ref.encode("utf-8") not in written:
                return _fail("the reference is recorded, or nobody can tell which credential read the state back")
            if _load(root / capture_receipt_path("enabled")).get("credential_refs") != [ref]:
                return _fail("the receipt names the credential this capture was given")

            # a read-back identity this capture was not given is a gap naming
            # the VARIABLE, never a quiet anonymous probe
            root2, _ = _mode_root(t, "effects-undeclared", scenario, "enabled")
            with patch.object(producer, "SourceRuntime", _fake_runtime(base_url)):
                rc = producer.main(["--root", str(root2), "--security-mode", "enabled",
                                    "--credential-ref", "TEST_OTHER_CREDENTIAL"])
            cap2 = _load(root2 / scenario_oracles_dir("enabled") / (scenario_slug(sid) + ".json"))
            if rc != 1 or cap2["status"] != "INCONCLUSIVE" or "read-backs" not in cap2["reason"] or ref not in cap2["reason"]:
                return _fail("an undeclared read-back credential is an INCONCLUSIVE capture naming it: rc=%s %s"
                             % (rc, {k: cap2.get(k) for k in ("status", "reason")}))
            if cap2["before"] or cap2["effects"]:
                return _fail("nothing is probed with a credential this capture was not given: %s" % cap2)
    finally:
        srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


class Challenging(BaseHTTPRequestHandler):
    """A source with its security switch ON, answering an anonymous read the
    way ADR-014's refusal probes expect: a 4xx that SAYS how to authenticate."""

    challenge = 'Basic realm="acme"'

    def do_GET(self):  # noqa: N802
        body = b'{"error":"unauthorized"}'
        self.send_response(401)
        if type(self).challenge:
            self.send_header("WWW-Authenticate", type(self).challenge)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


def _serve_handler(handler) -> tuple[HTTPServer, str]:
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def _challenge_header_case() -> int:
    """A scenario's OWN asserted headers are asserted, recorded and compared.

    The challenge is part of a refusal: a source that answers 401 with
    WWW-Authenticate has stated how to authenticate, and a destination that
    drops it has changed the behaviour a client sees. Until now the capture
    asserted only the headers the source EXPOSES through CORS, so the
    enabled-mode derivation could name a header nobody would ever look at --
    the comparison would have been silent about it, which is the false green
    ADR-014 exists to prevent. The controls: the header is in the capture's
    own asserted set and in its recorded map, a destination that omits it
    FAILs by name, and the switch and credential REFERENCES the capture runs
    with come from the decided file rather than a command line."""
    import os
    from unittest.mock import patch
    from planner.canonical import load_json as _load
    from _scenarios import capture_receipt_path, scenario_oracles_dir, scenario_parity_dir, scenario_slug

    producer = _load_producer()
    ref, sid = "TEST_ENABLED_CREDENTIAL", "sc:auth-anonymous-read-api-owners"
    anonymous = {"id": sid, "method": "GET", "path": "/api/owners", "body_absent": True,
                 "reset_before": False, "effects": [], "normalization": [],
                 "identity": {"kind": "none"}, "asserted_headers": ["WWW-Authenticate"],
                 "qualify": {"intent": "negative", "expect_status_class": "4xx"}}
    kept = os.environ.get(ref)
    os.environ[ref] = "an-identity:a-password"
    src, src_url = _serve_handler(Challenging)
    dest, dest_url = _serve_handler(type("Silent", (Challenging,), {"challenge": ""}))
    try:
        with tempfile.TemporaryDirectory(prefix="challenge-header-") as tmp:
            t = Path(tmp).resolve()
            root, _ = _mode_root(t, "challenge", anonymous, "enabled", security=_decided_security([ref]))
            fake = _fake_runtime(src_url)
            with patch.object(producer, "SourceRuntime", fake):
                rc = producer.main(["--root", str(root), "--security-mode", "enabled"])
            if rc != 0:
                return _fail("an enabled-mode capture with a decided section must capture: rc=%s" % rc)
            # the switch and the references came from the decided file, with
            # no --source-config and no --credential-ref on the command line
            receipt = _load(root / capture_receipt_path("enabled"))
            if receipt.get("source_config") != {SWITCH_KEY: SWITCH_ON} or receipt.get("credential_refs") != [ref]:
                return _fail("the capture starts the source with the DECIDED switch and reads the DECIDED references: %s"
                             % {k: receipt.get(k) for k in ("source_config", "credential_refs")})
            if not fake.instances or fake.instances[0].source_config != {SWITCH_KEY: SWITCH_ON}:
                return _fail("the decided switch reaches the runtime: %s" % (fake.instances[0].source_config if fake.instances else None))
            cap = _load(root / scenario_oracles_dir("enabled") / (scenario_slug(sid) + ".json"))
            if cap["status"] != "CAPTURED" or cap["response"]["status"] != 401:
                return _fail("the enabled source refuses the anonymous read: %s %s" % (cap["status"], cap.get("response")))
            if cap.get("asserted_headers_scenario") != ["WWW-Authenticate"] or "WWW-Authenticate" not in cap["asserted_headers_extra"]:
                return _fail("the capture records the headers THIS scenario asserts, beside the ones the source exposes: %s"
                             % {k: cap.get(k) for k in ("asserted_headers_scenario", "asserted_headers_extra")})
            if cap["response"]["headers"].get("WWW-Authenticate") != Challenging.challenge:
                return _fail("the challenge the source sent is what was recorded: %s" % cap["response"]["headers"])

            # ... and a destination that drops it FAILS, by name
            p = _run([sys.executable, str(COMPARE_SCENARIO), "--root", str(root), "--scenario", sid,
                      "--dest-url", dest_url, "--no-reset", "--security-mode", "enabled"])
            v = _load(root / scenario_parity_dir("enabled") / (scenario_slug(sid) + ".json"))
            if p.returncode != 1 or v["verdict"] != "FAIL" or "header WWW-Authenticate" not in v["reason"]:
                return _fail("a dropped challenge is a diff the comparator names: rc=%s %s" % (p.returncode, v.get("reason")))
            if v["observed"]["headers"].get("WWW-Authenticate") is not None:
                return _fail("the destination's own value is recorded beside the source's: %s" % v["observed"]["headers"])

            # a declared credential this workspace does not hold: nothing is
            # captured, the source is never started, and the receipt names the
            # VARIABLE -- never what it would have held
            root2, _ = _mode_root(t, "no-credential", anonymous, "enabled",
                                  security=_decided_security(["TEST_ABSENT_CREDENTIAL"]))
            with patch.object(producer, "SourceRuntime", side_effect=AssertionError("the source must not start")):
                rc = producer.main(["--root", str(root2), "--security-mode", "enabled"])
            idle = _load(root2 / capture_receipt_path("enabled"))
            if rc != 0 or idle.get("status") != "idle" or "TEST_ABSENT_CREDENTIAL" not in str(idle.get("reason")):
                return _fail("a credential the workspace does not hold is a recorded blocker naming the variable: rc=%s %s"
                             % (rc, {k: idle.get(k) for k in ("status", "reason")}))
            if (root2 / scenario_oracles_dir("enabled") / (scenario_slug(sid) + ".json")).exists():
                return _fail("nothing is captured when the credential is missing")
            # ... and the qualification of that mode says the same thing
            p = _run([sys.executable, str(QUALIFY_CAPTURES), "--root", str(root2), "--security-mode", "enabled"])
            from _scenarios import qualification_path
            q = _load(root2 / qualification_path("enabled"))
            if p.returncode != 0 or q.get("status") != "idle" or q["verdict"] != "INCONCLUSIVE" or q["scenarios"]:
                return _fail("an idle capture is nothing to judge, recorded as such: rc=%s %s" % (p.returncode, q))
    finally:
        for s in (src, dest):
            s.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _candidate_binding_case(root: Path, entry_point: str, dest_url: str) -> int:
    """The READ comparator on the acceptance path (the hole 6cdef368 left).

    A parity obligation whose entry point declares no scenario is a read
    oracle, and run-verify.sh then compares the WHOLE phase for it -- this
    comparator included. That verify rebuilt the work list on the candidate
    first, so the live seal is stale by construction: without a binding this
    comparator refuses every entry point as INCONCLUSIVE, the composer has
    nothing to compose from, and the card can never advance. It fails closed,
    and closed forever.

    So: with the seal stale, sealed mode still refuses (the control), --issued
    measures the candidate and records what it measured, and a card minted
    under another receipt than the one on disk is refused by name."""
    from planner.paths import ADMISSION_RECEIPT, LOOP_ISSUED, VERIFY_RUN, WORKLIST

    sys.path.insert(0, str(HERE))
    from _scenarios import product_tree_digest  # noqa: E402

    out = root / "verification" / "parity" / (slug(entry_point) + ".json")
    kept_wl = (root / WORKLIST).read_bytes()
    try:
        wl = load_json(root / WORKLIST)
        wl["_rebuilt_on_the_candidate"] = True
        write_canonical(root / WORKLIST, wl)
        receipt_digest = load_json(root / ADMISSION_RECEIPT)["receipt_digest"]
        card = "t_222c582a"
        write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "c:parity",
                                             "task_id": card, "attempt": 4, "gate": "parity",
                                             "receipt_sha256": receipt_digest, "items": ["parity:aaaa"]})
        on_tree = product_tree_digest(root)
        write_canonical(root / VERIFY_RUN, {"schema": "rhoai3.verify-run/v1", "mode": "acceptance",
                                            "candidate_sha256": on_tree})
        # the control: the M4 road still asks the seal, and the seal is stale
        p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", entry_point, "--dest-url", dest_url])
        if p.returncode != 1 or "not authoritative" not in p.stderr or load_json(out)["verdict"] != "INCONCLUSIVE":
            return _fail("without the binding the stale seal must refuse, or this control proves nothing: rc=%s %s"
                         % (p.returncode, p.stderr[-300:]))
        # ...and the same comparison, told which card it is for, measures the
        # candidate instead and says what it measured
        p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", entry_point,
                  "--dest-url", dest_url, "--issued", str(root / LOOP_ISSUED)])
        want = {"mode": "candidate", "candidate_sha256": on_tree, "issued_receipt_sha256": receipt_digest, "card": card}
        v = load_json(out)
        if p.returncode != 0 or v["verdict"] != "PASS" or v.get("binding") != want or v["receipt_sha256"] != receipt_digest:
            return _fail("a candidate-bound read comparison must compose a verdict over the stale seal and record what "
                         "it is OF: rc=%s %s %s" % (p.returncode, {k: v.get(k) for k in ("verdict", "binding", "receipt_sha256", "reason")}, p.stderr[-300:]))
        # H10 (dest v9 t_56adcd76): a card minted under another receipt than
        # the one on disk -- admission re-sealed after the mint by a concurrent
        # writer -- is bound to the receipt it was MINTED under; the verdict
        # composes and names that receipt, and the mismatch is noted
        write_canonical(root / LOOP_ISSUED, dict(load_json(root / LOOP_ISSUED), receipt_sha256="0" * 64))
        p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", entry_point,
                  "--dest-url", dest_url, "--issued", str(root / LOOP_ISSUED)])
        v = load_json(out)
        if (p.returncode != 0 or v["verdict"] != "PASS" or v.get("receipt_sha256") != "0" * 64
                or (v.get("binding") or {}).get("issued_receipt_sha256") != "0" * 64):
            return _fail("a card minted under another receipt is bound to THAT receipt and composes: rc=%s %s"
                         % (p.returncode, {k: v.get(k) for k in ("verdict", "reason", "receipt_sha256", "binding")}))
        # and the sealed road is untouched: no flags, no binding to make, the
        # seal is asked again
        (root / LOOP_ISSUED).unlink()
        (root / WORKLIST).write_bytes(kept_wl)
        p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", entry_point, "--dest-url", dest_url])
        v = load_json(out)
        if p.returncode != 0 or v["verdict"] != "PASS" or v.get("binding") != {"mode": "sealed"} or v["receipt_sha256"] != receipt_digest:
            return _fail("with the seal restored and no flags the M4 road is unchanged: rc=%s %s"
                         % (p.returncode, {k: v.get(k) for k in ("verdict", "binding", "receipt_sha256")}))
    finally:
        (root / WORKLIST).write_bytes(kept_wl)
    return 0


# --------------------------------------------------------------------------
# a fixture VARIANT of the source baseline (ADR-014)
# --------------------------------------------------------------------------
class AccountStatus(BaseHTTPRequestHandler):
    """A source whose identity store the running dataset decides.

    It reads the dataset it was started with and answers 401 for a request
    whose identity that dataset DISABLES -- which is the behaviour a capture
    taken against the declared baseline cannot show, because the baseline
    enables it."""

    expected = ""
    dataset = ""
    disabled_marker = ""

    def do_DELETE(self):  # noqa: N802
        return self.do_GET()

    def do_GET(self):  # noqa: N802
        cls = type(self)
        disabled = cls.disabled_marker and cls.disabled_marker in cls.dataset
        if self.headers.get("Authorization") != cls.expected or disabled:
            body, code = b'{"error":"unauthorized"}', 401
            self.send_response(code)
            self.send_header("WWW-Authenticate", 'Basic realm="fixture"')
        else:
            body, code = b'{"owners":[]}', 200
            self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # noqa: D102
        return


VARIANT = "identity-disabled"
DATASET_KEY = "acme.sql.init.data-locations"
DECLARED_DATASET = "src/main/resources/db/acme/populateDB.sql"
DECLARED_SQL = "INSERT INTO accounts VALUES ('an-identity', true);\n"
STATEMENT = "UPDATE accounts SET enabled = false WHERE name = 'an-identity'"


def _variant_fixture(refs: list[str], invalid: str = "") -> dict:
    sec = _decided_security(refs, invalid)
    sec["fixtures"] = [{"name": VARIANT, "intent": "refuse", "scenarios": "auth-allowed",
                        "dataset_config_key": DATASET_KEY, "statements": [STATEMENT]}]
    return sec


def _variant_capture_case() -> int:
    """The variant capture starts the source against a VARIED dataset, and
    records exactly what it varied.

    The architect's exit asks what the source answers for an identity the
    seed enables once it is disabled. The declared dataset cannot show it and
    must not be edited, so the capture builds the variant -- the declared
    dataset, then the fixture's statements -- points the source's own dataset
    configuration KEY at it, and writes the captures under the variant's own
    directory. The controls: the source is started with that key (and the
    statements really reach it, so the stub answers 401), the variant dataset
    is the declared bytes followed by the declared statements, its digest and
    the statements are on the receipt, every capture says which variant it is
    of, and the baseline's own directory is untouched."""
    import base64
    import os
    from unittest.mock import patch
    from planner.canonical import load_json as _load, sha256_file
    from planner.paths import producer_receipt as _producer_receipt
    from _scenarios import corpus_path, scenario_oracles_dir, scenario_slug, variant_dataset_path

    producer = _load_producer()
    secret, user, ref = "an0ther-s3cret", "an-identity", "TEST_VARIANT_CREDENTIAL"
    token = base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    handler = type("A", (AccountStatus,), {"expected": "Basic %s" % token, "dataset": "", "disabled_marker": "enabled = false"})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base_url = "http://127.0.0.1:%d" % srv.server_address[1]
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    try:
        with tempfile.TemporaryDirectory(prefix="variant-capture-") as tmp:
            t = Path(tmp).resolve()
            probe = {"id": "sc:auth-allowed-read-owners", "method": "GET", "path": "/api/owners", "body_absent": True,
                     "reset_before": False, "effects": [], "normalization": [],
                     "identity": {"kind": "basic", "credential_ref": ref}}
            root, ep = _mode_root(t, "variant", probe, "enabled", security=_variant_fixture([ref]))
            # the frozen source carries the DECLARED dataset the statements
            # are applied after, and the variant corpus names it by digest
            copy = Path(_load(_producer_receipt(root, "freeze"))["analysis_copy"])
            declared = copy / DECLARED_DATASET
            declared.parent.mkdir(parents=True, exist_ok=True)
            declared.write_text(DECLARED_SQL, encoding="utf-8")
            varied = dict(probe, id="sc:fixture-%s-auth-allowed-read-owners" % VARIANT, entry_point=ep,
                          security_mode="enabled", security_variant=VARIANT)
            write_canonical(root / corpus_path("enabled", VARIANT), {
                "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                "security_mode": "enabled", "security_variant": VARIANT,
                "initial_state": {"reset": "restart the service", "dataset": "seeded"},
                "fixture": {"name": VARIANT, "intent": "refuse", "scenarios": "auth-allowed",
                            "dataset_config_key": DATASET_KEY, "statements": [STATEMENT],
                            "dataset": {"path": DECLARED_DATASET, "sha256": sha256_file(declared)}},
                "scenarios": [varied]})

            fake = _fake_runtime(base_url)

            class DatasetAware(fake):  # the stub reads what it was started with
                def start(self):
                    location = self.source_config.get(DATASET_KEY, "")
                    p = location[len("file:"):] if location.startswith("file:") else location
                    handler.dataset = Path(p).read_text(encoding="utf-8") if p and Path(p).is_file() else ""
                    return super().start()

            with patch.object(producer, "SourceRuntime", DatasetAware):
                rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                    "--fixture-variant", VARIANT, "--credential-ref", ref])
            if rc != 0:
                return _fail("a declared variant captures: rc=%s" % rc)
            started = DatasetAware.instances[0].source_config if DatasetAware.instances else {}
            dataset_p = root / variant_dataset_path("enabled", VARIANT)
            if started.get(DATASET_KEY) != "file:%s" % dataset_p:
                return _fail("the source is started with its own dataset key pointed at the variant dataset: %s" % started)
            if started.get(SWITCH_KEY) != SWITCH_ON:
                return _fail("the variant is still the enabled mode, started with the decided switch: %s" % started)
            body = dataset_p.read_text(encoding="utf-8")
            if not body.startswith(DECLARED_SQL) or STATEMENT not in body or body.index(STATEMENT) < body.index(DECLARED_SQL):
                return _fail("the variant dataset is the DECLARED dataset and then the statements: %r" % body)
            out = root / scenario_oracles_dir("enabled", VARIANT) / (scenario_slug(varied["id"]) + ".json")
            if not out.is_file():
                return _fail("the variant writes into its own directory: %s" % scenario_oracles_dir("enabled", VARIANT))
            if (root / scenario_oracles_dir("enabled")).exists():
                return _fail("a variant capture writes nothing into the baseline's directory")
            cap = _load(out)
            if cap["status"] != "CAPTURED" or cap["response"]["status"] != 401:
                return _fail("the source answers the disabled identity 401, and that IS the capture: %s %s"
                             % (cap["status"], cap.get("response")))
            if cap.get("security_variant") != VARIANT or cap.get("security_mode") != "enabled":
                return _fail("every capture says which state it is of: %s" % {k: cap.get(k) for k in ("security_mode", "security_variant")})
            receipt = _load(root / scenario_oracles_dir("enabled", VARIANT) / "_capture.json")
            fx = receipt.get("fixture") or {}
            if (receipt.get("security_variant") != VARIANT or fx.get("statements") != [STATEMENT]
                    or fx.get("dataset_config_key") != DATASET_KEY
                    or fx.get("dataset", {}).get("sha256") != sha256_file(dataset_p)
                    or fx.get("declared_dataset", {}).get("path") != DECLARED_DATASET):
                return _fail("the receipt records the variant, its statements verbatim and the dataset it started the source with: %s" % receipt)
            written = _all_bytes(root / "verification")
            for forbidden, what in ((secret, "the password"), (token, "the Authorization value")):
                if forbidden.encode("utf-8") in written:
                    return _fail("%s reached the evidence of a variant capture" % what)

            # the declared dataset the corpus names must be the one on disk
            declared.write_text(DECLARED_SQL + "INSERT INTO accounts VALUES ('another', true);\n", encoding="utf-8")
            import contextlib
            import io
            errors = io.StringIO()
            with patch.object(producer, "SourceRuntime", DatasetAware):
                with contextlib.redirect_stderr(errors):
                    rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                        "--fixture-variant", VARIANT, "--credential-ref", ref])
            if rc != 1 or "was derived against" not in errors.getvalue():
                return _fail("a declared dataset that moved under the corpus refuses: rc=%s %s" % (rc, errors.getvalue()[-300:]))

            # ... and a variant nobody declared captures nothing and says so
            root2, _ = _mode_root(t, "undeclared", probe, "enabled", security=_decided_security([ref]))
            with patch.object(producer, "SourceRuntime", side_effect=AssertionError("the source must not start")):
                rc = producer.main(["--root", str(root2), "--security-mode", "enabled",
                                    "--fixture-variant", VARIANT, "--credential-ref", ref])
            idle = _load(root2 / scenario_oracles_dir("enabled", VARIANT) / "_capture.json")
            if rc != 0 or idle.get("status") != "idle" or "no security fixture named" not in str(idle.get("reason")):
                return _fail("an undeclared variant records the blocker and captures nothing: rc=%s %s" % (rc, idle))
    finally:
        srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _variant_revert_capture_case() -> int:
    """A revert-then-read scenario is captured in two states of the source:
    its read-backs on the DECLARED dataset (where the one identity is
    enabled, so they answer 200 as that identity), then the request on the
    variant dataset (where the same identity is refused). The source's
    database lives in its process, so no revert is applied to it and no after
    read is taken -- the capture says so -- and the next start is the
    variant's again."""
    import base64
    import os
    from unittest.mock import patch
    from planner.canonical import load_json as _load, sha256_file
    from planner.paths import producer_receipt as _producer_receipt
    from _scenarios import corpus_path, scenario_oracles_dir, scenario_slug, variant_dataset_path

    producer = _load_producer()
    secret, user, ref = "r3vert-s3cret", "an-identity", "TEST_REVERT_CREDENTIAL"
    token = base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    handler = type("R", (AccountStatus,), {"expected": "Basic %s" % token, "dataset": "", "disabled_marker": "enabled = false"})
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base_url = "http://127.0.0.1:%d" % srv.server_address[1]
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    try:
        with tempfile.TemporaryDirectory(prefix="variant-revert-capture-") as tmp:
            t = Path(tmp).resolve()
            own = {"kind": "basic", "credential_ref": ref}
            probe = {"id": "sc:fixture-%s-delete-owners" % VARIANT, "method": "DELETE", "path": "/api/owners/1",
                     "body_absent": True, "reset_before": True, "normalization": [], "identity": dict(own),
                     "effects": [{"id": "eff:owners", "method": "GET", "path": "/api/owners", "role": "unchanged_under_refusal"}],
                     "effects_identity": dict(own), "effects_db_scope": {"tables": ["accounts"], "rule": "fixture"},
                     "effects_reader": {"strategy": "revert_then_read", "name": user, "credential_ref": ref}}
            root, ep = _mode_root(t, "revert", dict(probe, id="sc:unused"), "enabled", security=_variant_fixture([ref]))
            copy = Path(_load(_producer_receipt(root, "freeze"))["analysis_copy"])
            declared = copy / DECLARED_DATASET
            declared.parent.mkdir(parents=True, exist_ok=True)
            declared.write_text(DECLARED_SQL, encoding="utf-8")
            varied = dict(probe, entry_point=ep, security_mode="enabled", security_variant=VARIANT)
            # a variant read after it: it resets to the VARIANT, not the baseline the reads above visited
            followed = {"id": "sc:fixture-%s-read-owners" % VARIANT, "entry_point": ep, "method": "GET", "path": "/api/owners",
                        "body_absent": True, "reset_before": True, "normalization": [], "identity": dict(own), "effects": [],
                        "security_mode": "enabled", "security_variant": VARIANT}
            write_canonical(root / corpus_path("enabled", VARIANT), {
                "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                "security_mode": "enabled", "security_variant": VARIANT,
                "initial_state": {"reset": "restart the service", "dataset": "seeded"},
                "fixture": {"name": VARIANT, "intent": "refuse", "scenarios": "auth-allowed",
                            "dataset_config_key": DATASET_KEY, "statements": [STATEMENT],
                            "dataset": {"path": DECLARED_DATASET, "sha256": sha256_file(declared)}},
                "scenarios": [varied, followed]})
            fake = _fake_runtime(base_url)
            loaded: list = []

            class DatasetAware(fake):
                def start(self):
                    location = self.source_config.get(DATASET_KEY, "")
                    path = location[len("file:"):] if location.startswith("file:") else location
                    loaded.append(path)
                    handler.dataset = Path(path).read_text(encoding="utf-8") if path and Path(path).is_file() else ""
                    return super().start()

            with patch.object(producer, "SourceRuntime", DatasetAware):
                rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                    "--fixture-variant", VARIANT, "--credential-ref", ref, "--no-reads"])
            if rc != 0:
                return _fail("a revert-then-read scenario captures: rc=%s" % rc)
            dataset_p = str(root / variant_dataset_path("enabled", VARIANT))
            if loaded != [dataset_p, str(declared), dataset_p, dataset_p]:
                return _fail("the source is started on the variant, then the declared baseline for the reads, then the "
                             "variant for the request, and the following variant read is restarted on the variant: %s" % loaded)
            nxt = _load(root / scenario_oracles_dir("enabled", VARIANT) / (scenario_slug(followed["id"]) + ".json"))
            if nxt["response"]["status"] != 401 or nxt.get("reset_before") is not True:
                return _fail("the following variant read is captured on the variant state: %s" % nxt.get("response"))
            cap = _load(root / scenario_oracles_dir("enabled", VARIANT) / (scenario_slug(varied["id"]) + ".json"))
            if cap["status"] != "CAPTURED" or cap["response"]["status"] != 401:
                return _fail("the request is refused on the variant: %s %s" % (cap["status"], cap.get("response")))
            if [(r["id"], r["status"], r.get("role")) for r in cap["before"]] != [("eff:owners", 200, "unchanged_under_refusal")]:
                return _fail("the read-backs are taken on the baseline as the request's own identity: %s" % cap["before"])
            se = cap.get("source_effects") or {}
            if cap["effects"] != [] or se.get("observed") is not False or "no executable revert" not in str(se.get("reason")):
                return _fail("with no store to hold the source's database the effect is recorded NOT observed, with the "
                             "reason, and no after read is taken: %s %s" % (cap["effects"], se))
            if (cap.get("effects_reader") or {}).get("strategy") != "revert_then_read" \
                    or (cap.get("before_dataset") or {}).get("path") != DECLARED_DATASET:
                return _fail("the capture records the strategy and the dataset the reads were taken on: %s" % cap)
            if secret.encode() in _all_bytes(root / "verification") or token.encode() in _all_bytes(root / "verification"):
                return _fail("only the reference travels")
    finally:
        srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _variant_store_capture_case() -> int:
    """The SOURCE's post-request state, observed (ADR-020/021).

    The refused request is sent to a source whose database a store holds.
    The scoped database state is read immediately before the request and
    again after it, before the revert; both observations and their digests
    are retained with the comparison; the post-request snapshot is retained;
    the fixture rows only are reverted; the HTTP reads are taken through the
    SAME running source. The counterexample: a handler that answers 401,
    deletes a row anyway, while a warmed cache keeps serving the old body --
    the HTTP read-backs say "unchanged" and qualification still FAILs on the
    database comparison. A revert that finds unexpected state records the
    effect as not observed, with both observations."""
    import base64
    import hashlib
    import os
    from unittest.mock import patch
    from planner.canonical import load_json as _load, sha256_file
    from planner.paths import producer_receipt as _producer_receipt
    from _scenarios import corpus_path, qualification_path, scenario_oracles_dir, scenario_slug
    import _variant_revert as vr

    producer = _load_producer()
    secret, user, ref = "st0re-s3cret", "an-identity", "TEST_STORE_CREDENTIAL"
    token = base64.b64encode(("%s:%s" % (user, secret)).encode("utf-8")).decode("ascii")
    events: list = []
    state: dict = {}

    class Handler(AccountStatus):
        expected = "Basic %s" % token
        dataset = ""
        disabled_marker = "enabled = false"
        mutates = False

        def do_DELETE(self):  # noqa: N802
            events.append(("request",))
            if type(self).mutates:
                # the handler ran: 401 on the wire, a row gone in the database
                state["owners"] = [r for r in state["owners"] if r != "id=1\tname=one"]
            return self.do_GET()   # 401; and GET keeps answering the cached list

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base_url = "http://127.0.0.1:%d" % srv.server_address[1]
    kept = os.environ.get(ref)
    os.environ[ref] = "%s:%s" % (user, secret)
    schema = "CREATE TABLE accounts (name VARCHAR(20) PRIMARY KEY, enabled BOOLEAN NOT NULL);\n"
    plan = vr.compute_plan([STATEMENT], DECLARED_SQL, schema, {"path": DECLARED_DATASET, "sha256": "0" * 64})

    class FakeStore:
        spec = {"engine": "fixture-engine", "file": "src/main/resources/application.properties"}
        jar_record = {"name": "engine.jar", "sha256": "e" * 64}
        refuse = False

        def start(self, files):
            events.append(("store-start", [f.name for f in files]))
            Handler.dataset = Path(files[-1]).read_text(encoding="utf-8")
            state.clear()
            state["owners"] = ["id=1\tname=one", "id=2\tname=two"]
            return ""

        def source_overrides(self):
            return {"fixture.datasource.url": "fixture://held"}

        def observe(self, tables, path):
            events.append(("observe", list(tables)))
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = sorted(["%s\t%s" % (t, r) for t in tables for r in state.get(t, [])] + ["%s\t#table" % t for t in tables])
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "rows": sum(len(state.get(t, [])) for t in tables)}, ""

        def snapshot(self, path):
            events.append(("snapshot",))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(Handler.dataset, encoding="utf-8")
            return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}, ""

        def revert(self, got_plan):
            events.append(("revert", list(got_plan["statements"])))
            if type(self).refuse:
                return 3, "REVERT_UNEXPECTED_STATE accounts.enabled: the rows do not hold the variant value false"
            Handler.dataset = Handler.dataset.replace(STATEMENT, "-- reverted")
            return 0, "reverted 1 row group(s)"

        def stop(self):
            events.append(("store-stop",))

    try:
        with tempfile.TemporaryDirectory(prefix="variant-store-capture-") as tmp:
            t = Path(tmp).resolve()
            own = {"kind": "basic", "credential_ref": ref}
            probe = {"id": "sc:fixture-%s-delete-owners" % VARIANT, "method": "DELETE", "path": "/api/owners/1",
                     "body_absent": True, "reset_before": True, "normalization": [], "identity": dict(own),
                     "effects": [{"id": "eff:owners", "method": "GET", "path": "/api/owners", "role": "unchanged_under_refusal"}],
                     "effects_identity": dict(own),
                     "effects_db_scope": {"tables": ["owners"], "rule": "fixture scope"},
                     "effects_reader": {"strategy": "revert_then_read", "name": user, "credential_ref": ref},
                     "qualify": {"intent": "negative", "expect_status_class": "4xx", "before_reads_usable": True,
                                 "after_equals_before": True, "db_unchanged": True}}
            root, ep = _mode_root(t, "store", dict(probe, id="sc:unused"), "enabled", security=_variant_fixture([ref]))
            copy = Path(_load(_producer_receipt(root, "freeze"))["analysis_copy"])
            declared = copy / DECLARED_DATASET
            declared.parent.mkdir(parents=True, exist_ok=True)
            declared.write_text(DECLARED_SQL, encoding="utf-8")
            (declared.parent / "initDB.sql").write_text(schema, encoding="utf-8")
            varied = dict(probe, entry_point=ep, security_mode="enabled", security_variant=VARIANT)
            write_canonical(root / corpus_path("enabled", VARIANT), {
                "schema": "rhoai3.scenario-corpus/v1", "approved_by": "operator:test",
                "security_mode": "enabled", "security_variant": VARIANT,
                "initial_state": {"reset": "restart the service", "dataset": "seeded"},
                "fixture": {"name": VARIANT, "intent": "refuse", "scenarios": "auth-allowed",
                            "dataset_config_key": DATASET_KEY, "statements": [STATEMENT], "revert": plan,
                            "dataset": {"path": DECLARED_DATASET, "sha256": sha256_file(declared)}},
                "scenarios": [varied]})
            fake = _fake_runtime(base_url)

            class Runtime(fake):
                def start(self):
                    held = "fixture.datasource.url" in self.source_config
                    events.append(("source-start", "store" if held else "in-process"))
                    if not held:
                        loc = self.source_config.get(DATASET_KEY, "")
                        path = loc[len("file:"):] if loc.startswith("file:") else loc
                        Handler.dataset = Path(path).read_text(encoding="utf-8") if path and Path(path).is_file() else ""
                    return super().start()

                def stop(self):
                    events.append(("source-stop",))

            out = root / scenario_oracles_dir("enabled", VARIANT) / (scenario_slug(varied["id"]) + ".json")

            def capture() -> tuple[int, dict]:
                events.clear()
                with patch.object(producer, "SourceRuntime", Runtime), \
                        patch.object(producer, "SOURCE_STORE_OPENER", lambda *a, **k: (FakeStore(), "")):
                    rc = producer.main(["--root", str(root), "--security-mode", "enabled",
                                        "--fixture-variant", VARIANT, "--credential-ref", ref, "--no-reads"])
                return rc, _load(out)

            def qualify() -> dict:
                subprocess.run([sys.executable, str(HERE / "qualify-source-captures.py"), "--root", str(root),
                                "--security-mode", "enabled", "--fixture-variant", VARIANT], text=True, capture_output=True)
                return _load(root / qualification_path("enabled", VARIANT))["scenarios"][varied["id"]]

            # (1) the source changed nothing
            rc, cap = capture()
            se = cap.get("source_effects") or {}
            if rc != 0 or cap["status"] != "CAPTURED" or cap["response"]["status"] != 401:
                return _fail("the refused request is captured against the held store: rc=%s %s" % (rc, cap.get("response")))
            order = [e[0] for e in events]
            want = ["store-start", "source-start", "observe", "request", "observe", "snapshot", "revert"]
            got = [k for k in order if k in set(want)]
            if got[got.index("store-start"):got.index("revert") + 1] != want:
                return _fail("store, source, database read, request, database read, snapshot, revert -- in that order: %s" % events)
            if "source-start" in order[order.index("request"):order.index("store-stop")]:
                return _fail("nothing restarts the source between the request and the observations: %s" % events)
            db = se.get("db") or {}
            if (se.get("observed") is not True or db.get("comparison", {}).get("equal") is not True
                    or db.get("scope", {}).get("tables") != ["owners"] or not Path(db["before"]["path"]).is_file()
                    or db["before"]["sha256"] != db["after"]["sha256"] or "definition" not in db["comparison"]
                    or "before" not in db["before"]["taken"] or "before any revert" not in db["after"]["taken"]):
                return _fail("both observations, their digests, the scope and the comparison are retained: %s" % se)
            if [(r["id"], r["status"]) for r in cap["effects"]] != [("eff:owners", 200)]:
                return _fail("the HTTP reads are taken beside the database evidence: %s" % cap["effects"])
            q = qualify()
            if q["capability"] != "PASS" or not any(c["check"] == "db_unchanged" and c["ok"] is True for c in q["checks"]):
                return _fail("an unchanged database qualifies the refusal: %s" % q)

            # (2) the counterexample: 401, a row deleted, the cache serving the old list
            Handler.mutates = True
            rc, cap = capture()
            Handler.mutates = False
            se = cap.get("source_effects") or {}
            diff = (se.get("db") or {}).get("comparison") or {}
            if rc != 0 or se.get("observed") is not True or diff.get("equal") is not False or "owners" not in diff.get("differences", {}):
                return _fail("the database comparison records the mutation the 401 hid: %s" % se)
            cap_before = {r["id"]: r["body_sha256"] for r in cap["before"]}
            if cap_before != {r["id"]: r["body_sha256"] for r in cap["effects"]}:
                return _fail("the fixture's cache must serve the old body, or the counterexample proves nothing")
            q = qualify()
            db_check = [c for c in q["checks"] if c["check"] == "db_unchanged"]
            http_check = [c for c in q["checks"] if c["check"] == "after_equals_before"]
            if (q["capability"] != "FAIL" or not db_check or db_check[0]["ok"] is not False
                    or "the HTTP read-backs say unchanged" not in db_check[0]["detail"]
                    or not http_check or http_check[0]["ok"] is not True):
                return _fail("HTTP says unchanged, the database says changed: the database decides and both are kept: %s" % q)

            # (3) a tampered observation is not evidence
            before_p = Path(cap["source_effects"]["db"]["before"]["path"])
            before_p.write_text(before_p.read_text(encoding="utf-8") + "owners\tid=9\n", encoding="utf-8")
            q = qualify()
            if q["capability"] != "INCONCLUSIVE" or "not the one the capture digested" not in q["reason"]:
                return _fail("an observation edited after capture is unusable: %s" % q)

            # (4) a revert that finds unexpected state
            FakeStore.refuse = True
            rc, cap = capture()
            FakeStore.refuse = False
            se = cap.get("source_effects") or {}
            if (se.get("observed") is not False or "REVERT_UNEXPECTED_STATE" not in se.get("reason", "")
                    or not se.get("snapshot") or not (se.get("db") or {}).get("comparison") or cap["effects"]):
                return _fail("a revert that finds unexpected state is recorded with both observations, not read past: %s" % se)
    finally:
        srv.shutdown()
        if kept is None:
            os.environ.pop(ref, None)
        else:
            os.environ[ref] = kept
    return 0


def _source_store_engine_case() -> int:
    """The store itself, against the real engine when this workspace has it:
    the source's datasource is found in its own configuration, the engine
    jar is the one its artifact ships, and the server-held database is
    initialised, snapshotted and reverted -- a second revert finds the
    baseline, not the variant, and refuses. Without the engine jar or a JDK
    the case says so and measures only the discovery."""
    import shutil
    import zipfile
    import _source_store as ss
    import _variant_revert as vr
    with tempfile.TemporaryDirectory(prefix="source-store-") as tmp:
        t = Path(tmp)
        copy = t / "src-copy"
        res = copy / "src" / "main" / "resources"
        res.mkdir(parents=True)
        spec, why = ss.discover(copy)
        if spec or "SOURCE_STORE_UNKNOWN" not in why:
            return _fail("a source that configures no in-memory datasource names that: %s" % why)
        (res / "application.properties").write_text("acme.profile=x\n", encoding="utf-8")
        (res / "application-x.properties").write_text(
            "acme.ds.url=jdbc:hsqldb:mem:acme\nacme.ds.username=sa \nacme.ds.password=\n", encoding="utf-8")
        spec, why = ss.discover(copy)
        if why or (spec["url_key"], spec["user_key"], spec["user"], spec["engine"]) != ("acme.ds.url", "acme.ds.username", "sa ", "hsqldb"):
            return _fail("the datasource is read from the source's own configuration: %s %s" % (spec, why))
        jars = sorted((Path.home() / ".m2" / "repository" / "org" / "hsqldb" / "hsqldb").glob("*/hsqldb-*.jar"))
        jars = [j for j in jars if "sources" not in j.name and "javadoc" not in j.name]
        if not jars or not shutil.which("javac") or not shutil.which("java"):
            print("  note: no hsqldb engine jar or JDK in this workspace; the store's engine run is not measured here")
            return 0
        artifact = t / "source.jar"
        with zipfile.ZipFile(artifact, "w") as z:
            z.write(jars[-1], "BOOT-INF/lib/%s" % jars[-1].name)
        store, why = ss.open_store(copy, artifact, t / "work")
        if store is None:
            return _fail("a store opens for a configured, shipped engine: %s" % why)
        if store.source_overrides() != {"acme.ds.url": store.url, "acme.ds.username": "sa"}:
            return _fail("the source is pointed at the store through its own keys: %s" % store.source_overrides())
        db = t / "db"
        db.mkdir()
        (db / "initDB.sql").write_text("CREATE TABLE accounts (name VARCHAR(20) PRIMARY KEY, enabled BOOLEAN NOT NULL);\n"
                                       "CREATE TABLE notes (id INTEGER PRIMARY KEY, body VARCHAR(20));\n", encoding="utf-8")
        seed = "INSERT INTO accounts VALUES ('an-identity', true);\nINSERT INTO notes VALUES (1, 'a;b');\n"
        (db / "populateDB.sql").write_text(seed, encoding="utf-8")
        (db / "variant.sql").write_text(seed + STATEMENT + ";\n", encoding="utf-8")
        plan = vr.compute_plan([STATEMENT], seed, (db / "initDB.sql").read_text(), {"path": "db/populateDB.sql"})
        try:
            files = ss.schema_files(db / "populateDB.sql") + [db / "variant.sql"]
            if [f.name for f in files] != ["initDB.sql", "variant.sql"]:
                return _fail("the schema files are found beside the dataset by content: %s" % files)
            err = store.start(files)
            if err:
                return _fail("the store starts and is initialised: %s" % err)
            snap, err = store.snapshot(t / "snap" / "post.script")
            text = Path(snap.get("path", "")).read_text(encoding="utf-8") if snap else ""
            if err or len(snap["sha256"]) != 64 or "ACCOUNTS" not in text.upper():
                return _fail("the post-request snapshot is the engine's own, digested: %s %s" % (snap, err))
            before, err = store.observe(["accounts", "notes"], t / "obs" / "before.rows")
            again, err2 = store.observe(["accounts", "notes"], t / "obs" / "again.rows")
            if err or err2 or before["sha256"] != again["sha256"] or before["rows"] != 2:
                return _fail("two reads of an unchanged scope are the same observation: %s %s %s %s" % (before, again, err, err2))
            if not ss.compare_observations(Path(before["path"]), Path(again["path"]))["equal"]:
                return _fail("an unchanged scope compares equal")
            if "notes\tid=1\tbody=a;b" not in Path(before["path"]).read_text(encoding="utf-8"):
                return _fail("every column of every row is read: %s" % Path(before["path"]).read_text(encoding="utf-8"))
            rc, out = store.revert(plan)
            if rc != 0:
                return _fail("the revert finds the variant state and restores it: %s" % out)
            after, err = store.observe(["accounts", "notes"], t / "obs" / "after.rows")
            cmp_ = ss.compare_observations(Path(before["path"]), Path(after["path"]))
            if err or cmp_["equal"] or list(cmp_["differences"]) != ["accounts"]:
                return _fail("a changed value is a difference in its own table only: %s %s" % (cmp_, err))
            rc, out = store.revert(plan)
            if rc != 3 or "REVERT_UNEXPECTED_STATE" not in out:
                return _fail("a revert that finds the baseline instead of the variant refuses: rc=%s %s" % (rc, out))
        finally:
            store.stop()
    return 0


def main() -> int:
    if _challenge_header_case():
        return 1
    if _security_mode_capture_case():
        return 1
    if _effects_identity_capture_case():
        return 1
    if (_variant_capture_case() or _variant_revert_capture_case() or _variant_store_capture_case()
            or _source_store_engine_case()):
        return 1
    with tempfile.TemporaryDirectory(prefix="oracle-") as tmp:
        t = Path(tmp).resolve()
        root = specimens.build_dest(t / "dest", specimens.specimen("scheduled"), decisions=specimens.admitted_decisions("scheduled"))
        specimens.prepare_loop(root)
        if pipeline.admit(root)["status"] != "ADMITTED":
            return _fail("fixture not admitted: %s" % pipeline.admit(root)["reasons"][:3])
        # add an http specimen too for HTTP parity
        hroot = specimens.build_dest(t / "http", specimens.specimen("http"), decisions=specimens.admitted_decisions("http"))
        specimens.prepare_loop(hroot)
        pipeline.admit(hroot)
        src, src_url = serve({"/api/owners": [{"id": 1, "name": "a"}], "/api/pets": [{"id": 2}], "/api/vets": []})
        same, same_url = serve({"/api/owners": [{"name": "a", "id": 1}], "/api/pets": [{"id": 2}], "/api/vets": []})
        diff, diff_url = serve({"/api/owners": [{"id": 1, "name": "b"}], "/api/pets": [{"id": 2}], "/api/vets": []})
        try:
            p = _run([sys.executable, str(CAPTURE), "--root", str(hroot), "--base-url", src_url])
            if p.returncode != 0:
                return _fail("capture: %s%s" % (p.stdout, p.stderr))
            oracles = list((hroot / "verification" / "source-oracles").glob("*.json"))
            statuses = {load_json(o)["entry_point"]: load_json(o)["status"] for o in oracles}
            get_owner = next(k for k in statuses if "OwnerController#list" in k)
            post_owner = next(k for k in statuses if "OwnerController#create" in k)
            if statuses[get_owner] != "CAPTURED" or statuses[post_owner] != "INCONCLUSIVE":
                return _fail("capture statuses %s" % statuses)
            # a templated path is not a request: without a value it is
            # INCONCLUSIVE, and with one both sides are compared at the same
            # concrete URL (the substitution is recorded in the oracle)
            tspec = json.loads(json.dumps(specimens.specimen("http")))
            for ty in tspec["types"]:
                for m in ty.get("methods") or []:
                    if m.get("name") == "list":
                        for a in m.get("annotations") or []:
                            if a["fqn"].endswith("GetMapping"):
                                a.setdefault("values", {})["value"] = ["/{ownerId}"]
            troot = specimens.build_dest(t / "templated", tspec, decisions=specimens.admitted_decisions("http"))
            specimens.prepare_loop(troot)
            rec_a = pipeline.admit(troot)
            if rec_a["status"] != "ADMITTED":
                return _fail("templated fixture must admit: %s %s" % (rec_a["status"], (rec_a.get("reasons") or [])[:3]))
            tep = next(e["id"] for e in load_json(troot / "evidence" / "planning" / "evidence-bundle.json")["entry_points"]
                       if e.get("http_path", "").endswith("/{ownerId}"))
            oracle_p = troot / "verification" / "source-oracles" / (slug(tep) + ".json")
            _run([sys.executable, str(CAPTURE), "--root", str(troot), "--base-url", src_url, "--entry-point", tep])
            rec = load_json(oracle_p)
            if rec["status"] != "INCONCLUSIVE" or "--path-var ownerId=" not in rec["reason"]:
                return _fail("a templated path with no value must be INCONCLUSIVE and name the variable: %s" % rec)
            _run([sys.executable, str(CAPTURE), "--root", str(troot), "--base-url", src_url, "--entry-point", tep, "--path-var", "ownerId=1"])
            rec = load_json(oracle_p)
            if rec["status"] != "CAPTURED" or rec["oracle"]["path"] != "/api/owners/1" or rec["oracle"]["path_vars"] != {"ownerId": "1"}:
                return _fail("a substituted path must be captured concretely and record what it substituted: %s" % rec)

            # a fresh M1 has no admission receipt: the reads still capture,
            # bound to the frozen source the bundle describes
            import os as _os
            receipt_p = hroot / "evidence" / "planning" / "admission-receipt.json"
            kept = receipt_p.read_bytes()
            receipt_p.unlink()
            pm1 = _run([sys.executable, str(CAPTURE), "--root", str(hroot), "--base-url", src_url, "--any-status"])
            if pm1.returncode != 0:
                return _fail("a read capture before admission must work (M1 precedes M2): %s%s" % (pm1.stdout, pm1.stderr))
            fresh = load_json(hroot / "verification" / "source-oracles" / (slug(get_owner) + ".json"))
            if fresh["status"] != "CAPTURED" or fresh["receipt_sha256"] != "" or not fresh.get("evidence_bundle_sha256"):
                return _fail("a pre-admission capture binds to the bundle, not to a receipt: %s" % {k: fresh[k] for k in ("status", "receipt_sha256", "evidence_bundle_sha256")})
            receipt_p.write_bytes(kept)
            _run([sys.executable, str(CAPTURE), "--root", str(hroot), "--base-url", src_url])

            # parity PASS (key order differs but canonical JSON matches)
            if _run([sys.executable, str(COMPARE), "--root", str(hroot), "--entry-point", get_owner, "--dest-url", same_url]).returncode != 0:
                return _fail("identical destination must PASS")
            p = _run([sys.executable, str(COMPARE), "--root", str(hroot), "--entry-point", get_owner, "--dest-url", diff_url])
            if p.returncode != 1 or "FAIL" not in p.stderr:
                return _fail("diverging destination must FAIL: %s" % p.stderr)
            rec = load_json(hroot / "verification" / "parity" / [f for f in (hroot / "verification" / "parity").glob("*.json") if "list" in f.name][0].name)
            if rec["verdict"] != "FAIL":
                return _fail("parity record must retain FAIL")
            # parity receipt refuses (POST inconclusive + FAIL)
            p = _run([sys.executable, str(RECEIPT), "--root", str(hroot)])
            if p.returncode != 1:
                return _fail("parity receipt must refuse while any entry point is not PASS")
            # non-HTTP: scheduled + messaging observations
            eps = load_json(root / "evidence" / "planning" / "evidence-bundle.json")["entry_points"]
            sched = next(e["id"] for e in eps if e["kind"] == "scheduled")
            msg = next(e["id"] for e in eps if e["kind"] == "messaging")
            obs = t / "sync.log"
            obs.write_text("2026-09-08T10:00:00Z sync started\n2026-09-08T10:00:01Z synced 12 items\n", encoding="utf-8")
            obs2 = t / "orders.log"
            obs2.write_text("12:00:00 order 1 handled\n", encoding="utf-8")
            p = _run([sys.executable, str(CAPTURE), "--root", str(root), "--observation", "%s=%s" % (sched, obs), "--observation", "%s=%s" % (msg, obs2)])
            if p.returncode != 0:
                return _fail("non-http capture: %s" % p.stderr)
            dest_obs = t / "sync-dest.log"
            dest_obs.write_text("2026-09-09T11:22:33Z synced 12 items\n2026-09-09T11:22:32Z sync started\n", encoding="utf-8")
            if _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", sched, "--dest-observation", str(dest_obs)]).returncode != 0:
                return _fail("timestamp-stripped identical observation must PASS")
            dest_obs.write_text("2026-09-09T11:22:33Z synced 11 items\n", encoding="utf-8")
            if _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", sched, "--dest-observation", str(dest_obs)]).returncode != 1:
                return _fail("diverging observation must FAIL")
            p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", msg])
            if p.returncode != 1 or "INCONCLUSIVE" not in p.stderr:
                return _fail("missing destination observation must be INCONCLUSIVE")
            # the oracle is bound to the FROZEN SOURCE, never to the receipt:
            # an oracle from another bundle is INCONCLUSIVE, one with no bundle
            # digest (an older capture) too, and a hand-written expected value
            # cannot be smuggled in under either
            op = next((root / "verification" / "source-oracles").glob("*.json"))
            doc = load_json(op)
            kept_doc = json.dumps(doc)
            doc["evidence_bundle_sha256"] = "0" * 64
            op.write_text(json.dumps(doc), encoding="utf-8")
            p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", doc["entry_point"], "--dest-observation", str(dest_obs)])
            if p.returncode != 1 or "another frozen source" not in p.stderr:
                return _fail("oracle from another bundle must be INCONCLUSIVE: %s" % p.stderr)
            doc.pop("evidence_bundle_sha256")
            op.write_text(json.dumps(doc), encoding="utf-8")
            p = _run([sys.executable, str(COMPARE), "--root", str(root), "--entry-point", doc["entry_point"], "--dest-observation", str(dest_obs)])
            if p.returncode != 1 or "not bound to the frozen source" not in p.stderr:
                return _fail("an oracle with no bundle digest must be INCONCLUSIVE: %s" % p.stderr)
            op.write_text(kept_doc, encoding="utf-8")
            # a capture taken under a NON-AUTHORITATIVE receipt (the work list
            # rebuilt after the seal, as beside the M3 loop on v9) is still
            # CAPTURED, bound to the bundle, and usable once the receipt is
            # authoritative again; the VERDICT stays bound to the receipt
            wl = hroot / "evidence" / "planning" / "worklist.json"
            kept_wl = wl.read_bytes()
            touched = load_json(wl)
            touched["_rebuilt_after_seal"] = True
            wl.write_text(json.dumps(touched), encoding="utf-8")
            p = _run([sys.executable, str(CAPTURE), "--root", str(hroot), "--base-url", src_url, "--entry-point", get_owner])
            if p.returncode != 0 or "not authoritative" in p.stderr:
                return _fail("a stale receipt must not stop the read capture: rc=%s %s" % (p.returncode, p.stderr[-300:]))
            stale = load_json(hroot / "verification" / "source-oracles" / (slug(get_owner) + ".json"))
            bundle_sha = digest(load_json(hroot / "evidence" / "planning" / "evidence-bundle.json"))
            if stale["status"] != "CAPTURED" or stale["receipt_sha256"] != "" or stale["evidence_bundle_sha256"] != bundle_sha:
                return _fail("a capture under a stale receipt is CAPTURED and bound to the bundle only: %s" % {k: stale.get(k) for k in ("status", "receipt_sha256", "evidence_bundle_sha256")})
            wl.write_bytes(kept_wl)
            if _run([sys.executable, str(COMPARE), "--root", str(hroot), "--entry-point", get_owner, "--dest-url", same_url]).returncode != 0:
                return _fail("that capture must be usable once the receipt is authoritative")
            v = load_json(hroot / "verification" / "parity" / (slug(get_owner) + ".json"))
            if v["verdict"] != "PASS" or v["receipt_sha256"] != load_json(hroot / "evidence" / "planning" / "admission-receipt.json")["receipt_digest"]:
                return _fail("the verdict is a destination judgement and stays receipt-bound: %s" % {k: v.get(k) for k in ("verdict", "receipt_sha256")})
            if _candidate_binding_case(hroot, get_owner, same_url):
                return 1
        finally:
            for s in (src, same, diff):
                s.shutdown()
    print("OK: capture-source-oracles (HTTP capture/parity PASS+FAIL; non-idempotent INCONCLUSIVE; non-HTTP observations; bundle binding: an oracle from another bundle or with no bundle digest is INCONCLUSIVE, a capture under a stale receipt is CAPTURED and usable, the verdict stays receipt-bound; parity receipt refuses; "
          "the READ comparator takes the acceptance path's binding too (--issued): over a work list rebuilt on the candidate the sealed road still refuses, the candidate-bound "
          "comparison measures and records the candidate, the receipt the card was minted under and the card, a card minted under another receipt is bound to the receipt it was minted under (H10), and with "
          "the seal restored the unflagged comparison is the sealed M4 road again; "
          "an enabled-mode scenario capture authenticates from a declared credential REFERENCE, records the reference and the mode and "
          "never the password, the Authorization value or the account, writes into its own directory, refuses a --source-config value "
          "equal to a credential by naming the key, and leaves the disabled mode's paths, keys and request digests untouched; "
          "an enabled capture reads the enabled corpus, asserts and records the headers THAT scenario declares beside the ones the "
          "source exposes so a dropped WWW-Authenticate is a named diff, takes the switch and the credential REFERENCES from "
          "decisions.yaml, and records an idle receipt naming the missing VARIABLE -- never its value -- when the workspace does not "
          "hold a declared credential, which the qualification of that mode then reports as nothing to judge; a scenario naming an "
          "effects_identity has its before/after read-backs taken as THAT identity while the request stays the anonymous one the "
          "source refuses -- so a refused write's unchanged state is visible as 200s rather than two more 401s -- the capture "
          "records whose read-backs they are by reference, and a read-back credential this capture was not given is an "
          "INCONCLUSIVE capture naming the variable with nothing probed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
