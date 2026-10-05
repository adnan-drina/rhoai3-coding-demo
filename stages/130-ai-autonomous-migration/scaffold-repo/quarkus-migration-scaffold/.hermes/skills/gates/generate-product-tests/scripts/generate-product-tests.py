#!/usr/bin/env python3
"""Generate the product parity tests from the source captures (ADR-015).

A worker does not author an expected value and does not weaken one. This
producer reads the derived scenario corpus, the M1 source captures and their
qualification, and WRITES the ``@QuarkusTest`` cases that ask the destination
the recorded question and assert the recorded answer. The generated files are
owned by the harness: every one of them is listed in
``evidence/tests/generated-manifest.json`` with its sha256, and ``--check``
refuses when a byte moved.

What the generated case does, and why each part is not negotiable:

  real request      REST Assured sends the recorded method, path, headers and
                    body bytes to the running application. No mocked
                    controller, no mocked repository, no authentication
                    substitute: a test that mocks the thing under test proves
                    the mock.
  real reset        ``@BeforeEach`` runs the declared reset command (the same
                    contract ``capture-source-oracles`` uses) and then PROVES
                    the destination is in the state the source started from,
                    by replaying the capture's own ``before`` read-backs,
                    identity-sequence probes included. No ``@Transactional``:
                    a rolled-back test transaction does not undo an HTTP
                    write, so it cannot stand in for a reset.
  first response    ``redirect().follow(false)``. Following a redirect records
                    the target's answer as the application's and drops the
                    ``Location`` that said where it pointed.
  source values     status, canonical body digest, the asserted response
                    headers and every declared effect's after-state, all from
                    the capture. ``Location`` is compared after mapping the
                    declared SOURCE origin to the destination's, and nothing
                    else -- no path rewriting, no ID normalization, no value
                    read back off the destination.
  exact accounting  one identifiable test method per QUALIFIED scenario,
                    linked to its entry point in the manifest. A scenario that
                    did not qualify produces no test and appears under
                    ``gaps`` with the qualification's own reason. Nothing is
                    silently omitted.

``@QuarkusTest`` execution COMPLEMENTS the packaged-artifact parity gate
(``compare-scenario-parity.py``); it does not replace it. One runs in the test
JVM against the development runtime, the other against the artifact that
ships.

WHERE THE GENERATED TESTS LIVE, and why it is not ``src/test/java``: a
generated case measures PARITY, and parity is measured once, at M4. Under
``src/test/java`` every M3 verify would compile and run these cases, so a
parity finding would enter the loop's own measure -- the tuple that decides
ACCEPTED vs REVERTED -- and revert the step that was being verified for
reasons that have nothing to do with it. So they are written to a dedicated
root, ``src/parity-test/java`` (+ ``src/parity-test/resources``), which Maven
compiles and runs ONLY under the ``m4-parity`` profile this producer writes
into the destination ``pom.xml``. The pre-verdict runner activates that
profile; nothing else does.

  generate-product-tests.py --root <dest> [--out src/parity-test/java]
                            [--resources src/parity-test/resources]
                            [--security-mode disabled|enabled] [--check]

Exit 0 generated (or checked), 1 refused, 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shlex
import sys
from pathlib import Path
from typing import Any

# The corpus model, the request digest and the comparator's header rules are
# IMPORTED from the skill that owns them. A copy here would be a second
# definition of "the same request", which is the defect the corpus exists for.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
_CAPTURE_SCRIPTS = _SCRIPTS.parents[1] / "capture-source-oracles" / "scripts"
if str(_CAPTURE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_SCRIPTS))

# The harness-owned m4-parity block lives in ONE module, because the bootstrap
# writes the same block into the pom it commits and this producer must find it
# byte-identical at M4 (ADR-015).
from parity_pom import (  # noqa: E402
    BOM_MANAGED,
    DEFAULT_OUT,
    DEFAULT_RESOURCES,
    LOOP_TEST_ROOTS,
    POM,
    POM_BEGIN,
    POM_END,
    POM_PLUGIN_ARTIFACT,
    POM_PLUGIN_GROUP,
    POM_PLUGIN_VERSION,
    POM_PROFILE_ID,
    STALE_BLOCK,
    Refuse,
    block_pin_gaps,
    ensure_pom_profile,
    pom_plugin_pin,
    pom_profile_block,
    read_pom_profile,
)

from _oracle_common import (  # noqa: E402
    ASSERTED_RESPONSE_HEADERS,
    LIST_HEADERS,
    ensure_hermes_lib,
    origin_of,
    required_headers,
)
from _scenarios import (  # noqa: E402
    QUALIFICATION,
    SCENARIO_ORACLES,
    CorpusError,
    corpus_digest,
    is_derived,
    load_corpus,
    request_of,
    scenario_slug,
)

ensure_hermes_lib()
from planner.canonical import digest, load_json, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE  # noqa: E402

GENERATOR = "generate-product-tests.py"
GENERATOR_VERSION = "1.2.0"
SCHEMA = "rhoai3.generated-tests/v1"
MANIFEST = Path("evidence") / "tests" / "generated-manifest.json"

CAPTURE_RECEIPT = SCENARIO_ORACLES / "_capture.json"
GENERATED_PACKAGE_LEAF = "generated"
GENERATED_RESOURCE_DIR = "generated"
SUPPORT_CLASS = "ParitySupport"
DEFAULT_RESET_SCRIPT = Path(".hermes") / "skills" / "gates" / "capture-source-oracles" / "scripts" / "reset-parity-db.sh"

# Sent by the transport, not by the application; replaying them is replaying
# the proxy rather than the request. ``Origin`` is NOT one of these: it is
# what makes a cross-origin exchange cross-origin.
HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "transfer-encoding", "upgrade", "content-length", "host", "expect",
})

_JAVA_IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_JAVA_KEYWORDS = frozenset("""abstract assert boolean break byte case catch char class const continue default do
double else enum extends final finally float for goto if implements import instanceof int interface long native new
package private protected public return short static strictfp super switch synchronized this throw throws transient
try void volatile while""".split())


# ---------------------------------------------------------------------------
# reading what binds
# ---------------------------------------------------------------------------

def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(root: Path) -> dict[str, Any]:
    """Every document the generation binds to, or a refusal saying which one
    does not bind. Reading is not judging: nothing here decides a verdict, it
    decides whether there is evidence to generate FROM."""
    try:
        corpus = load_corpus(root)
    except CorpusError as exc:
        raise Refuse(str(exc))
    corpus_sha = corpus_digest(corpus)

    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        raise Refuse("no %s in this tree; the generated tests must name the frozen source they come from" % EVIDENCE_BUNDLE)
    bundle_sha = digest(load_json(bundle_p))

    cap_p = root / CAPTURE_RECEIPT
    if not cap_p.is_file():
        raise Refuse("no capture receipt %s; the source was never asked these requests (capture-source-scenarios.py)" % CAPTURE_RECEIPT)
    capture_receipt = load_json(cap_p)
    if str(capture_receipt.get("corpus_sha256") or "") != corpus_sha:
        raise Refuse("%s records corpus %s, this tree's corpus is %s; re-capture the source rather than generating across corpora"
                     % (CAPTURE_RECEIPT, str(capture_receipt.get("corpus_sha256") or "")[:12] or "<none>", corpus_sha[:12]))
    if str(capture_receipt.get("evidence_bundle_sha256") or "") != bundle_sha:
        raise Refuse("%s was captured against evidence bundle %s, this tree's bundle is %s; the captures describe another frozen source"
                     % (CAPTURE_RECEIPT, str(capture_receipt.get("evidence_bundle_sha256") or "")[:12] or "<none>", bundle_sha[:12]))

    q_p = root / QUALIFICATION
    if not q_p.is_file():
        raise Refuse("no %s; a capture nobody judged is a capability nobody demonstrated (qualify-source-captures.py)" % QUALIFICATION)
    qualification = load_json(q_p)
    if str(qualification.get("corpus_sha256") or "") != corpus_sha:
        raise Refuse("%s judged corpus %s, this tree's corpus is %s; requalify the captures"
                     % (QUALIFICATION, str(qualification.get("corpus_sha256") or "")[:12] or "<none>", corpus_sha[:12]))
    if str(qualification.get("evidence_bundle_sha256") or "") != bundle_sha:
        raise Refuse("%s judged captures of evidence bundle %s, this tree's bundle is %s; requalify the captures"
                     % (QUALIFICATION, str(qualification.get("evidence_bundle_sha256") or "")[:12] or "<none>", bundle_sha[:12]))

    records = qualification.get("scenarios")
    if not isinstance(records, dict):
        raise Refuse("%s records no per-scenario result" % QUALIFICATION)

    captures: dict[str, dict[str, Any]] = {}
    for sc in corpus.get("scenarios") or []:
        sid = str(sc["id"])
        p = root / SCENARIO_ORACLES / (scenario_slug(sid) + ".json")
        rec = records.get(sid)
        on_disk = _sha_file(p) if p.is_file() else ""
        bound = str((rec or {}).get("capture_sha256") or "")
        if rec is not None and (bound or on_disk) and bound != on_disk:
            raise Refuse("the qualification of %s judged capture %s and the capture on disk is %s; requalify after recapture"
                         % (sid, bound[:12] or "<none>", on_disk[:12] or "<absent>"))
        if p.is_file():
            captures[sid] = load_json(p)

    return {
        "corpus": corpus, "corpus_sha256": corpus_sha,
        "corpus_provenance": "derived" if is_derived(corpus) else "authored",
        "evidence_bundle_sha256": bundle_sha,
        "capture_receipt": capture_receipt,
        "source_digest": str((capture_receipt.get("source") or {}).get("analysis_copy_digest") or ""),
        "qualification": qualification,
        "qualification_sha256": _sha_file(q_p),
        "records": records,
        "captures": captures,
    }


def reset_contract(root: Path, corpus: dict[str, Any], reset_cmd: str) -> dict[str, Any]:
    """The reset the generated tests run, and what it is declared to prove.

    The default is the script ``capture-source-oracles`` restores the source
    with, invoked from the product root exactly as ``compare-scenario-parity``
    invokes it. A tree that does not carry it refuses rather than generating a
    ``@BeforeEach`` that silently does nothing."""
    if reset_cmd.strip():
        argv = shlex.split(reset_cmd)
    else:
        script = root / DEFAULT_RESET_SCRIPT
        if not script.is_file():
            raise Refuse("the reset contract %s is not in this tree and --reset-cmd names none; a generated test that cannot "
                         "restore the recorded initial state would assert against whatever state it found" % DEFAULT_RESET_SCRIPT)
        argv = ["bash", DEFAULT_RESET_SCRIPT.as_posix(), "--root", "."]
    initial = corpus.get("initial_state") or {}
    declared = [str(x) for x in (initial.get("identity_sequences") or []) if str(x).strip()]
    return {
        "command": argv,
        "source": DEFAULT_RESET_SCRIPT.as_posix() if not reset_cmd.strip() else "--reset-cmd",
        "initial_state": {k: str(v) for k, v in sorted(initial.items()) if isinstance(v, (str, int, float, bool))},
        "identity_sequences": sorted(declared),
        "identity_sequences_note": ("" if declared else
                                    "the reset contract declares no identity sequence; the capture's own before read-backs "
                                    "are the only recorded initial state, and they are all verified"),
        "transactional": False,
    }


# ---------------------------------------------------------------------------
# what a qualified scenario becomes
# ---------------------------------------------------------------------------

def declaring_type(entry_point: str) -> str:
    """The fully qualified type that declares the entry point, from its id
    (``ep:<fqn>#<member>:<kind>`` or ``ep:<fqn>:<kind>``)."""
    s = str(entry_point or "")
    if not s.startswith("ep:"):
        return ""
    rest = s[3:]
    if "#" in rest:
        return rest.split("#", 1)[0].strip()
    return rest.rsplit(":", 1)[0].strip() if ":" in rest else rest.strip()


def java_name_ok(name: str) -> bool:
    return bool(_JAVA_IDENT.match(name)) and name not in _JAVA_KEYWORDS


def split_type(fqn: str) -> tuple[str, str]:
    """(package, simple name); ("", "") when it is not a usable Java type."""
    if not fqn or "." not in fqn:
        return "", ""
    pkg, _, simple = fqn.rpartition(".")
    segments = pkg.split(".")
    if not all(java_name_ok(s) for s in segments) or not java_name_ok(simple):
        return "", ""
    return pkg, simple


def method_name(scenario_id: str) -> str:
    return "parity_" + re.sub(r"[^A-Za-z0-9]+", "_", str(scenario_id)).strip("_")


def common_package(packages: list[str]) -> str:
    """The longest package prefix every generated test shares, which is where
    the one shared support class lives. Deterministic and specimen-agnostic:
    it is read off the entry points, never named in this file."""
    if not packages:
        return ""
    parts = [p.split(".") for p in sorted(set(packages))]
    out: list[str] = []
    for i in range(min(len(p) for p in parts)):
        seg = parts[0][i]
        if all(p[i] == seg for p in parts):
            out.append(seg)
        else:
            break
    return ".".join(out) or sorted(set(packages))[0]


def plan_cases(root: Path, inputs: dict[str, Any], security_mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(cases, gaps). Every scenario the corpus names lands in exactly one of
    them: a qualified capability becomes a case, anything else becomes a gap
    carrying the reason somebody else recorded."""
    cases: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    records = inputs["records"]
    captures = inputs["captures"]
    for sc in sorted(inputs["corpus"].get("scenarios") or [], key=lambda s: str(s["id"])):
        sid = str(sc["id"])
        rec = records.get(sid) or {}
        capability = str(rec.get("capability") or "")
        entry_point = str(sc.get("entry_point") or "")

        def gap(reason: str, kind: str) -> None:
            gaps.append({"scenario": sid, "entry_point": entry_point, "capability": capability or "UNJUDGED",
                         "intent": str(rec.get("intent") or ""), "kind": kind, "reason": reason})

        if not rec:
            gap("no qualification record; a capability nobody judged is a capability nobody demonstrated", "unqualified")
            continue
        if capability != "PASS":
            gap(str(rec.get("reason") or "") or ("qualification %s" % capability), "unqualified")
            continue
        cap = captures.get(sid)
        if cap is None:
            gap("no source capture on disk for a qualified scenario", "uncaptured")
            continue
        if str(cap.get("status")) != "CAPTURED":
            gap("the source capture is %s: %s" % (cap.get("status"), cap.get("reason") or ""), "uncaptured")
            continue
        pkg, simple = split_type(declaring_type(entry_point))
        if not pkg:
            gap("the scenario names no entry point whose declaring type is a Java type (%r), so a case cannot be linked to one"
                % entry_point, "unbound-entry-point")
            continue
        try:
            req = request_of(root, sc)
        except CorpusError as exc:
            gap(str(exc), "unbound-request")
            continue
        recorded_req = cap.get("request") or {}
        if str(recorded_req.get("request_sha256") or "") != req["request_sha256"]:
            gap("the request this corpus describes (%s) is not the one the source answered (%s); the generated call would not be a replay"
                % (req["request_sha256"][:12], str(recorded_req.get("request_sha256") or "")[:12] or "<none>"), "unbound-request")
            continue
        response = cap.get("response") or {}
        status = response.get("status")
        if not isinstance(status, int) or not status:
            gap("the capture records no response status to assert", "uncaptured")
            continue
        headers = response.get("headers")
        needed = required_headers(req["method"], status, req["headers"])
        if needed and not isinstance(headers, dict):
            gap("this exchange requires %s and the capture recorded no header map; re-capture the source (redirects not followed)"
                % ", ".join(needed), "uncaptured")
            continue
        identity = req["identity"]
        ident_kind = str(identity.get("kind") or "none")
        if ident_kind not in ("", "none") and security_mode != "enabled":
            gap("the scenario authenticates (identity kind %s) and --security-mode is %s; the generated request would not carry "
                "the credentials the source answered, so it would not be the recorded request" % (ident_kind, security_mode),
                "security-mode")
            continue
        if ident_kind not in ("", "none", "basic"):
            gap("identity kind %r is not one the generated request can carry by reference" % ident_kind, "security-mode")
            continue

        body_resource = ""
        body_sha = ""
        if not req["body_absent"]:
            body_resource = "%s/%s.body" % (GENERATED_RESOURCE_DIR, scenario_slug(sid))
            body_sha = req["body_sha256"]

        send_headers = {k: v for k, v in sorted(req["headers"].items()) if str(k).lower() not in HOP_BY_HOP}
        before = [_probe(row, inputs) for row in (cap.get("before") or [])]
        effects = [_probe(row, inputs) for row in (cap.get("effects") or [])]
        unanswered = [p["id"] for p in before + effects if not isinstance(p["status"], int) or not p["status"]]
        if unanswered:
            gap("the capture recorded no answered status for %s; a read-back nobody took cannot be asserted"
                % ", ".join(sorted(unanswered)), "uncaptured")
            continue
        declared_effects = sorted(str(e.get("id") or e.get("path")) for e in (sc.get("effects") or []))
        if declared_effects != sorted(p["id"] for p in effects):
            gap("the corpus declares effects %s and the capture recorded %s"
                % (declared_effects, sorted(p["id"] for p in effects)), "uncaptured")
            continue
        cases.append({
            "scenario": sid,
            "entry_point": entry_point,
            "declaring_type": declaring_type(entry_point),
            "package": pkg + "." + GENERATED_PACKAGE_LEAF,
            "class": pkg + "." + GENERATED_PACKAGE_LEAF + "." + simple + "ParityTest",
            "simple_class": simple + "ParityTest",
            "method": method_name(sid),
            "http_method": req["method"],
            "path": req["path"],
            "request_headers": send_headers,
            "request_sha256": req["request_sha256"],
            "body_resource": body_resource,
            "body_sha256": body_sha,
            "body_file": str(sc.get("body_file") or ""),
            "status": status,
            "response_body_sha256": str(response.get("body_sha256") or ""),
            "response_body_kind": str(response.get("body_kind") or ""),
            "asserted_headers": _asserted(headers),
            "source_origin": origin_of(str((cap.get("source") or {}).get("base_url") or "")),
            "reset_before": bool(sc.get("reset_before", True)),
            "before": before,
            "effects": effects,
            "intent": str(rec.get("intent") or ""),
            "capture_sha256": str(rec.get("capture_sha256") or ""),
            "credential_references": ([str(identity.get("user_env") or ""), str(identity.get("password_env") or "")]
                                      if ident_kind == "basic" else []),
        })

    # a deterministic, collision-free method name per class
    used: dict[tuple[str, str], int] = {}
    for case in sorted(cases, key=lambda c: c["scenario"]):
        key = (case["class"], case["method"])
        used[key] = used.get(key, 0) + 1
        if used[key] > 1:
            case["method"] = "%s_%d" % (case["method"], used[key])
    return cases, gaps


def _asserted(headers: Any) -> list[dict[str, Any]]:
    """The response headers the capture asserted, in the comparator's own
    order and with its own comparison rule per header. A recorded ``null`` is
    an observation (the source granted no such permission) and is asserted as
    absent, not skipped."""
    if not isinstance(headers, dict):
        return []
    order = list(ASSERTED_RESPONSE_HEADERS) + sorted(k for k in headers if k not in ASSERTED_RESPONSE_HEADERS)
    out: list[dict[str, Any]] = []
    for key in order:
        if key not in headers:
            continue
        value = headers[key]
        rule = "location" if key == "Location" else ("tokens" if key in LIST_HEADERS else "literal")
        out.append({"name": key, "value": None if value is None else str(value), "rule": rule})
    return out


def _probe(row: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    ident = str(row.get("id") or row.get("path") or "")
    declared = set((inputs["corpus"].get("initial_state") or {}).get("identity_sequences") or [])
    return {
        "id": ident,
        "method": str(row.get("method") or "GET"),
        "path": str(row.get("path") or "/"),
        "status": row.get("status"),
        "body_sha256": str(row.get("body_sha256") or ""),
        "identity_sequence": ident in {str(x) for x in declared},
    }


# ---------------------------------------------------------------------------
# Java emission
# ---------------------------------------------------------------------------

def jstr(value: Any) -> str:
    """A Java string literal, or ``null``. ASCII-only so the generated file is
    byte-identical whatever the platform encoding is."""
    if value is None:
        return "null"
    out = ['"']
    for ch in str(value):
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif 0x20 <= code <= 0x7E:
            out.append(ch)
        else:
            raw = ch.encode("utf-16-be")
            for i in range(0, len(raw), 2):
                out.append("\\u%04x" % ((raw[i] << 8) | raw[i + 1]))
    out.append('"')
    return "".join(out)


def _header_comment(corpus_sha: str, subject: str, scenarios: list[str]) -> list[str]:
    lines = [
        "// Generated by %s %s. DO NOT EDIT." % (GENERATOR, GENERATOR_VERSION),
        "// generator_version: %s" % GENERATOR_VERSION,
        "// corpus_sha256: %s" % corpus_sha,
        "// subject: %s" % subject,
    ]
    for sid in scenarios:
        lines.append("// scenario: %s" % sid)
    lines.append("// Expected values come from the M1 source captures (ADR-015). A worker may not")
    lines.append("// weaken them: regenerate with generate-product-tests.py, or record a gap.")
    return lines


_PROBE_ARRAY_EMPTY = "new %s.Probe[0]" % SUPPORT_CLASS


def _probe_literal(p: dict[str, Any]) -> str:
    return "new %s.Probe(%s, %s, %s, %s, %s, %s)" % (
        SUPPORT_CLASS, jstr(p["id"]), jstr(p["method"]), jstr(p["path"]),
        int(p["status"]),
        jstr(p["body_sha256"] or None), "true" if p["identity_sequence"] else "false")


_VERB = {"GET": "get", "POST": "post", "PUT": "put", "PATCH": "patch",
         "DELETE": "delete", "HEAD": "head", "OPTIONS": "options"}


def emit_test_class(cases: list[dict[str, Any]], support_package: str, corpus_sha: str, security_mode: str) -> str:
    """One class per declaring type, one method per qualified scenario."""
    first = cases[0]
    package = first["package"]
    lines = _header_comment(corpus_sha, first["declaring_type"], [c["scenario"] for c in cases])
    lines.append("")
    lines.append("package %s;" % package)
    lines.append("")
    lines.append("import static io.restassured.RestAssured.given;")
    lines.append("")
    imports = ["io.quarkus.test.junit.QuarkusTest", "io.restassured.response.Response",
               "java.util.LinkedHashMap", "java.util.Map", "org.junit.jupiter.api.BeforeEach",
               "org.junit.jupiter.api.Test", "org.junit.jupiter.api.TestInfo"]
    if support_package != package:
        imports.append("%s.%s" % (support_package, SUPPORT_CLASS))
    for fqcn in sorted(imports):
        lines.append("import %s;" % fqcn)
    lines.append("")
    lines.append("@QuarkusTest")
    lines.append("public class %s {" % first["simple_class"])
    lines.append("")
    lines.append("    private static final Map<String, %s.Scenario> SCENARIOS = scenarios();" % SUPPORT_CLASS)
    lines.append("")
    lines.append("    private static Map<String, %s.Scenario> scenarios() {" % SUPPORT_CLASS)
    lines.append("        Map<String, %s.Scenario> declared = new LinkedHashMap<String, %s.Scenario>();" % (SUPPORT_CLASS, SUPPORT_CLASS))
    for case in cases:
        refs = case["credential_references"]
        user = jstr(refs[0]) if refs else "null"
        password = jstr(refs[1]) if refs else "null"
        if case["before"]:
            body = ",".join("\n                " + _probe_literal(p) for p in case["before"])
            probes = "new %s.Probe[] {%s\n            }" % (SUPPORT_CLASS, body)
        else:
            probes = _PROBE_ARRAY_EMPTY
        lines.append("        declared.put(%s, new %s.Scenario(%s, %s, %s, %s, %s));"
                     % (jstr(case["method"]), SUPPORT_CLASS, jstr(case["scenario"]),
                        "true" if case["reset_before"] else "false", user, password, probes))
    lines.append("        return declared;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** The declared reset, then PROOF that the destination is in the state the source started from. */")
    lines.append("    @BeforeEach")
    lines.append("    void restoreRecordedInitialState(TestInfo info) {")
    lines.append("        %s.resetAndVerify(SCENARIOS.get(%s.methodName(info)));" % (SUPPORT_CLASS, SUPPORT_CLASS))
    lines.append("    }")
    for case in cases:
        lines.append("")
        lines.extend("    " + ln for ln in emit_test_method(case, security_mode))
    lines.append("}")
    return "\n".join(lines) + "\n"


def emit_test_method(case: dict[str, Any], security_mode: str) -> list[str]:
    sid = case["scenario"]
    verb = _VERB.get(case["http_method"], "")
    lines = ["// scenario: %s" % sid,
             "// entry point: %s" % case["entry_point"],
             "@Test",
             "void %s() {" % case["method"],
             "    %s.Scenario scenario = SCENARIOS.get(%s);" % (SUPPORT_CLASS, jstr(case["method"])),
             "    Response response = given()",
             "            .redirects().follow(false)"]
    if security_mode == "enabled" and case["credential_references"]:
        user, password = case["credential_references"]
        lines.append("            .auth().preemptive().basic(%s.credential(%s), %s.credential(%s))"
                     % (SUPPORT_CLASS, jstr(user), SUPPORT_CLASS, jstr(password)))
    for name, value in sorted(case["request_headers"].items()):
        lines.append("            .header(%s, %s)" % (jstr(name), jstr(value)))
    if case["body_resource"]:
        lines.append("            .body(%s.body(%s, %s))" % (SUPPORT_CLASS, jstr(case["body_resource"]), jstr(case["body_sha256"])))
    lines.append("        .when()")
    if verb:
        lines.append("            .%s(%s)" % (verb, jstr(case["path"])))
    else:
        lines.append("            .request(%s, %s)" % (jstr(case["http_method"]), jstr(case["path"])))
    lines.append("        .then()")
    lines.append("            .statusCode(%d)" % int(case["status"]))
    lines.append("            .extract().response();")
    if case["response_body_sha256"]:
        lines.append("    %s.assertBody(scenario, response, %s);" % (SUPPORT_CLASS, jstr(case["response_body_sha256"])))
    else:
        lines.append("    // the capture retained no body digest for this response; nothing about the body is asserted")
    for header in case["asserted_headers"]:
        if header["rule"] == "location":
            lines.append("    %s.assertLocation(scenario, response, %s, %s);"
                         % (SUPPORT_CLASS, jstr(header["value"]), jstr(case["source_origin"] or None)))
        elif header["rule"] == "tokens":
            lines.append("    %s.assertHeaderTokens(scenario, response, %s, %s);"
                         % (SUPPORT_CLASS, jstr(header["name"]), jstr(header["value"])))
        else:
            lines.append("    %s.assertHeader(scenario, response, %s, %s);"
                         % (SUPPORT_CLASS, jstr(header["name"]), jstr(header["value"])))
    for probe in case["effects"]:
        lines.append("    %s.assertEffect(scenario, %s);" % (SUPPORT_CLASS, _probe_literal(probe)))
    lines.append("}")
    return lines


def emit_support(package: str, corpus_sha: str, contract: dict[str, Any], security_mode: str, case_count: int) -> str:
    argv = ", ".join(jstr(a) for a in contract["command"])
    header = "\n".join(_header_comment(corpus_sha, "shared parity support for %d case(s)" % case_count, []))
    return SUPPORT_TEMPLATE.replace("@@HEADER@@", header) \
                           .replace("@@PACKAGE@@", package) \
                           .replace("@@CLASS@@", SUPPORT_CLASS) \
                           .replace("@@VERSION@@", GENERATOR_VERSION) \
                           .replace("@@CORPUS@@", corpus_sha) \
                           .replace("@@SECURITY@@", security_mode) \
                           .replace("@@RESET@@", argv)


SUPPORT_TEMPLATE = r"""@@HEADER@@

package @@PACKAGE@@;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.math.BigInteger;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/**
 * Shared machinery for the generated parity tests. Generated, not authored:
 * every expected value lives in the test methods and comes from the M1 source
 * captures.
 *
 * <p>The canonical body form asserted here is the comparator's, restated for
 * the JVM: a response whose bytes parse as JSON is compared by the SHA-256 of
 * <code>json.dumps(value, sort_keys=True, separators=(",", ":"),
 * ensure_ascii=True) + "\n"</code> encoded UTF-8 -- object keys sorted by
 * Unicode code point, no insignificant whitespace, every character above
 * <code>0x7e</code> escaped as a lowercase <code>\\uXXXX</code> unit (astral
 * characters as a surrogate pair), integers rendered exactly and floating
 * point numbers in Python's shortest round-trip repr. Anything that does not
 * parse as JSON is compared by the SHA-256 of its raw bytes. Both are exactly
 * what <code>_oracle_common.normalize_body</code> computes, so a digest
 * recorded from the source and a digest computed here mean the same thing.
 */
public final class @@CLASS@@ {

    public static final String GENERATOR_VERSION = "@@VERSION@@";
    public static final String CORPUS_SHA256 = "@@CORPUS@@";
    public static final String SECURITY_MODE = "@@SECURITY@@";
    /** The declared reset: the same contract capture-source-oracles restores with. */
    public static final String[] RESET_COMMAND = new String[] {@@RESET@@};

    private @@CLASS@@() {
    }

    /** A read-back: what a probe answered, and what it proves. */
    public static final class Probe {
        public final String id;
        public final String method;
        public final String path;
        public final int status;
        public final String bodySha256;
        public final boolean identitySequence;

        public Probe(String id, String method, String path, int status, String bodySha256, boolean identitySequence) {
            this.id = id;
            this.method = method;
            this.path = path;
            this.status = status;
            this.bodySha256 = bodySha256;
            this.identitySequence = identitySequence;
        }
    }

    /** One recorded scenario: how it authenticates and what state it started from. */
    public static final class Scenario {
        public final String id;
        public final boolean resetBefore;
        public final String userReference;
        public final String passwordReference;
        public final Probe[] before;

        public Scenario(String id, boolean resetBefore, String userReference, String passwordReference, Probe[] before) {
            this.id = id;
            this.resetBefore = resetBefore;
            this.userReference = userReference;
            this.passwordReference = passwordReference;
            this.before = before;
        }
    }

    public static String methodName(org.junit.jupiter.api.TestInfo info) {
        if (info == null || info.getTestMethod() == null || !info.getTestMethod().isPresent()) {
            return "";
        }
        return info.getTestMethod().get().getName();
    }

    /**
     * A credential by REFERENCE. The generated sources never carry a secret:
     * the reference names a system property, else an environment variable.
     */
    public static String credential(String reference) {
        String value = System.getProperty(reference);
        if (value == null || value.isEmpty()) {
            value = System.getenv(reference);
        }
        if (value == null || value.isEmpty()) {
            throw new AssertionError("the generated request authenticates by reference and " + reference
                    + " is set neither as a system property nor in the environment");
        }
        return value;
    }

    /** The recorded request body, verified against the digest the corpus bound. */
    public static byte[] body(String resource, String sha256) {
        InputStream in = @@CLASS@@.class.getClassLoader().getResourceAsStream(resource);
        if (in == null) {
            throw new AssertionError("the generated body " + resource + " is not on the test classpath");
        }
        byte[] raw;
        try {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[8192];
            int read;
            while ((read = in.read(chunk)) > 0) {
                buffer.write(chunk, 0, read);
            }
            in.close();
            raw = buffer.toByteArray();
        } catch (java.io.IOException exc) {
            throw new AssertionError("the generated body " + resource + " could not be read: " + exc);
        }
        String have = sha256Hex(raw);
        if (!have.equals(sha256)) {
            throw new AssertionError("the generated body " + resource + " is " + have
                    + ", the corpus bound " + sha256 + "; regenerate rather than editing it");
        }
        return raw;
    }

    /**
     * Restore the declared initial state and PROVE the destination is in it.
     * No test transaction stands in for this: a rollback does not undo an HTTP
     * write, and an effect probe on a mutated database proves nothing.
     */
    public static void resetAndVerify(Scenario scenario) {
        if (scenario == null) {
            throw new AssertionError("no recorded scenario is bound to this test method; regenerate the parity tests");
        }
        if (scenario.resetBefore) {
            runReset(scenario);
        }
        for (Probe probe : scenario.before) {
            Response answered = probe(scenario, probe);
            String what = probe.identitySequence
                    ? "the identity sequence the reset contract declares (" + probe.id + ")"
                    : "the state the source started from (" + probe.id + ")";
            assertProbe(scenario, probe, answered, what);
        }
    }

    private static void runReset(Scenario scenario) {
        try {
            ProcessBuilder builder = new ProcessBuilder(RESET_COMMAND);
            builder.redirectErrorStream(true);
            Process process = builder.start();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int read;
            while ((read = process.getInputStream().read(chunk)) > 0) {
                out.write(chunk, 0, read);
            }
            int rc = process.waitFor();
            if (rc != 0) {
                throw new AssertionError(scenario.id + ": the declared initial state could not be restored ("
                        + String.join(" ", RESET_COMMAND) + " exited " + rc + "): "
                        + out.toString(StandardCharsets.UTF_8.name()));
            }
        } catch (java.io.IOException exc) {
            throw new AssertionError(scenario.id + ": the declared reset could not run: " + exc);
        } catch (InterruptedException exc) {
            Thread.currentThread().interrupt();
            throw new AssertionError(scenario.id + ": the declared reset was interrupted");
        }
    }

    /** The destination ORIGIN: scheme, host and port of RestAssured's base URI. */
    public static String destinationOrigin() {
        String base = RestAssured.baseURI == null ? "" : RestAssured.baseURI;
        int port = RestAssured.port;
        try {
            URI uri = URI.create(base);
            String scheme = uri.getScheme() == null ? "http" : uri.getScheme();
            String host = uri.getHost() == null ? "localhost" : uri.getHost();
            int effective = port > 0 ? port : uri.getPort();
            return effective > 0 ? scheme + "://" + host + ":" + effective : scheme + "://" + host;
        } catch (IllegalArgumentException exc) {
            return "";
        }
    }

    /**
     * Rewrite ONLY the declared source origin to this destination's. The root
     * path (RestAssured's basePath) is deliberately NOT part of an origin and
     * NOT rewritten: the recorded path, escaping, query and fragment are the
     * value's own and are compared as they are, and no identifier is
     * normalized.
     */
    public static String mapOrigin(String value, String sourceOrigin) {
        String destination = destinationOrigin();
        if (value == null || sourceOrigin == null || sourceOrigin.isEmpty() || destination.isEmpty()) {
            return value;
        }
        if (value.equals(sourceOrigin)) {
            return destination;
        }
        for (String separator : new String[] {"/", "?", "#"}) {
            if (value.startsWith(sourceOrigin + separator)) {
                return destination + value.substring(sourceOrigin.length());
            }
        }
        return value;
    }

    public static void assertBody(Scenario scenario, Response response, String expectedSha256) {
        String have = normalizedBodySha256(response);
        if (!have.equals(expectedSha256)) {
            throw new AssertionError(scenario.id + ": body " + have + " vs the source's " + expectedSha256
                    + " (canonical JSON where the body parses as JSON, raw bytes otherwise)");
        }
    }

    public static void assertLocation(Scenario scenario, Response response, String recorded, String sourceOrigin) {
        String expected = mapOrigin(recorded, sourceOrigin);
        String have = response.getHeader("Location");
        if (!equal(have, expected)) {
            throw new AssertionError(scenario.id + ": header Location " + have + " vs " + expected
                    + " (source " + recorded + ", origin-mapped only)");
        }
    }

    public static void assertHeader(Scenario scenario, Response response, String name, String expected) {
        String have = response.getHeader(name);
        if (!equal(have, expected)) {
            throw new AssertionError(scenario.id + ": header " + name + " " + have + " vs " + expected);
        }
    }

    public static void assertHeaderTokens(Scenario scenario, Response response, String name, String expected) {
        String have = response.getHeader(name);
        if (have == null || expected == null) {
            if (!equal(have, expected)) {
                throw new AssertionError(scenario.id + ": header " + name + " " + have + " vs " + expected);
            }
            return;
        }
        if (!tokens(have).equals(tokens(expected))) {
            throw new AssertionError(scenario.id + ": header " + name + " " + have + " vs " + expected
                    + " (compared as a token set)");
        }
    }

    /** The resulting state: an identical response does not prove the write happened. */
    public static void assertEffect(Scenario scenario, Probe effect) {
        Response answered = probe(scenario, effect);
        assertProbe(scenario, effect, answered, "effect " + effect.id);
    }

    private static Response probe(Scenario scenario, Probe probe) {
        io.restassured.specification.RequestSpecification spec = RestAssured.given().redirects().follow(false);
        if (scenario.userReference != null && scenario.passwordReference != null) {
            spec = spec.auth().preemptive().basic(credential(scenario.userReference), credential(scenario.passwordReference));
        }
        io.restassured.specification.RequestSender sender = spec.when();
        String method = probe.method == null ? "GET" : probe.method.toUpperCase(java.util.Locale.ROOT);
        if ("GET".equals(method)) {
            return sender.get(probe.path);
        }
        if ("HEAD".equals(method)) {
            return sender.head(probe.path);
        }
        return sender.request(method, probe.path);
    }

    private static void assertProbe(Scenario scenario, Probe probe, Response answered, String what) {
        int status = answered.getStatusCode();
        String have = normalizedBodySha256(answered);
        if (status != probe.status || !have.equals(probe.bodySha256 == null ? "" : probe.bodySha256)) {
            throw new AssertionError(scenario.id + ": " + what + " answered " + status + "/" + have
                    + ", the source recorded " + probe.status + "/" + probe.bodySha256);
        }
    }

    private static boolean equal(String a, String b) {
        return a == null ? b == null : a.equals(b);
    }

    private static TreeSet<String> tokens(String value) {
        TreeSet<String> out = new TreeSet<String>();
        for (String token : value.split(",")) {
            String trimmed = token.trim().toLowerCase(java.util.Locale.ROOT);
            if (!trimmed.isEmpty()) {
                out.add(trimmed);
            }
        }
        return out;
    }

    // -- the canonical body digest -------------------------------------------------

    public static String normalizedBodySha256(Response response) {
        byte[] raw = response.asByteArray();
        if (raw == null) {
            raw = new byte[0];
        }
        String text = new String(raw, StandardCharsets.UTF_8);
        try {
            Json parser = new Json(text);
            Object value = parser.parse();
            StringBuilder out = new StringBuilder();
            writeCanonical(value, out);
            out.append('\n');
            return sha256Hex(out.toString().getBytes(StandardCharsets.UTF_8));
        } catch (IllegalArgumentException notJson) {
            return sha256Hex(raw);
        }
    }

    private static void writeCanonical(Object value, StringBuilder out) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof Boolean) {
            out.append(((Boolean) value).booleanValue() ? "true" : "false");
        } else if (value instanceof BigInteger) {
            out.append(value.toString());
        } else if (value instanceof Double) {
            out.append(repr(((Double) value).doubleValue()));
        } else if (value instanceof String) {
            writeString((String) value, out);
        } else if (value instanceof List) {
            out.append('[');
            List<?> items = (List<?>) value;
            for (int i = 0; i < items.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                writeCanonical(items.get(i), out);
            }
            out.append(']');
        } else if (value instanceof Map) {
            out.append('{');
            Map<?, ?> entries = (Map<?, ?>) value;
            List<String> keys = new ArrayList<String>();
            for (Object key : entries.keySet()) {
                keys.add(String.valueOf(key));
            }
            java.util.Collections.sort(keys, new java.util.Comparator<String>() {
                public int compare(String a, String b) {
                    int i = 0;
                    while (i < a.length() && i < b.length()) {
                        int ca = a.codePointAt(i);
                        int cb = b.codePointAt(i);
                        if (ca != cb) {
                            return ca < cb ? -1 : 1;
                        }
                        i += Character.charCount(ca);
                    }
                    return a.length() - b.length();
                }
            });
            for (int i = 0; i < keys.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                writeString(keys.get(i), out);
                out.append(':');
                writeCanonical(entries.get(keys.get(i)), out);
            }
            out.append('}');
        } else {
            throw new IllegalArgumentException("not a JSON value: " + value.getClass());
        }
    }

    private static void writeString(String value, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char ch = value.charAt(i);
            if (ch == '"') {
                out.append("\\\"");
            } else if (ch == '\\') {
                out.append("\\\\");
            } else if (ch == '\n') {
                out.append("\\n");
            } else if (ch == '\r') {
                out.append("\\r");
            } else if (ch == '\t') {
                out.append("\\t");
            } else if (ch == '\b') {
                out.append("\\b");
            } else if (ch == '\f') {
                out.append("\\f");
            } else if (ch >= 0x20 && ch <= 0x7e) {
                out.append(ch);
            } else {
                out.append(String.format("\\u%04x", (int) ch));
            }
        }
        out.append('"');
    }

    /**
     * Python's <code>repr</code> of a float: the shortest decimal that reads
     * back to the same double, in positional notation while the decimal point
     * sits within (-4, 16], and exponential otherwise.
     */
    static String repr(double value) {
        if (Double.isNaN(value) || Double.isInfinite(value)) {
            throw new IllegalArgumentException("not a canonical JSON number");
        }
        String sign = (value < 0 || (value == 0.0 && Double.doubleToRawLongBits(value) != 0L)) ? "-" : "";
        String shortest = Double.toString(Math.abs(value));
        int exponent = 0;
        int marker = shortest.indexOf('E');
        if (marker >= 0) {
            exponent = Integer.parseInt(shortest.substring(marker + 1));
            shortest = shortest.substring(0, marker);
        }
        int dot = shortest.indexOf('.');
        String digits = dot < 0 ? shortest : shortest.substring(0, dot) + shortest.substring(dot + 1);
        int decpt = (dot < 0 ? shortest.length() : dot) + exponent;
        int lead = 0;
        while (lead < digits.length() - 1 && digits.charAt(lead) == '0') {
            lead++;
        }
        digits = digits.substring(lead);
        decpt -= lead;
        int end = digits.length();
        while (end > 1 && digits.charAt(end - 1) == '0') {
            end--;
        }
        digits = digits.substring(0, end);
        if ("0".equals(digits)) {
            decpt = 1;
        }
        StringBuilder out = new StringBuilder(sign);
        if (decpt <= -4 || decpt > 16) {
            out.append(digits.charAt(0));
            if (digits.length() > 1) {
                out.append('.').append(digits.substring(1));
            }
            int e = decpt - 1;
            out.append('e').append(e < 0 ? '-' : '+');
            String magnitude = Integer.toString(Math.abs(e));
            if (magnitude.length() < 2) {
                out.append('0');
            }
            out.append(magnitude);
        } else if (decpt <= 0) {
            out.append("0.");
            for (int i = 0; i < -decpt; i++) {
                out.append('0');
            }
            out.append(digits);
        } else if (decpt >= digits.length()) {
            out.append(digits);
            for (int i = digits.length(); i < decpt; i++) {
                out.append('0');
            }
            out.append(".0");
        } else {
            out.append(digits, 0, decpt).append('.').append(digits.substring(decpt));
        }
        return out.toString();
    }

    public static String sha256Hex(byte[] raw) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256").digest(raw);
            StringBuilder out = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                out.append(Character.forDigit((b >> 4) & 0xf, 16)).append(Character.forDigit(b & 0xf, 16));
            }
            return out.toString();
        } catch (java.security.NoSuchAlgorithmException exc) {
            throw new AssertionError("SHA-256 is not available in this JVM");
        }
    }

    /** A strict JSON reader: exactly the grammar json.loads accepts, less its NaN extensions. */
    static final class Json {
        private final String text;
        private int at;

        Json(String text) {
            this.text = text;
        }

        Object parse() {
            skip();
            Object value = value();
            skip();
            if (at != text.length()) {
                throw new IllegalArgumentException("trailing content at " + at);
            }
            return value;
        }

        private void skip() {
            while (at < text.length()) {
                char ch = text.charAt(at);
                if (ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r') {
                    at++;
                } else {
                    return;
                }
            }
        }

        private char peek() {
            if (at >= text.length()) {
                throw new IllegalArgumentException("unexpected end of input");
            }
            return text.charAt(at);
        }

        private void expect(String literal) {
            if (!text.startsWith(literal, at)) {
                throw new IllegalArgumentException("expected " + literal + " at " + at);
            }
            at += literal.length();
        }

        private Object value() {
            char ch = peek();
            if (ch == '{') {
                return object();
            }
            if (ch == '[') {
                return array();
            }
            if (ch == '"') {
                return string();
            }
            if (ch == 't') {
                expect("true");
                return Boolean.TRUE;
            }
            if (ch == 'f') {
                expect("false");
                return Boolean.FALSE;
            }
            if (ch == 'n') {
                expect("null");
                return null;
            }
            return number();
        }

        private Map<String, Object> object() {
            Map<String, Object> out = new LinkedHashMap<String, Object>();
            at++;
            skip();
            if (peek() == '}') {
                at++;
                return out;
            }
            while (true) {
                skip();
                String key = string();
                skip();
                if (peek() != ':') {
                    throw new IllegalArgumentException("expected : at " + at);
                }
                at++;
                skip();
                out.put(key, value());
                skip();
                char ch = peek();
                if (ch == ',') {
                    at++;
                    continue;
                }
                if (ch == '}') {
                    at++;
                    return out;
                }
                throw new IllegalArgumentException("expected , or } at " + at);
            }
        }

        private List<Object> array() {
            List<Object> out = new ArrayList<Object>();
            at++;
            skip();
            if (peek() == ']') {
                at++;
                return out;
            }
            while (true) {
                skip();
                out.add(value());
                skip();
                char ch = peek();
                if (ch == ',') {
                    at++;
                    continue;
                }
                if (ch == ']') {
                    at++;
                    return out;
                }
                throw new IllegalArgumentException("expected , or ] at " + at);
            }
        }

        private String string() {
            if (peek() != '"') {
                throw new IllegalArgumentException("expected a string at " + at);
            }
            at++;
            StringBuilder out = new StringBuilder();
            while (true) {
                if (at >= text.length()) {
                    throw new IllegalArgumentException("unterminated string");
                }
                char ch = text.charAt(at++);
                if (ch == '"') {
                    return out.toString();
                }
                if (ch != '\\') {
                    if (ch < 0x20) {
                        throw new IllegalArgumentException("control character in a string at " + at);
                    }
                    out.append(ch);
                    continue;
                }
                char escape = text.charAt(at++);
                if (escape == 'u') {
                    out.append((char) Integer.parseInt(text.substring(at, at + 4), 16));
                    at += 4;
                } else if (escape == 'n') {
                    out.append('\n');
                } else if (escape == 't') {
                    out.append('\t');
                } else if (escape == 'r') {
                    out.append('\r');
                } else if (escape == 'b') {
                    out.append('\b');
                } else if (escape == 'f') {
                    out.append('\f');
                } else if (escape == '"' || escape == '\\' || escape == '/') {
                    out.append(escape);
                } else {
                    throw new IllegalArgumentException("unknown escape at " + at);
                }
            }
        }

        private Object number() {
            int start = at;
            if (at < text.length() && text.charAt(at) == '-') {
                at++;
            }
            while (at < text.length() && Character.isDigit(text.charAt(at))) {
                at++;
            }
            boolean floating = false;
            if (at < text.length() && text.charAt(at) == '.') {
                floating = true;
                at++;
                while (at < text.length() && Character.isDigit(text.charAt(at))) {
                    at++;
                }
            }
            if (at < text.length() && (text.charAt(at) == 'e' || text.charAt(at) == 'E')) {
                floating = true;
                at++;
                if (at < text.length() && (text.charAt(at) == '+' || text.charAt(at) == '-')) {
                    at++;
                }
                while (at < text.length() && Character.isDigit(text.charAt(at))) {
                    at++;
                }
            }
            String token = text.substring(start, at);
            if (token.isEmpty() || "-".equals(token)) {
                throw new IllegalArgumentException("expected a value at " + start);
            }
            try {
                return floating ? (Object) Double.valueOf(token) : (Object) new BigInteger(token);
            } catch (NumberFormatException exc) {
                throw new IllegalArgumentException("not a number: " + token);
            }
        }
    }
}
"""


# ---------------------------------------------------------------------------
# the harness-owned pom profile: parity_pom.py, imported above
#
# The block text, its digest, the plugin pin and the idempotent rewrite live in
# parity_pom.py because bootstrap-destination.py writes the SAME block into the
# pom it bootstraps. Two copies would be two definitions of what makes the
# generated tests runnable at all.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# writing, and checking what was written
# ---------------------------------------------------------------------------

def assert_phase_roots(out_dir: str, resources_dir: str) -> None:
    """M4 only. A generated case under the loop's own test roots runs in every
    M3 verify, and a parity finding then reverts the step being verified."""
    for label, rel in (("--out", out_dir), ("--resources", resources_dir)):
        if _under(rel.rstrip("/"), *LOOP_TEST_ROOTS):
            raise Refuse("%s %s is under the M3 loop's test roots (%s); the generated parity tests execute in the M4 phase "
                         "only, from a root the %s profile adds (default %s / %s)"
                         % (label, rel, ", ".join(LOOP_TEST_ROOTS), POM_PROFILE_ID, DEFAULT_OUT, DEFAULT_RESOURCES))


def generate(root: Path, out_dir: str, resources_dir: str, security_mode: str, reset_cmd: str) -> tuple[int, str]:
    assert_phase_roots(out_dir, resources_dir)
    inputs = load_inputs(root)
    contract = reset_contract(root, inputs["corpus"], reset_cmd)
    cases, gaps = plan_cases(root, inputs, security_mode)
    # The pom is read and validated before anything is written: a pom this
    # producer may not own is a refusal, not a half-generated tree.
    pom_profile = ensure_pom_profile(root, out_dir.rstrip("/"), resources_dir.rstrip("/"), security_mode)

    support_package = ""
    if cases:
        support_package = common_package([c["package"].rsplit("." + GENERATED_PACKAGE_LEAF, 1)[0] for c in cases]) + "." + GENERATED_PACKAGE_LEAF

    files: dict[str, bytes] = {}
    by_class: dict[str, list[dict[str, Any]]] = {}
    for case in sorted(cases, key=lambda c: (c["class"], c["scenario"])):
        by_class.setdefault(case["class"], []).append(case)
    for fqcn, group in sorted(by_class.items()):
        rel = "%s/%s.java" % (out_dir.rstrip("/"), fqcn.replace(".", "/"))
        files[rel] = emit_test_class(group, support_package, inputs["corpus_sha256"], security_mode).encode("utf-8")
    if cases:
        rel = "%s/%s/%s.java" % (out_dir.rstrip("/"), support_package.replace(".", "/"), SUPPORT_CLASS)
        files[rel] = emit_support(support_package, inputs["corpus_sha256"], contract, security_mode, len(cases)).encode("utf-8")
    for case in cases:
        if not case["body_resource"]:
            continue
        src = root / case["body_file"]
        rel = "%s/%s" % (resources_dir.rstrip("/"), case["body_resource"])
        files[rel] = src.read_bytes()

    previous = root / MANIFEST
    stale: list[str] = []
    if previous.is_file():
        try:
            old = load_json(previous)
        except (OSError, ValueError):
            old = {}
        for row in (old.get("files") or []):
            rel = str((row or {}).get("path") or "")
            if rel and rel not in files and _under(rel, out_dir, resources_dir):
                stale.append(rel)
    for rel in stale:
        p = root / rel
        if p.is_file():
            p.unlink()
    for rel, blob in sorted(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    _prune_empty(root, out_dir)
    _prune_empty(root, resources_dir)

    manifest = {
        "schema": SCHEMA,
        "generator": GENERATOR,
        "generator_version": GENERATOR_VERSION,
        "corpus_sha256": inputs["corpus_sha256"],
        "corpus_provenance": inputs["corpus_provenance"],
        "evidence_bundle_sha256": inputs["evidence_bundle_sha256"],
        "source_digest": inputs["source_digest"],
        "qualification_sha256": inputs["qualification_sha256"],
        "security_mode": security_mode,
        # Whether the mode above is PINNED where the suite runs. An unpinned
        # mode is decided by whatever the test classpath sets -- on the pilot
        # specimen, the frozen source's own test resources -- so a manifest
        # that only recorded the mode would record an intention, not a fact.
        "security_mode_pinned": bool((pom_profile.get("pins") or {}).get("security_pinned")),
        "pin_notes": list((pom_profile.get("pins") or {}).get("notes") or []),
        "reset_contract": contract,
        "out": out_dir.rstrip("/"),
        "resources": resources_dir.rstrip("/"),
        # what the block IS, never what this run happened to do to it: a
        # manifest that recorded "changed" would differ between two runs of
        # the same producer on the same inputs.
        "pom_profile": {k: v for k, v in pom_profile.items() if k not in ("changed", "placement")},
        "pom_profile_sha256": pom_profile["sha256"],
        "support_class": (support_package + "." + SUPPORT_CLASS) if cases else "",
        "cases": [_case_row(c) for c in sorted(cases, key=lambda c: c["scenario"])],
        "gaps": sorted(gaps, key=lambda g: str(g["scenario"])),
        "totals": {"scenarios": len(cases) + len(gaps), "cases": len(cases), "gaps": len(gaps),
                   "classes": len(by_class)},
        "files": [{"path": rel, "sha256": hashlib.sha256(blob).hexdigest()} for rel, blob in sorted(files.items())],
    }
    write_canonical(root / MANIFEST, manifest)
    # The pom edit is a harness-owned change to a file the destination owns.
    # It is printed here so the phase that runs this producer can see it, and
    # it is recorded in the manifest; this producer never commits it.
    pin = ("%s:%s:%s" % (pom_profile["plugin"]["group_id"], pom_profile["plugin"]["artifact_id"], pom_profile["plugin"]["version"])
           if pom_profile["plugin"]["version"] else
           "%s:%s (version managed by the BOM)" % (pom_profile["plugin"]["group_id"], pom_profile["plugin"]["artifact_id"]))
    print("POM: %s profile %r %s (%s), test source %s, test resources %s, %s, block %s — harness-owned, not committed here"
          % (POM, POM_PROFILE_ID, "rewritten" if pom_profile["changed"] else "already current",
             pom_profile["placement"], out_dir.rstrip("/"), resources_dir.rstrip("/"), pin, pom_profile["sha256"][:12]))
    pins = pom_profile.get("pins") or {}
    pinned = ["%s=%s" % (p["name"], p["value"])
              for row in (pom_profile.get("test_plugins") or [])[:1] for p in row["system_properties"]]
    print("POM: the %s profile hands the test JVM %s (%s)"
          % (POM_PROFILE_ID, ", ".join(pinned) or "no system property",
             ", ".join(r["artifact_id"] for r in (pom_profile.get("test_plugins") or [])) or "no test plugin configured"))
    for note in (pins.get("notes") or []):
        print("POM: %s" % note)
    return 0, ("OK: GENERATE_TESTS %d case(s) in %d class(es), %d gap(s), security-mode %s (corpus %s) → %s"
               % (len(cases), len(by_class), len(gaps), security_mode, inputs["corpus_sha256"][:12], MANIFEST.as_posix()))


def _case_row(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario": case["scenario"],
        "class": case["class"],
        "method": case["method"],
        "entry_point": case["entry_point"],
        "declaring_type": case["declaring_type"],
        "http_method": case["http_method"],
        "path": case["path"],
        "request_sha256": case["request_sha256"],
        "capture_sha256": case["capture_sha256"],
        "intent": case["intent"],
        "status": case["status"],
        "body_resource": case["body_resource"],
        "body_sha256": case["body_sha256"],
        "response_body_sha256": case["response_body_sha256"],
        "asserted_headers": [h["name"] for h in case["asserted_headers"]],
        "required_headers": required_headers(case["http_method"], case["status"], case["request_headers"]),
        "effects": [p["id"] for p in case["effects"]],
        "before": [p["id"] for p in case["before"]],
        "reset_before": case["reset_before"],
        "credential_references": case["credential_references"],
        "source_origin": case["source_origin"],
    }


def _under(rel: str, *dirs: str) -> bool:
    return any(rel == d.rstrip("/") or rel.startswith(d.rstrip("/") + "/") for d in dirs)


def _prune_empty(root: Path, rel: str) -> None:
    base = root / rel
    if not base.is_dir():
        return
    for d in sorted(base.rglob("*"), key=lambda p: len(p.as_posix()), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()


def check(root: Path) -> tuple[int, str]:
    """The floor's question: are the files on disk the ones the harness wrote?"""
    p = root / MANIFEST
    if not p.is_file():
        raise Refuse("no %s; the product parity tests were never generated (generate-product-tests.py)" % MANIFEST)
    try:
        manifest = load_json(p)
    except (OSError, ValueError) as exc:
        raise Refuse("%s could not be read: %s" % (MANIFEST, exc))
    if manifest.get("schema") != SCHEMA:
        raise Refuse("%s is not a %s document" % (MANIFEST, SCHEMA))
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise Refuse("%s lists no generated files" % MANIFEST)

    try:
        corpus_sha = corpus_digest(load_corpus(root))
    except CorpusError as exc:
        raise Refuse(str(exc))
    if str(manifest.get("corpus_sha256") or "") != corpus_sha:
        raise Refuse("the generated tests were written for corpus %s and this tree's corpus is %s; regenerate them"
                     % (str(manifest.get("corpus_sha256") or "")[:12] or "<none>", corpus_sha[:12]))

    listed = {str((row or {}).get("path") or ""): str((row or {}).get("sha256") or "") for row in rows}
    problems: list[str] = []
    for rel in sorted(listed):
        f = root / rel
        if not f.is_file():
            problems.append("%s is missing" % rel)
            continue
        have = _sha_file(f)
        if have != listed[rel]:
            problems.append("%s is %s, the harness wrote %s" % (rel, have[:12], listed[rel][:12]))
    # The block that makes the generated tests runnable at all. A tree whose
    # tests are byte-perfect and whose profile is gone runs none of them, and
    # a suite that never ran is the failure this gate exists to catch.
    want_pom = str(manifest.get("pom_profile_sha256") or "")
    if not want_pom:
        raise Refuse("%s records no pom_profile_sha256; it was written before the %s profile was harness-owned — regenerate"
                     % (MANIFEST, POM_PROFILE_ID))
    have_pom, body = read_pom_profile(root)
    # BEFORE the digest: a block written before these pins existed matches its
    # own manifest byte for byte, and runs the suite with the profile guards
    # inactive and the security mode decided by the test classpath. The digest
    # cannot see that, so the DECLARATION is asked first.
    gaps = block_pin_gaps(root, body, str(manifest.get("security_mode") or ""))
    if gaps:
        raise Refuse("%s — the %s block of %s does not pin %s. Those are the destination's declared build profiles and the "
                     "captured security mode; without them the generated suite runs against a destination whose "
                     "profile-guarded beans are absent and whose security mode is whatever the test classpath sets. "
                     "Rewrite the block: bootstrap-destination.py --root <dest> --reapply-catalog"
                     % (STALE_BLOCK, POM_PROFILE_ID, POM, ", ".join(gaps)))
    if have_pom != want_pom:
        problems.append("the %s block of %s is %s, the harness wrote %s" % (POM_PROFILE_ID, POM, have_pom[:12], want_pom[:12]))

    out_dir = str(manifest.get("out") or DEFAULT_OUT)
    support = str(manifest.get("support_class") or "")
    package_leaf = "/" + GENERATED_PACKAGE_LEAF + "/"
    base = root / out_dir
    if base.is_dir():
        for f in sorted(base.rglob("*.java")):
            rel = f.relative_to(root).as_posix()
            if package_leaf in rel and rel not in listed:
                problems.append("%s is in the generated package and the manifest does not list it" % rel)
    if problems:
        raise Refuse("the generated product tests do not match the manifest (%d): %s"
                     % (len(problems), "; ".join(problems[:6])))
    return 0, ("OK: GENERATE_TESTS --check %d generated file(s) and the %s pom profile match the manifest "
               "(%d case(s), %d gap(s), source root %s, support %s)"
               % (len(listed), POM_PROFILE_ID, len(manifest.get("cases") or []), len(manifest.get("gaps") or []),
                  out_dir, support or "<none>"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the destination tree")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="where the generated test sources go; the %s profile adds it as a test source root, and it is "
                         "never one of the roots the M3 loop compiles (default %s)" % (POM_PROFILE_ID, DEFAULT_OUT))
    ap.add_argument("--resources", default=DEFAULT_RESOURCES,
                    help="where the recorded request bodies go; the %s profile adds it as a test resource root "
                         "(default %s)" % (POM_PROFILE_ID, DEFAULT_RESOURCES))
    ap.add_argument("--security-mode", choices=("disabled", "enabled"), default="disabled",
                    help="enabled: an authenticating scenario carries its credentials by REFERENCE (a system property or "
                         "environment variable name recorded in the manifest), never a literal")
    ap.add_argument("--reset-cmd", default="", help="the command that restores the declared initial state; defaults to the "
                                                    "reset script the capture skill uses, run from the product root")
    ap.add_argument("--check", action="store_true", help="verify the generated files on disk against the manifest digests")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("REFUSE: GENERATE_TESTS --root %s is not a directory" % args.root, file=sys.stderr)
        return 2
    try:
        rc, message = check(root) if args.check else generate(root, args.out, args.resources, args.security_mode, args.reset_cmd)
    except Refuse as exc:
        print("REFUSE: GENERATE_TESTS %s" % exc, file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print("REFUSE: GENERATE_TESTS %s" % exc, file=sys.stderr)
        return 1
    print(message)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
