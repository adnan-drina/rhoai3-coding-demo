#!/usr/bin/env python3
"""M4 parity, run as a tool: every scenario, every read oracle, one receipt.

The parity phase used to be a worker's judgement. Measured on destination v9's
first M4 card (t_32c82390, 2026-09-15): the worker composed the receipt BEFORE
any comparison, never ran compare-runtime-parity.py for a single one of the 34
admitted entry points (24 of them ended "no parity record"), and wrote floor
receipts by hand. Nothing about that is a model failure -- a phase whose order
and completeness live in prose is a phase that will be run in the wrong order
and incompletely. So the order and the completeness move here:

  1. every scenario the approved corpus declares, in CORPUS ORDER, with the
     reset command, through compare-scenario-parity.py
  2. every admitted entry point that has a CAPTURED http read oracle, through
     compare-runtime-parity.py
  2b. a bounded navigation check for every scenario whose first response on
     the DESTINATION was a redirect -- a SEPARATE measurement, never inside
     the comparison
  2c. every parity record that does NOT belong to this corpus, moved aside
  3. compose-parity-receipt.py, once, last

--scenario (repeatable) scopes step 1 to the named corpus scenarios and skips
step 2: that is how the fix-until-green acceptance path re-measures ONE parity
card's obligation without paying for the whole phase. Step 3 still runs, over
every record on disk, so the receipt a scoped run composes still states the
verdict of every entry point -- the scoped ones from this run, the rest from
the records their last full run left. The record says what was skipped and why.

--read-oracle (repeatable) re-runs step 2 for the named admitted entry points
inside a --scenario run (H3, dest v9 t_4d75569c): a parity obligation that
came from an entry point's READ ORACLE (the method-and-path replay, which
declares no scenario) is re-measured only by that replay, and a scoped run that
skipped every read oracle left the entry point's FAIL record on disk exactly as
the baseline had it -- so the card's repair could discharge its scenario
obligation and never its read-oracle one. The acceptance path names the entry
points of the issued card's obligations here; the record says which read
oracles this run re-ran (``read_oracles.rerun``) and names every other entry
point as not compared, with the reason. A read oracle NOT named keeps the
verdict its last run recorded: this run never writes that file. The read-oracle
phase is default-mode only, so an enabled-mode run re-runs none and says so.

Composing over the records on disk is what makes that possible, and it is why
step 2c exists. Measured on destination v9, verification/parity/scenarios/ held
cors-preflight-<digest>.json from an earlier naming scheme beside the current
sc_cors-preflight-<...>.json, and the composer read both: the leftover became
an INCONCLUSIVE row ("no scenario '<id>' in the corpus") and the receipt came
back 33 INCONCLUSIVE of 34 after a scoped run that compared one scenario. A
record whose file name is not the slug of a scenario this corpus declares, or
which was compared against another corpus digest or in another security mode,
is a leftover of another question: it is moved to
verification/parity/_orphaned/<stamp>/ with an index saying where it came from
and why, and _run.json records the move. Nothing is deleted -- another run's
evidence stays readable -- and with no corpus nothing is judged to belong or
not belong, so nothing is moved at all.

The admitted entry points are the ones the composer itself counts: the
evidence bundle's entry_points (_oracle_common.entry_points), and the
scenarios the corpus requires of them (_scenarios.load_corpus). Nothing is
recomputed here; this runner calls the same source of truth so the set it
compares and the set the receipt judges cannot drift apart.

With no --dest-url the runner packages nothing but starts what packaging
produced: target/quarkus-app/quarkus-run.jar against the decided datasource
(decisions.yaml), waits for readiness the way the capture skill waits for the
source, and stops what it started. A destination someone else is running is
passed in with --dest-url and is never stopped.

--issued <verification/loop/issued.json> says this run measures the CANDIDATE
that issued card was verified on rather than the accepted tree, and is passed
to BOTH comparators (scenario and read oracle) and to the composer so all of
them agree about it -- a parity obligation whose entry point declares no
scenario is a read oracle, and the whole phase is compared for it: on that path
the acceptance verify has already rebuilt the work list on the candidate, so
the live seal cannot match it, and what binds the verdicts instead is the
candidate digest this verification recorded, the receipt the card was minted
under and the card. Without it, the M4 road: the accepted tree, the sealed
receipt.

--security-mode says which setting of the source's security switch this run
measures (ADR-014), and it is the mode's own evidence throughout: the mode's
corpus, the mode's captures, the mode's parity records, the mode's receipt and
the mode's run record. Every child is told the same mode, so a destination
running with security enabled is never graded against anonymous expectations.
Two things follow from the mode and are recorded rather than assumed:

  - the read-oracle phase runs in the DEFAULT mode only. The read oracles are
    not mode-scoped (verification/source-oracles/<slug>.json) and were captured
    with the switch off; re-comparing them from an enabled-mode destination
    would compare an authenticated service against anonymous expectations. The
    enabled run names every entry point it did not compare, with that reason.
  - the identity an enabled-mode request is made as comes from the credential
    ENVIRONMENT VARIABLES the corpus names and the capture used -- the
    comparator reads them itself. This runner only checks, before it starts
    anything, that each one is set, and refuses naming the VARIABLE when it is
    not. What it holds is never read, printed or written.

--dest-config KEY=VALUE (repeatable) is the configuration the destination this
runner STARTS is started with: -DKEY=VALUE on its java command line, recorded
verbatim in the run record. --from-decisions fills it with the specimen's own
security switch from decisions.yaml (security.switch.key = the mode's declared
value), which is the default whenever an enabled-mode run has to start the
destination itself: ADR-014's exit is ONE artifact restarted with the switch
changed at runtime, so the switch must be a recorded property of the run and
not a shell someone remembers. A --dest-config value that equals a credential
the declared references hold is refused by KEY: the run record is evidence.

The run record carries the packaged artifact's digest (the quarkus-app manifest
digest the packaging and boot gates already compute over the same files), so
the two mode runs can be SHOWN to have measured one artifact rather than
asserted to have.

The comparison compares the FIRST response and never follows a redirect; that
is deliberate and unchanged. ADR-016 asks something the first response cannot
answer -- whether the legacy address SERVES the replacement UI or redirects to
its effective address -- so a bounded navigation runs beside the comparison,
on the destination only, and writes verification/parity/navigation/<slug>.json
(rhoai3.parity-navigation/v1) per scenario. A 302 to a 404 passes the
comparison and is exactly the dead compatibility URL the ruling refuses.

Writes the mode's run record (rhoai3.parity-run/v1) beside the mode's receipt:
what ran, in what order, with each child's exit code, the binding, the mode,
the configuration the destination was started with and the artifact digest.
The default mode's record is verification/parity/_run.json, exactly where it
has always been; the enabled mode writes _run-enabled.json beside it, so one
mode's run cannot overwrite the other's evidence -- the ADR-014 exit is the
two records held against each other.

``receipt_verdict`` is the verdict of a receipt THIS run composed, and null
when the composer refused. A refusing composer writes nothing and the previous
receipt stays on disk, still readable and still saying PASS: a scoped run over
a work list rebuilt on the candidate reported "receipt PASS" at rc 0 while the
only scenario it compared came back INCONCLUSIVE. So the receipt is read as
this run's measurement only when this run wrote it, it is OF what this run
measured (``binding``) and it names the receipt this run is bound to; the
record says which of those failed, and the runner exits 1.

Exit 0 when every child RAN and the receipt was composed. The receipt's own
verdict is the measurement, not this runner's grade: a FAIL or INCONCLUSIVE
receipt exits 0 here and refuses at compose-m4-verdict, where a refusal is a
verdict. Exit 1 only when a child could not run: no corpus, a destination that
never became ready, a child that produced no record, or a composer that
refused to compose. Exit 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _hermes_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "lib" / ".hermes-lib").is_file():
            return parent
    raise SystemExit("FAIL: PARITY_RUN .hermes/lib marker missing")


HERMES = _hermes_dir()
CAPTURE = HERMES / "skills" / "gates" / "capture-source-oracles" / "scripts"
RUNTIME_GATE = HERMES / "skills" / "migration" / "fix-until-green" / "scripts" / "verify-runtime.py"
COMPARE_SCENARIO = CAPTURE / "compare-scenario-parity.py"
COMPARE_RUNTIME = CAPTURE / "compare-runtime-parity.py"
COMPOSE_RECEIPT = CAPTURE / "compose-parity-receipt.py"
RESET_SCRIPT = CAPTURE / "reset-parity-db.sh"

sys.path.insert(0, str(CAPTURE))
sys.path.insert(0, str(HERMES / "lib"))
from _oracle_common import NAV_DEAD, NAV_LOOP, NAV_OK, NAV_TOO_MANY, ORACLES, PARITY, entry_points, final_page_differs, http_observe, navigate, slug  # noqa: E402
from _scenarios import (DEFAULT_SECURITY_MODE, PARITY_ORPHANS, SECURITY_MODES, CorpusError, auth_headers, binding_of,  # noqa: E402
                        candidate_binding, corpus_digest, corpus_path, credential_conflicts, effects_identity_of,
                        load_corpus, normalize_security_mode, normalized_identity, parity_receipt_path,
                        parse_assignments, partition_parity_records, scenario_parity_dir, scenario_slug,
                        scenario_oracles_dir, sealed_binding)
from planner.admission import verify_receipt  # noqa: E402
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import VERIFY_PACKAGE  # noqa: E402
from planner.server_error import annotate_record  # noqa: E402

SCHEMA = "rhoai3.parity-run/v1"
READ_METHODS = ("GET", "HEAD")

# The bounded navigation check (ADR-016), which is a SEPARATE measurement and
# never part of the comparison. The comparator compares the FIRST response and
# nothing else, by design: following a redirect inside it would record the
# target's answer as the source's and drop the Location that said where it
# pointed. But ADR-016's exit is not only "302 with exactly that Location" --
# it is also "that legacy address serves the replacement UI or redirects to
# its effective address", proven by "a separate bounded navigation check
# reaching the real UI and usable OpenAPI document in the packaged production
# artifact, without a redirect loop". A 302 to a 404 satisfies the comparison
# and is the dead compatibility URL the ruling refuses; nothing measured it.
# So the navigation runs here, beside the comparison, over the DESTINATION
# only, writes its own records, and the composer reads them.
NAVIGATION = PARITY / "navigation"
NAV_SCHEMA = "rhoai3.parity-navigation/v1"
NAV_DEFAULT_HOPS = 3
NAV_COUNTER = {NAV_OK: "ok", NAV_DEAD: "dead", NAV_LOOP: "loop", NAV_TOO_MANY: "too_many_hops"}
# Where a parity record that does not belong to this corpus is moved before the
# composer reads the directory, and the index that says where each came from.
# Never a delete: a record another run produced stays readable.
ORPHAN_INDEX_SCHEMA = "rhoai3.parity-orphans/v1"
# What a scoped run does NOT measure, named in the record rather than left to
# be inferred from a count: a filtered run is a re-measurement of one card's
# obligation, and the read oracles of every other entry point keep the verdicts
# their last full run recorded (the composer reads those records, not this run).
READ_ORACLES_FILTERED = ("skipped: this run compares only the scenarios it was scoped to (%s)%s; the read-oracle verdicts "
                         "on disk are the ones the last unfiltered run recorded")
# ... and what an enabled-mode run does NOT measure, for a reason that is not a
# choice: the read oracles live in an oracle directory that is NOT mode-scoped
# (verification/source-oracles/<slug>.json) and were captured with the switch
# off. Replaying them against a destination running with security enabled would
# compare an authenticated service against anonymous expectations -- the
# cross-mode reuse ADR-014 forbids, arriving through the phase that was never
# mode-scoped. The verdicts the default-mode run recorded stay on disk and the
# composer reads those; this run says plainly that it re-measured none of them.
READ_ORACLES_MODE = ("skipped: the read oracles are %s-mode captures (%s is not mode-scoped) and this run is of the %s "
                     "mode; the read-oracle verdicts on disk are the ones the %s-mode run recorded")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: PARITY_RUN cannot load %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_GATE: Any = None


def _runtime_gate() -> Any:
    """The packaging/boot gate, loaded once: it owns what the packaged artifact
    IS (the quarkus-app manifest) and how it is started, and parity measures
    what that gate produced rather than a second opinion about it."""
    global _GATE
    if _GATE is None:
        _GATE = _load_module(RUNTIME_GATE, "verify_runtime_gate")
    return _GATE


def run_record_path(security_mode: str) -> Path:
    """Where THIS mode's run record goes.

    The default mode keeps verification/parity/_run.json exactly where the
    paved road KEEPs it; the enabled mode writes its own beside it. One file
    per mode is the point: ADR-014's exit is two runs of one artifact shown
    together, and a shared record would leave the second run's evidence as the
    only evidence there ever was."""
    mode = normalize_security_mode(security_mode)
    return PARITY / ("_run.json" if mode == DEFAULT_SECURITY_MODE else "_run-%s.json" % mode)


def artifact_identity(root: Path) -> dict[str, Any]:
    """What the destination this run measures IS, by digest.

    ADR-014 asks the enabled mode to be proved "from one artifact, restarted
    with the switch changed at runtime". Two run records that each name the
    same digest are what SHOWS that; two runs that merely happened in sequence
    show nothing. The digest is the packaging gate's own: one sha256 over every
    file of target/quarkus-app (quarkus-run.jar is a thin launcher beside lib/,
    app/ and quarkus/, so hashing it alone would not notice a changed
    dependency), computed by the same function the boot gate computes it with,
    beside the digest packaging recorded for the same tree."""
    gate = _runtime_gate()
    files, manifest = gate.artifact_manifest(Path(root))
    doc: dict[str, Any] = {"path": gate.APP_DIR.as_posix(), "sha256": manifest, "files": len(files),
                           "packaged_sha256": "", "reason": ""}
    if not manifest:
        doc["reason"] = ("%s is absent; the packaging gate produces the artifact parity starts, and there is nothing to "
                         "identify this run's destination by" % gate.APP_DIR.as_posix())
    p = Path(root) / VERIFY_PACKAGE
    if p.is_file():
        try:
            doc["packaged_sha256"] = str((load_json(p) or {}).get("artifact_sha256") or "")
        except (OSError, ValueError):
            doc["packaged_sha256"] = ""
    if manifest and doc["packaged_sha256"] and doc["packaged_sha256"] != manifest:
        doc["reason"] = ("the artifact on disk is not the one packaging verified (%s, packaged %s); it was rebuilt or "
                         "changed since" % (manifest[:12], doc["packaged_sha256"][:12]))
    return doc


def decided_security(root: Path) -> tuple[dict[str, Any], str]:
    """(the decided security switch and identities, why-not) from decisions.yaml.

    The switch is the SPECIMEN's own: which property turns its security on is
    an Operator decision under an accepted ADR, never a name this harness
    carries. Nothing here is a credential -- the identities name environment
    variables, and only the names travel."""
    from planner.decisions import DecisionsError, load_decisions, security
    from planner.paths import DECISIONS

    try:
        doc = load_decisions(Path(root))
    except DecisionsError as exc:
        return {}, str(exc)
    decided = security(doc)
    if not decided:
        return {}, ("%s declares no usable security section (ADR-014): the specimen's own security switch is an Operator "
                    "decision, and a destination started without it would be measured for a mode nobody set"
                    % DECISIONS.as_posix())
    return decided, ""


def switch_config(decided: dict[str, Any], security_mode: str) -> dict[str, str]:
    """The declared switch at this mode's setting, as one KEY=VALUE property."""
    switch = (decided or {}).get("switch") or {}
    key = str(switch.get("key") or "")
    value = str(switch.get("enabled_value" if security_mode != DEFAULT_SECURITY_MODE else "disabled_value") or "")
    return {key: value} if key and value else {}


def corpus_credential_refs(scenarios: list[dict[str, Any]]) -> list[str]:
    """Every environment variable the given scenarios are replayed as, by NAME.

    Both identity shapes count, and both places an identity can appear: the
    request's own ``identity`` and the ``effects_identity`` its read-backs are
    taken as. The comparator resolves these itself at request time; this is the
    list whose absence it would discover one refusal at a time."""
    names: set[str] = set()
    for sc in scenarios or []:
        for ident in (sc.get("identity"), effects_identity_of(sc)):
            row = normalized_identity(ident) if ident else {}
            if str(row.get("kind") or "none") in ("", "none"):
                continue
            ref = str(row.get("credential_ref") or "")
            if ref:
                names.add(ref)
                continue
            names.update(n for n in (str(row.get("user_env") or ""), str(row.get("password_env") or "")) if n)
    return sorted(names)


def missing_credentials(names: list[str]) -> list[str]:
    """The named variables this workspace does not hold. The NAME is the whole
    message: what it would have held is never read, printed or written."""
    return [n for n in names if not os.environ.get(n, "").strip()]


def dest_config_argv(dest_config: dict[str, str]) -> list[str]:
    """The configuration as the JVM takes it: one -DKEY=VALUE per property, in
    a fixed order so two runs of the same configuration produce the same
    command line."""
    return ["-D%s=%s" % (k, v) for k, v in sorted((dest_config or {}).items())]


def _verdict_of(path: Path) -> tuple[str, str]:
    """The verdict a comparator recorded, or ("", "") when it recorded none.

    A comparator exits 1 for a FAIL and for an INCONCLUSIVE alike; the record
    is what says which, and its ABSENCE is what says the child could not run."""
    if not path.is_file():
        return "", ""
    try:
        doc = load_json(path)
    except (OSError, ValueError):
        return "", "unreadable record %s" % path.name
    if not isinstance(doc, dict):
        return "", "record %s is not an object" % path.name
    return str(doc.get("verdict") or ""), str(doc.get("reason") or "")


def _rel_or_empty(root: Path, p: Path | None) -> str:
    if p is None:
        return ""
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def json_compact(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _file_stamp(path: Path) -> dict[str, Any]:
    """What identifies the file on disk right now: whether it is there, its
    content digest, its size and the nanosecond it was last written.

    write_canonical ALWAYS rewrites the bytes, so a file whose digest, size and
    mtime are all the ones taken a moment earlier was not written in between."""
    try:
        st = path.stat()
    except OSError:
        return {"present": False, "sha256": "", "size": 0, "mtime_ns": 0}
    try:
        sha = sha256_file(path)
    except OSError:
        sha = ""
    return {"present": True, "sha256": sha, "size": int(st.st_size), "mtime_ns": int(st.st_mtime_ns)}


def _composed_by_this_run(before: dict[str, Any], after: dict[str, Any], doc: Any,
                          binding: dict[str, Any], receipt_sha: str, rc: int) -> str:
    """"" when the receipt on disk is the one THIS run's composer wrote, else
    why it is not.

    The composer refuses without writing (a binding it cannot make, a mode
    mismatch, a seal that is not authoritative) and the PREVIOUS receipt then
    stays on disk, unchanged and still readable. Reading its verdict as this
    run's measurement is a false green, and it was measured: a scoped unbound
    run over a rebuilt work list printed "receipt PASS" at rc 0 while the only
    scenario it compared came back INCONCLUSIVE.

    So the receipt is trusted only when this run produced it, on three counts
    the receipt itself carries: it was WRITTEN during this run (the composer
    refuses without writing, and write_canonical never leaves the bytes,
    the size and the mtime all as they were), it is OF what this run measured
    (``binding``), and it names the receipt this run is bound to
    (``receipt_sha256``). Any one of them failing leaves the verdict
    unmeasured rather than borrowed from whoever wrote the file last."""
    if not after.get("present"):
        return "compose-parity-receipt.py wrote no receipt at all (rc %d)" % rc
    if before.get("present") and all(before.get(k) == after.get(k) for k in ("sha256", "size", "mtime_ns")):
        return ("the receipt on disk is the one this run started from, byte for byte and to the nanosecond; the composer "
                "refused (rc %d) and left it" % rc)
    if not isinstance(doc, dict):
        return "the composed receipt is not an object"
    got = binding_of(doc)
    if got != (binding or {}):
        return ("it is a measurement of %s and this run measured %s"
                % (json_compact(got), json_compact(binding or {})))
    if receipt_sha and str(doc.get("receipt_sha256") or "") != receipt_sha:
        return ("it names receipt %s and this run is bound to %s"
                % (str(doc.get("receipt_sha256") or "")[:12] or "none", receipt_sha[:12]))
    return ""


def _run_child(argv: list[str], label: str) -> subprocess.CompletedProcess:
    """One child, one line of log. The v9 card's 77 KB worker log is the reason
    this prints a summary rather than the child's whole output."""
    proc = subprocess.run(argv, text=True, capture_output=True)
    tail = [ln for ln in ((proc.stdout or "") + (proc.stderr or "")).splitlines() if ln.strip()]
    print("  [%d] %s%s" % (proc.returncode, label, (" :: " + tail[-1][:200]) if tail else ""))
    return proc


# --- the destination this runner starts, when nobody handed it one ----------

def _wait_ready(url: str, timeout: int, proc: subprocess.Popen | None) -> tuple[bool, str]:
    """Readiness as the capture skill defines it for the source: any answer
    below 500 from the process we started, within a bounded time."""
    started = time.time()
    last = ""
    while time.time() - started < timeout:
        if proc is not None and proc.poll() is not None:
            return False, "the destination exited with %d before answering" % proc.returncode
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - our own application
                if int(resp.status) < 500:
                    return True, ""
        except urllib.error.HTTPError as exc:
            if int(exc.code) < 500:
                return True, ""
            last = "HTTP %s" % exc.code
        except Exception as exc:  # noqa: BLE001 - any transport error is "not yet"
            last = str(exc)
        time.sleep(1.0)
    return False, last or "no answer within %ds" % timeout


class Destination:
    """The packaged destination, started against the decided database.

    Packaging is NOT done here: the packaging gate (verify-runtime.py --gate
    package) owns that, and a parity run that rebuilt the tree would be
    comparing something other than what was verified. This starts the artifact
    that gate produced, and stops it again."""

    def __init__(self, root: Path, port: int, java: str | None, timeout: int,
                 dest_config: dict[str, str] | None = None) -> None:
        self.root = root
        self.port = port
        self.gate = _runtime_gate()
        # The java this destination is started with is the boot gate's own
        # (verify-runtime.py / run-verify.sh: $JAVA_HOME_21, then $JAVA_HOME,
        # then PATH), resolved by the one function both import. dest v9 took
        # the first `java` on PATH, an older runtime than the build's, and the
        # artifact died with UnsupportedClassVersionError. --java overrides.
        if java:
            self.java, self.java_source = java, "--java"
        else:
            self.java, self.java_source = self.gate.resolve_java()
        # what was resolved, its version and what the artifact requires; filled
        # by start() before anything is started, and recorded in _run.json
        self.java_record: dict[str, Any] = {"binary": self.java, "source": self.java_source}
        self.timeout = timeout
        # The configuration this destination is STARTED with -- the security
        # switch at the setting this run measures, first among them. It is the
        # caller's (or the Operator's, through decisions.yaml): the harness
        # knows no property name of the specimen's own.
        self.dest_config = dict(dest_config or {})
        self.argv: list[str] = []
        self.proc: subprocess.Popen | None = None
        self.log = root / PARITY / "logs" / "destination.log"
        self.root_path = self.gate.root_path_of(root)
        self.ds: dict[str, Any] = {}
        self.profiles: list[str] = []

    def command(self) -> list[str]:
        """The command line this destination is started with.

        The configuration goes on it as system properties: the SAME artifact,
        started again with a different switch setting, which is what ADR-014
        asks the enabled mode to be proved from. It is a method so the command
        can be read -- by this runner's record, and by a test -- without
        starting anything."""
        return [self.java, *dest_config_argv(self.dest_config), "-jar", str(self.gate.RUNNER)]

    @property
    def base_url(self) -> str:
        rp = self.root_path if self.root_path.startswith("/") else "/" + self.root_path
        return "http://127.0.0.1:%d%s" % (self.port, rp.rstrip("/") if rp != "/" else "")

    def start(self) -> str:
        from planner.decisions import DecisionsError, build_profiles, datasource, load_decisions

        try:
            decisions = load_decisions(self.root)
            self.ds = datasource(decisions) or {}
            self.profiles = [str(x) for x in (build_profiles(decisions).get("active") or [])]
        except DecisionsError as exc:
            return str(exc)
        if not self.ds:
            return ("the effective datasource is not decided (decisions.yaml datasource under an accepted ADR); "
                    "there is no database to compare the destination against")
        runner = self.root / self.gate.RUNNER
        if not runner.is_file():
            return ("the destination is not packaged (%s is absent); the packaging gate produces what parity starts"
                    % self.gate.RUNNER.as_posix())
        # Can the resolved runtime run what was packaged? Asked BEFORE starting:
        # an artifact compiled for a newer Java dies at class loading, and the
        # only thing the readiness wait would say is that nothing answered.
        self.java_record, refusal = self.gate.runtime_check(self.root, self.gate.APP_DIR, self.java, self.java_source)
        if refusal:
            return refusal
        # Whose database is this? A parity result taken against another run's
        # data is evidence about the wrong data, so the endpoint is parsed and
        # compared with this run's assignment and receipt before the
        # destination is started -- the same check the reset and the startup
        # gate make, from the same module, so they cannot disagree.
        from planner import run_identity

        verdict = run_identity.check(self.root)
        if verdict.blocking_for("parity"):
            return "%s %s" % (verdict.code, verdict.detail)
        ok, _ = _wait_ready(self.base_url, 1, None)
        if ok:
            return ("port %d is already answering before anything was started; a parity reading there would not be "
                    "about this application (pass --dest-url to compare against a destination someone else runs)" % self.port)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ)
        env["QUARKUS_HTTP_PORT"] = str(self.port)
        if self.profiles:
            env["QUARKUS_PROFILE"] = ",".join(self.profiles)
        sink = self.log.open("wb")
        # kept so the run record can state what was STARTED rather than what
        # was intended
        self.argv = self.command()
        self.proc = subprocess.Popen(self.argv, cwd=str(self.root),
                                     stdout=sink, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        ready, why = _wait_ready(self.base_url, self.timeout, self.proc)
        text = self.log.read_text(encoding="utf-8", errors="replace") if self.log.is_file() else ""
        if not ready:
            return "the destination did not become ready: %s (see %s)" % (why, self.log.name)
        db_ok, db_why = self.gate.database_ready(text, self.ds)
        if not db_ok:
            return "the destination answered but its datasource did not start: %s (see %s)" % (db_why, self.log.name)
        return ""

    def stop(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=25)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:  # noqa: BLE001
                    pass
        self.proc = None


# --- what gets compared ------------------------------------------------------

def read_oracle_gap(root: Path, ep: str) -> str:
    """"" when this entry point has a CAPTURED http read oracle, else why not.

    compare-runtime-parity.py replays a method and a path: that is a read, and
    provably not a write (it sends no body). The gap is NAMED rather than
    passed over in silence -- an entry point nobody could compare is a coverage
    gap the receipt reports, not an absence nobody wrote down."""
    p = root / ORACLES / (slug(ep) + ".json")
    if not p.is_file():
        return "no source oracle captured at M1"
    try:
        oracle = load_json(p)
    except (OSError, ValueError):
        return "the source oracle is unreadable"
    if str(oracle.get("status") or "") != "CAPTURED":
        return "the source oracle is %s: %s" % (oracle.get("status"), str(oracle.get("reason") or "")[:120])
    kind = str(oracle.get("kind") or "")
    if kind != "http":
        return "a %s entry point is compared from a captured destination observation (--dest-observation), not over HTTP" % (kind or "non-http")
    method = str((oracle.get("oracle") or {}).get("method") or "GET").upper()
    if method not in READ_METHODS:
        return "a %s entry point is compared through the scenario corpus, not by replaying a method and a path" % method
    return ""


# --- the bounded navigation check -------------------------------------------

# _split_url / navigate live in _oracle_common (shared with the SOURCE capture,
# so both sides record the same walk shape and the composer can compare the
# final pages -- H11)


def redirect_target(record: Any, dest_url: str) -> str:
    """The address a scenario's FIRST response on the destination sent the
    caller to, resolved against the destination -- "" when that response was
    not a redirect with a Location.

    The comparison's own record is what says so: this reads the observation it
    already made rather than repeating the request."""
    observed = (record or {}).get("observed") if isinstance(record, dict) else None
    observed = observed if isinstance(observed, dict) else {}
    try:
        status = int(observed.get("status") or 0)
    except (TypeError, ValueError):
        return ""
    if not (300 <= status < 400):
        return ""
    headers = observed.get("headers") if isinstance(observed.get("headers"), dict) else {}
    location = headers.get("Location")
    if not location:
        return ""
    return urllib.parse.urljoin(str(dest_url or "").rstrip("/") + "/", str(location))


def run_navigation(root: Path, scenarios: list[dict[str, Any]], dest_url: str, max_hops: int,
                   nav: dict[str, Any], parity_dir: Path, oracles_dir: Path | None = None) -> None:
    """One bounded navigation per scenario whose first response on the
    DESTINATION was a redirect, recorded beside the comparison it belongs to.

    Credentials: none, unless the scenario declares an ``effects_identity`` --
    the identity its read-backs are taken as -- and then the SAME reference,
    resolved from this environment. A navigation that invented an identity
    would be measuring an address nobody navigates to."""
    nav["ran"] = True
    for sc in scenarios:
        sid = str(sc.get("id") or "")
        if not sid:
            continue
        rec_p = root / parity_dir / (scenario_slug(sid) + ".json")
        try:
            record = load_json(rec_p) if rec_p.is_file() else {}
        except (OSError, ValueError):
            nav["not_navigated"].append({"scenario": sid, "reason": "the comparison record %s is unreadable" % rec_p.name})
            continue
        start = redirect_target(record, dest_url)
        if not start:
            continue
        identity = effects_identity_of(sc)
        headers: dict[str, str] = {}
        if identity is not None:
            headers, gap = auth_headers(identity)
            if gap:
                nav["not_navigated"].append({"scenario": sid, "reason": gap})
                continue
        result = navigate(start, headers, max_hops)
        out = {"schema": NAV_SCHEMA, "producer": "run-parity.py", "at": _now(), "scenario": sid,
               "entry_point": str(sc.get("entry_point") or ""), "dest_url": dest_url, "max_hops": int(max_hops),
               "identity": dict(normalized_identity(identity)) if identity is not None else {}}
        out.update(result)
        # H11: the SOURCE's own walk, when its capture recorded one, decides
        # whether the page the destination lands on is the kind the source's is
        src_rec_p = root / oracles_dir / (scenario_slug(sid) + ".json")
        try:
            src_nav = (load_json(src_rec_p) if src_rec_p.is_file() else {}).get("navigation") or {}
        except (OSError, ValueError):
            src_nav = {}
        out["source_final"] = dict(src_nav.get("final") or {}) if isinstance(src_nav, dict) else {}
        out["final_differs"] = final_page_differs(result.get("final"), out["source_final"]) if result.get("terminal") == NAV_OK else ""
        write_canonical(root / NAVIGATION / (scenario_slug(sid) + ".json"), out)
        nav["checked"] += 1
        nav[NAV_COUNTER[result["terminal"]]] += 1
        nav["results"].append({"scenario": sid, "entry_point": str(sc.get("entry_point") or ""),
                               "start": result["start"], "terminal": result["terminal"],
                               "final_status": result["final_status"], "hops": len(result["hops"]),
                               "final_differs": out["final_differs"]})
        if out["final_differs"]:
            nav["final_differs"] = int(nav.get("final_differs") or 0) + 1
        print("  [nav] %s %s → %s (%s, %d hop(s)%s)" % (sid, result["start"], result["terminal"],
                                                        result["final_status"], len(result["hops"]),
                                                        ("; final page differs from the source: " + out["final_differs"]) if out["final_differs"] else ""))


def prune_orphaned_records(root: Path, security_mode: str, corpus: dict[str, Any], corpus_sha: str,
                           at: str) -> dict[str, Any]:
    """Move every parity record that does not belong to THIS corpus aside,
    before the composer reads the directory.

    The composer composes over the records on disk -- that is what keeps a
    scoped run from erasing the verdicts the last full run left for every other
    scenario -- and it names the ones that do not belong rather than judging
    them. This is the other half: a leftover from an earlier naming scheme, an
    earlier corpus or another mode is not evidence of anything about this run,
    so it stops accumulating in the directory the next run will read. Measured
    on destination v9: verification/parity/scenarios/ held
    cors-preflight-<digest>.json beside the current sc_cors-preflight-<...>.json
    and the receipt came back 33 INCONCLUSIVE of 34.

    Nothing is deleted. Each record is moved under
    verification/parity/_orphaned/<stamp>/ with an index naming where it came
    from and why, so the evidence a previous run produced is still readable and
    the move itself is on the record."""
    out: dict[str, Any] = {"pruned": 0, "dir": "", "records": [], "gaps": []}
    if not corpus:
        out["gaps"].append("no corpus was loaded, so no record could be judged to belong to one; nothing was moved")
        return out
    _kept, orphans = partition_parity_records(root, security_mode, "",
                                              declared=(corpus.get("scenarios") or []), corpus_sha=corpus_sha)
    if not orphans:
        return out
    stamp = at.replace("-", "").replace(":", "") or _now().replace("-", "").replace(":", "")
    where = root / PARITY_ORPHANS / stamp
    n = 2
    while where.exists():
        where = root / PARITY_ORPHANS / ("%s-%d" % (stamp, n))
        n += 1
    where.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, Any]] = []
    for o in orphans:
        src = root / o["path"]
        target = where / src.name
        k = 2
        while target.exists():
            target = where / ("%s-%d%s" % (src.stem, k, src.suffix))
            k += 1
        try:
            src.replace(target)
        except OSError as exc:
            out["gaps"].append("%s could not be moved aside (%s); it stays where it is and the receipt names it"
                               % (o["path"], exc))
            continue
        moved.append({**o, "moved_to": target.relative_to(root).as_posix()})
        print("  [orphan] %s (%s): %s" % (o["path"], o["kind"], o["reason"]))
    if not moved:
        try:
            where.rmdir()
        except OSError:
            pass
        return out
    write_canonical(where / "_index.json",
                    {"schema": ORPHAN_INDEX_SCHEMA, "producer": "run-parity.py", "at": at,
                     "from": scenario_parity_dir(security_mode).as_posix(), "security_mode": security_mode,
                     "corpus_sha256": corpus_sha, "records": moved})
    out["pruned"] = len(moved)
    out["dir"] = where.relative_to(root).as_posix()
    out["records"] = moved
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the destination product root")
    ap.add_argument("--dest-url", default="", help="a destination someone else is running; without it the packaged one is started here and stopped again")
    ap.add_argument("--reset-cmd", default="", help="the command that restores the declared initial state (default: the reset script beside the capture skill)")
    ap.add_argument("--scenario", action="append", default=[], metavar="ID",
                    help="repeatable: compare ONLY these corpus scenarios (the fix-until-green acceptance path scopes the "
                         "comparison to the scenarios the issued parity card is made of). The read-oracle phase is skipped "
                         "under the filter -- except for the entry points --read-oracle names -- and said so in _run.json; "
                         "the composer still runs, over every record on "
                         "disk that belongs to this corpus -- so the scenarios this run did not compare keep the "
                         "verdicts their last run recorded")
    ap.add_argument("--read-oracle", action="append", default=[], metavar="ENTRY_POINT",
                    help="repeatable, with --scenario: ALSO re-run the read oracle (the method-and-path replay) of this "
                         "admitted entry point, so a scoped acceptance run re-measures a card's read-oracle obligation "
                         "and not only its scenario ones (dest v9 t_4d75569c). _run.json names the entry points whose "
                         "read oracle this run re-ran under read_oracles.rerun; the read-oracle records of every other "
                         "entry point are left exactly as their last run wrote them. Default-mode only, like the "
                         "phase itself. An entry point nobody admitted is refused; without --scenario the whole "
                         "phase runs and every read oracle with it")
    ap.add_argument("--issued", default="", metavar="PATH",
                    help="verification/loop/issued.json: this run measures the CANDIDATE that issued card was verified on, "
                         "not the accepted tree. The binding is passed to both comparators and the composer, which then do not "
                         "ask the live seal to match the work list the acceptance path rebuilt on the candidate, and is "
                         "recorded in _run.json. Passing it more than once is the same as passing it once.")
    ap.add_argument("--nav-max-hops", type=int, default=NAV_DEFAULT_HOPS, metavar="N",
                    help="how many redirects the bounded navigation check follows from a scenario's redirect target "
                         "before it calls the chain too long (default %d). The navigation is a SEPARATE measurement "
                         "beside the comparison and is performed on the destination only; the comparison itself never "
                         "follows a redirect." % NAV_DEFAULT_HOPS)
    ap.add_argument("--no-navigation", action="store_true",
                    help="do not perform the bounded navigation check. _run.json then records navigation: skipped, and "
                         "the records of any earlier run stay on disk for the composer to read")
    ap.add_argument("--security-mode", choices=list(SECURITY_MODES), default=DEFAULT_SECURITY_MODE,
                    help="which setting of the source's security switch this run measures (ADR-014, default %s). It selects "
                         "the mode's corpus, the mode's captures, the mode's parity records, the mode's receipt and the "
                         "mode's run record, and is passed to every comparator and to the composer. The read-oracle phase "
                         "runs in the %s mode only: those captures are not mode-scoped"
                         % (DEFAULT_SECURITY_MODE, DEFAULT_SECURITY_MODE))
    ap.add_argument("--dest-config", action="append", default=[], metavar="KEY=VALUE",
                    help="configuration the destination this runner STARTS is started with (repeatable), passed as a JVM "
                         "system property (-DKEY=VALUE) and recorded verbatim in the run record. For the enabled mode this "
                         "is the specimen's own security switch; the key is recorded, never assumed. A value that equals a "
                         "declared credential is refused by key")
    ap.add_argument("--from-decisions", action="store_true",
                    help="take the destination's security switch from decisions.yaml's security section (ADR-014): "
                         "--dest-config is filled with switch.key = the value that mode declares (enabled_value for the "
                         "enabled mode, disabled_value for the disabled one). The default whenever an enabled-mode run has "
                         "to start the destination itself. A --dest-config the caller named for the same key wins")
    ap.add_argument("--port", type=int, default=8081, help="the port the destination this runner starts listens on")
    ap.add_argument("--dest-log", default="",
                    help="H5b: the log of a destination passed with --dest-url, so a 5xx verdict can carry the destination's "
                         "exception (the destination this runner starts logs to verification/parity/logs/destination.log and "
                         "needs nothing). For every FAIL whose status difference is a 5xx the source did not answer, the "
                         "exception block is taken from the log -- by the error id the body carried, else the last "
                         "ERROR/stack block appended while the request ran -- and recorded bounded on the verdict as "
                         "server_error, with the first frames that belong to THIS product resolved to their files")
    ap.add_argument("--ready-timeout", type=int, default=180)
    ap.add_argument("--java", default=None,
                    help="the java that starts the destination; default the boot gate's own: $JAVA_HOME_21/bin/java, "
                         "then $JAVA_HOME/bin/java, then java on PATH. Recorded with its version under "
                         "destination.java in _run.json, and refused before starting when the packaged classes need a "
                         "newer Java")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print("FAIL: PARITY_RUN --root must be an existing directory", file=sys.stderr)
        return 2
    try:
        security_mode = normalize_security_mode(args.security_mode)
        dest_config = parse_assignments(args.dest_config, "--dest-config")
    except CorpusError as exc:
        print("FAIL: PARITY_RUN %s" % exc, file=sys.stderr)
        return 2
    # Which evidence this run is OF, resolved once, through the same functions
    # every other producer resolves it through: no path is spelled here, so no
    # two of them can drift apart or share a directory between modes.
    corpus_rel = corpus_path(security_mode)
    parity_dir = scenario_parity_dir(security_mode)
    receipt_rel = parity_receipt_path(security_mode)
    mode_argv = ["--security-mode", security_mode]
    reset_cmd = args.reset_cmd or shlex.join(["bash", str(RESET_SCRIPT), "--root", str(root)])

    # What this run MEASURES: the accepted tree under the live seal, or the
    # candidate an issued card was verified on. The children are told the same
    # thing, so the runner, the comparator and the composer cannot disagree
    # about which tree the verdicts are of.
    binding, binding_gaps = ({}, [])
    binding_notes: list[str] = []
    if args.issued:
        binding, binding_gaps = candidate_binding(root, issued_path=args.issued, notes=binding_notes)
        for note in binding_notes:
            # H10: said out loud, never a refusal -- the binding is to the
            # receipt the card was minted under
            print("parity: NOTE %s" % note, file=sys.stderr)
    else:
        binding = sealed_binding()
    issued_argv = ["--issued", str(args.issued)] if args.issued else []

    receipt, receipt_gaps = verify_receipt(root, require_admitted=True)
    # Which receipt a receipt composed by THIS run must name: the one the card
    # was minted under on the acceptance path, the live seal on the M4 road.
    expected_receipt_sha = (str(binding.get("issued_receipt_sha256") or "")
                            if str(binding.get("mode") or "") == "candidate"
                            else str((receipt or {}).get("receipt_digest") or ""))
    wanted = sorted(str(e.get("id")) for e in entry_points(root) if e.get("id"))
    corpus: dict[str, Any] = {}
    corpus_error = ""
    try:
        corpus = load_corpus(root, security_mode)
    except CorpusError as exc:
        corpus_error = str(exc)
    corpus_sha = corpus_digest(corpus) if corpus else ""
    declared = [sc for sc in (corpus.get("scenarios") or []) if str(sc.get("id") or "")]
    # The filter SELECTS from the corpus; it never invents a scenario. An id
    # nobody declared is a caller asking for a comparison that cannot be made,
    # and it refuses rather than running a smaller set in silence.
    wanted_ids = sorted({str(s) for s in (args.scenario or []) if str(s)})
    unknown_ids = [s for s in wanted_ids if s not in {str(sc["id"]) for sc in declared}]
    scenarios = [sc for sc in declared if str(sc["id"]) in set(wanted_ids)] if wanted_ids else declared
    # The read oracles a SCOPED run re-runs beside its scenarios: the entry
    # points the caller named, selected from the admitted set exactly as the
    # scenario filter selects from the corpus -- an entry point nobody admitted
    # is a comparison that cannot be made, refused rather than skipped.
    oracle_ids = sorted({str(e) for e in (args.read_oracle or []) if str(e)})
    unknown_oracles = [e for e in oracle_ids if e not in set(wanted)]
    # whole phase (no scenario filter, default mode): every read oracle runs
    # and the option adds nothing; scoped: only the named ones; another mode:
    # none, whatever was named (the captures are default-mode)
    reads_all = not wanted_ids and security_mode == DEFAULT_SECURITY_MODE
    reads_some = sorted(e for e in oracle_ids if e in set(wanted)) if (wanted_ids and security_mode == DEFAULT_SECURITY_MODE) else []

    # --- what the destination is started with, and as whom it is asked ------
    # Both are read BEFORE anything is started: a switch nobody declared and a
    # credential this workspace does not hold are refusals that cost nothing
    # here and cost a whole phase after the destination is up.
    decided, decided_why = decided_security(root)
    # The enabled mode needs the switch set on the destination it starts; that
    # is the ADR-014 exit ("one artifact, restarted with the switch changed").
    # A destination someone else runs is theirs to configure, and a caller that
    # named the configuration itself has already said what it wants.
    from_decisions = bool(args.from_decisions
                          or (security_mode != DEFAULT_SECURITY_MODE and not dest_config and not args.dest_url))
    derived: dict[str, str] = {}
    derive_gap = ""
    if from_decisions:
        if not decided:
            derive_gap = decided_why
        else:
            derived = switch_config(decided, security_mode)
            if not derived:
                derive_gap = ("decisions.yaml declares no %s_value for the security switch"
                              % ("enabled" if security_mode != DEFAULT_SECURITY_MODE else "disabled"))
    # The caller's own --dest-config wins over the derived switch: the decision
    # is the default, not an override of what was asked for explicitly.
    dest_config = {**derived, **dest_config}
    # Every credential reference these requests may resolve: the ones the
    # Operator declared and the ones this mode's corpus names. A configuration
    # value that equals one of them would be written verbatim into the run
    # record, which is exactly what ADR-014 keeps credentials out of.
    credential_refs = sorted({str(i.get("credential_ref") or "") for i in ((decided or {}).get("identities") or [])
                              if str(i.get("credential_ref") or "")}
                             | ({str((decided or {}).get("invalid_credential_ref") or "")}
                                if (decided or {}).get("invalid_credential_ref") else set())
                             | set(corpus_credential_refs(scenarios)))
    config_conflicts = credential_conflicts(dest_config, credential_refs)
    # The identities the enabled-mode replay is made as, which the comparator
    # reads for itself at request time. This checks they are there; it never
    # reads what they hold.
    absent_credentials = (missing_credentials(corpus_credential_refs(scenarios))
                          if security_mode != DEFAULT_SECURITY_MODE else [])

    doc: dict[str, Any] = {
        "schema": SCHEMA, "producer": "run-parity.py", "at": _now(), "root": str(root),
        "dest_url": "", "started_by_runner": False, "reset_cmd": reset_cmd,
        "receipt_sha256": receipt["receipt_digest"] if receipt else "",
        "receipt_gaps": list(receipt_gaps or []),
        "issued": str(args.issued or ""),
        "binding": dict(binding) if binding else {"mode": "candidate", "gaps": list(binding_gaps)},
        "corpus": str(corpus_rel.as_posix()), "corpus_sha256": corpus_sha, "corpus_error": corpus_error,
        "scenario_filter": list(wanted_ids),
        # what this run is OF (ADR-014), and what it started the destination
        # with to make it so: the mode, the configuration verbatim, which of it
        # came from the decided switch, and which credential NAMES the replay
        # may resolve. No value of a credential is here, and none ever is.
        "security_mode": security_mode,
        "dest_config": dict(dest_config),
        "dest_config_from_decisions": sorted(derived),
        "dest_config_gap": derive_gap,
        "credential_refs": list(credential_refs),
        "artifact": artifact_identity(root),
        "scenarios": {"declared": len(declared), "selected": len(scenarios), "run": 0, "passed": 0, "failed": 0,
                      "inconclusive": 0, "results": []},
        # ``ran``: the WHOLE read-oracle phase ran (an unfiltered default-mode
        # run). ``rerun``: the entry points whose read oracle a SCOPED run
        # re-ran beside its scenarios (filled in as they record a verdict);
        # ``requested`` is what was asked. A reader that wants "was this entry
        # point's read oracle measured by this run" asks ran or membership.
        "read_oracles": {"ran": reads_all, "requested": list(oracle_ids), "rerun": [],
                         "reason": ("; ".join(
                             ([READ_ORACLES_FILTERED % (", ".join(wanted_ids),
                                                        (" except the read oracle(s) of %s, re-run for the card" % ", ".join(reads_some))
                                                        if reads_some else "")] if wanted_ids else [])
                             + ([READ_ORACLES_MODE % (DEFAULT_SECURITY_MODE, (ORACLES / "<slug>.json").as_posix(),
                                                      security_mode, DEFAULT_SECURITY_MODE)]
                                if security_mode != DEFAULT_SECURITY_MODE else [])))},
        "entry_points": {"admitted": len(wanted), "compared": 0, "passed": 0, "failed": 0, "inconclusive": 0,
                         "skipped": 0, "results": [], "not_compared": []},
        # the bounded navigation check (ADR-016): a separate measurement beside
        # the comparison, never inside it. "skipped" is what --no-navigation
        # records, so a reader can tell "nothing to navigate" (checked 0) from
        # "nobody looked".
        "navigation": ("skipped" if args.no_navigation else
                       {"ran": False, "max_hops": int(args.nav_max_hops), "dir": NAVIGATION.as_posix(),
                        "checked": 0, "ok": 0, "dead": 0, "loop": 0, "too_many_hops": 0,
                        "results": [], "not_navigated": []}),
        # the records in this mode's parity scenarios directory that do NOT
        # belong to this corpus, moved aside (never deleted) before the
        # composer reads it, with where they went
        "orphaned": {"pruned": 0, "dir": "", "records": [], "gaps": []},
        "compose": {"rc": None, "argv": []},
        "receipt_verdict": "", "failures": [], "ok": False,
    }
    out = root / run_record_path(security_mode)
    failures: list[str] = doc["failures"]
    if corpus_error:
        # The corpus is the only source of a write comparison. Its absence is
        # not an idle phase at M4: the scenario child could not run at all.
        failures.append("corpus: %s" % corpus_error)
    if unknown_ids:
        failures.append("scenario filter: %s is not declared by the corpus (%s); nothing was compared for it"
                        % (", ".join(unknown_ids), corpus_rel.as_posix()))
    if unknown_oracles:
        failures.append("read-oracle filter: %s is not an admitted entry point; nothing was compared for it"
                        % ", ".join(unknown_oracles))
    if binding_gaps:
        # The caller asked for a candidate-bound run and the binding cannot be
        # made: the children would each refuse for the same reason. Say it once,
        # here, rather than as N identical scenario refusals.
        failures.append("issued binding: %s" % "; ".join(binding_gaps))

    # --- what stops the run BEFORE anything is started ----------------------
    # These three are not results of a measurement; they are reasons no
    # measurement can be made. Discovering them after the destination is up
    # would spend the whole phase to learn what decisions.yaml and the
    # environment could have said at the start -- and, in the credential case,
    # would replay every enabled-mode scenario as nobody and record the 401s as
    # the destination's answer.
    preflight: list[str] = []
    if derive_gap:
        preflight.append("--from-decisions: %s" % derive_gap)
    if config_conflicts:
        preflight.append("--dest-config %s carries the value of a credential (%s); the run record is evidence, so a "
                         "credential reaches the destination through the environment variable that holds it and never as "
                         "a recorded property" % (", ".join(config_conflicts), ", ".join(credential_refs)))
    if absent_credentials:
        preflight.append("credential(s) %s are not set in this workspace; the %s-mode scenarios are replayed as the "
                         "identities the corpus names, and a credential is never invented nor a request quietly made as "
                         "nobody" % (", ".join(absent_credentials), security_mode))
    if preflight:
        failures.extend(preflight)
        doc["ok"] = False
        write_canonical(out, doc)
        for f in preflight:
            print("  - %s" % f, file=sys.stderr)
        print("REFUSE: PARITY_RUN nothing was started and nothing was compared → %s" % out, file=sys.stderr)
        return 1

    dest = None
    try:
        if args.dest_url:
            doc["dest_url"] = args.dest_url
            if dest_config:
                # Said plainly rather than left to be assumed from the presence
                # of the key: a destination someone else runs was started by
                # them, and this configuration reached nothing.
                doc["dest_config_note"] = ("a destination passed with --dest-url is started by someone else; this "
                                           "configuration is what the run was ASKED for, not what that destination runs")
        else:
            dest = Destination(root, args.port, args.java, args.ready_timeout, dest_config)
            print("starting the packaged destination on port %d ..." % args.port)
            err = dest.start()
            doc["dest_url"] = dest.base_url
            doc["started_by_runner"] = True
            doc["destination"] = {"port": args.port, "root_path": dest.root_path,
                                  "log": str(dest.log.relative_to(root)) if dest.log.is_file() else "",
                                  "profiles": list(dest.profiles), "db_kind": str(dest.ds.get("db_kind") or ""),
                                  "config": dict(dest.dest_config), "argv": list(dest.argv),
                                  "java": dict(dest.java_record)}
            if err:
                failures.append("destination: %s" % err)
                doc["destination"]["error"] = err
                write_canonical(out, doc)
                print("REFUSE: PARITY_RUN %s → %s" % (err, out), file=sys.stderr)
                return 1

        dest_url = doc["dest_url"]
        # H5b: the destination's log, and the byte span of it that each
        # comparison appends -- the request's window. The runner is the one
        # place that has the log and the window together, so a 5xx verdict is
        # given its exception here, before the composer reads the record.
        dest_log = dest.log if dest is not None else (Path(args.dest_log) if args.dest_log else None)
        doc["dest_log"] = _rel_or_empty(root, dest_log)

        def _log_mark() -> int:
            try:
                return dest_log.stat().st_size if dest_log is not None else 0
            except OSError:
                return 0

        def _server_error(record: Path, mark: int, row: dict[str, Any], label: str) -> None:
            if dest_log is None or row.get("verdict") != "FAIL":
                return
            se = annotate_record(root, record, dest_log, (mark, _log_mark()))
            if se is None:
                return
            row["server_error"] = {"exception": se.get("exception") or "", "matched": se.get("matched") or "",
                                   "files": [f["file"] for f in (se.get("frames") or [])]}
            print("  server error on %s: %s%s (%s)" % (
                label, se.get("exception") or "no exception block in the log",
                (" in " + ", ".join(sorted({f["file"] for f in (se.get("frames") or [])}))) if se.get("frames") else "",
                "matched by error id" if se.get("matched") == "error_id" else
                "last ERROR block in the request window" if se.get("matched") == "window" else se.get("note") or "unmatched"))

        # 1. every scenario the corpus declares, in corpus order
        for sc in scenarios:
            sid = str(sc["id"])
            argv_sc = [sys.executable, str(COMPARE_SCENARIO), "--root", str(root), "--scenario", sid,
                       "--dest-url", dest_url, "--reset-cmd", reset_cmd, *mode_argv, *issued_argv]
            mark = _log_mark()
            proc = _run_child(argv_sc, "scenario %s" % sid)
            record = root / parity_dir / (scenario_slug(sid) + ".json")
            verdict, reason = _verdict_of(record)
            row = {"id": sid, "entry_point": str(sc.get("entry_point") or ""), "rc": proc.returncode,
                   "verdict": verdict, "reason": reason[:300]}
            _server_error(record, mark, row, "scenario %s" % sid)
            doc["scenarios"]["results"].append(row)
            if not verdict:
                failures.append("scenario %s recorded no verdict (rc %d): %s"
                                % (sid, proc.returncode, ((proc.stderr or proc.stdout or "").strip()[-200:])))
                continue
            doc["scenarios"]["run"] += 1
            key = {"PASS": "passed", "FAIL": "failed"}.get(verdict, "inconclusive")
            doc["scenarios"][key] += 1

        # 2. every admitted entry point that has a captured read oracle -- or,
        #    when this run was scoped to named scenarios, only the entry points
        #    whose read oracle the caller asked to re-run beside them (the
        #    issued card's own); every other entry point is named as not
        #    compared, with the reason, and its record on disk is not touched
        to_compare = list(wanted) if reads_all else list(reads_some)
        for ep in to_compare:
            gap = read_oracle_gap(root, ep)
            if gap:
                doc["entry_points"]["skipped"] += 1
                doc["entry_points"]["not_compared"].append({"entry_point": ep, "reason": gap})
                continue
            argv_ep = [sys.executable, str(COMPARE_RUNTIME), "--root", str(root), "--entry-point", ep,
                       "--dest-url", dest_url, *issued_argv]
            mark = _log_mark()
            proc = _run_child(argv_ep, "entry point %s" % ep)
            record = root / PARITY / (slug(ep) + ".json")
            verdict, reason = _verdict_of(record)
            row_ep = {"entry_point": ep, "rc": proc.returncode, "verdict": verdict, "reason": reason[:300]}
            _server_error(record, mark, row_ep, "entry point %s" % ep)
            doc["entry_points"]["results"].append(row_ep)
            if not verdict:
                failures.append("entry point %s recorded no verdict (rc %d): %s"
                                % (ep, proc.returncode, ((proc.stderr or proc.stdout or "").strip()[-200:])))
                continue
            doc["entry_points"]["compared"] += 1
            key = {"PASS": "passed", "FAIL": "failed"}.get(verdict, "inconclusive")
            doc["entry_points"][key] += 1
            if not reads_all:
                # re-run for the card, and it recorded a verdict: the
                # acceptance path counts this entry point as re-measured
                doc["read_oracles"]["rerun"].append(ep)
        if not reads_all:
            compared_now = set(to_compare)
            for ep in wanted:
                if ep in compared_now:
                    continue
                doc["entry_points"]["skipped"] += 1
                doc["entry_points"]["not_compared"].append({"entry_point": ep, "reason": doc["read_oracles"]["reason"]})

        # 2b. the bounded navigation check, on the destination only, while it
        #     is still up -- after the comparisons and before the composer,
        #     which reads the records it leaves.
        if not args.no_navigation:
            run_navigation(root, scenarios, dest_url, args.nav_max_hops, doc["navigation"], parity_dir,
                           oracles_dir=scenario_oracles_dir(security_mode))
    finally:
        if dest is not None:
            dest.stop()

    # 2c. the records that do not belong to this corpus, moved aside before the
    #     composer reads the directory. A scoped run composes over every record
    #     on disk by design; an orphan left there would be judged as a scenario
    #     of this corpus and is not one.
    doc["orphaned"] = prune_orphaned_records(root, security_mode, corpus, corpus_sha, doc["at"])

    # 3. the receipt, once, last
    receipt_p = root / receipt_rel
    # the receipt as it stood BEFORE the composer ran: what tells a receipt
    # this run composed apart from the one a refusing composer left behind
    before_stamp = _file_stamp(receipt_p)
    argv_rc = [sys.executable, str(COMPOSE_RECEIPT), "--root", str(root), *mode_argv, *issued_argv]
    proc = _run_child(argv_rc, "compose-parity-receipt")
    doc["compose"] = {"rc": proc.returncode, "argv": argv_rc[1:]}
    after_stamp = _file_stamp(receipt_p)
    composed_doc: Any = None
    if after_stamp.get("present"):
        try:
            composed_doc = load_json(receipt_p)
        except (OSError, ValueError):
            composed_doc = None
    not_ours = _composed_by_this_run(before_stamp, after_stamp, composed_doc, binding, expected_receipt_sha,
                                     proc.returncode)
    verdict, _ = _verdict_of(receipt_p)
    # A verdict this run did not produce is not this run's measurement. The
    # runner reports the receipt's verdict, and that report is read as the
    # phase's outcome; reporting the previous receipt's verdict after a
    # composer that refused is a false green, so there is nothing to report.
    doc["receipt"] = {"path": str(receipt_p.relative_to(root)), "composed_by_this_run": not not_ours,
                      "reason": not_ours}
    doc["receipt_verdict"] = verdict if not not_ours else None
    if not_ours:
        failures.append("receipt not composed by this run: %s%s"
                        % (not_ours, (" :: " + (proc.stderr or proc.stdout or "").strip()[-300:])
                           if (proc.stderr or proc.stdout or "").strip() else ""))

    doc["ok"] = not failures
    write_canonical(out, doc)
    nav_doc = doc["navigation"]
    nav_summary = ("navigation skipped" if nav_doc == "skipped" else
                   "%d redirect target(s) navigated (%d ok, %d dead, %d loop, %d too many hops)"
                   % (nav_doc["checked"], nav_doc["ok"], nav_doc["dead"], nav_doc["loop"], nav_doc["too_many_hops"]))
    pruned = ("; %d orphaned record(s) moved to %s" % (doc["orphaned"]["pruned"], doc["orphaned"]["dir"])
              if doc["orphaned"]["pruned"] else "")
    reruns = (" (read oracle(s) re-run for the card: %s)" % ", ".join(doc["read_oracles"]["rerun"])
              if doc["read_oracles"]["rerun"] else "")
    summary = ("%s%s%d/%d scenario(s) run (%d PASS, %d FAIL, %d INCONCLUSIVE); %d/%d entry point(s) compared "
               "(%d not compared)%s; %s; receipt %s%s"
               % (("%s mode: " % security_mode) if security_mode != DEFAULT_SECURITY_MODE else "",
                  ("scoped to %s: " % ", ".join(wanted_ids)) if wanted_ids else "",
                  doc["scenarios"]["run"], doc["scenarios"]["selected"], doc["scenarios"]["passed"],
                  doc["scenarios"]["failed"], doc["scenarios"]["inconclusive"], doc["entry_points"]["compared"],
                  doc["entry_points"]["admitted"], doc["entry_points"]["skipped"], reruns, nav_summary,
                  doc["receipt_verdict"] or "NOT COMPOSED BY THIS RUN", pruned))
    for row in doc["entry_points"]["not_compared"]:
        print("  - not compared: %s (%s)" % (row["entry_point"], row["reason"]))
    if failures:
        for f in failures:
            print("  - %s" % f, file=sys.stderr)
        print("REFUSE: PARITY_RUN %s → %s" % (summary, out), file=sys.stderr)
        return 1
    # The receipt's verdict is the measurement, not this runner's grade.
    print("OK: PARITY_RUN %s → %s" % (summary, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
