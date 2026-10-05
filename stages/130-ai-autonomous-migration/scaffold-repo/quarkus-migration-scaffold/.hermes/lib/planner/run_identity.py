"""Does this endpoint belong to THIS run? Decided by parsing, never by matching.

Every migration run owns its own parity database, its own credentials secret
and its own fixture identities. The property that keeps two runs apart is not
that the names differ -- it is that nothing destructive happens until the
endpoint the environment actually carries has been taken apart and compared,
field by field, with the assignment the platform issued for this run.

A substring test cannot do that, and the four counterexamples the architect
raised on 2026-09-22 are all substring passes:

  * the right service name in the WRONG NAMESPACE
    (jdbc:postgresql://r-db.other-ns.svc:5432/parity);
  * the right server and the WRONG DATABASE
    (jdbc:postgresql://r-db.ns.svc:5432/somebody-else);
  * a DIFFERENT HOST whose name merely starts with the expected one
    (jdbc:postgresql://r-db-old.ns.svc:5432/parity);
  * ANOTHER HOST ENTIRELY carrying the expected name only in a query
    parameter (jdbc:postgresql://elsewhere:5432/parity?ApplicationName=r-db).

So the URL is parsed into engine, host, port and database, the host is reduced
to (service, namespace) through the DNS forms Kubernetes actually gives the
same Service, and each field is compared for EQUALITY with the assignment.
Nothing here reads, prints or returns a credential value.

THREE STATEMENTS MUST AGREE, and they come from three different places:

  1. the ASSIGNMENT -- migration.yaml `resources`, stamped into the run's
     repository by the RHDH app-migration template at initiation. It says
     which database this run was assigned;
  2. the RECEIPT -- `PARITY_RUN_RECEIPT`, written into the run's workspace
     secret by the trusted platform provisioner and delivered by DevWorkspace
     Operator targeted automount. It says which database the platform
     actually created, for which run, from which scaffolding commit. Delivery
     is a platform trust assumption, not an environment-variable sandbox;
  3. the ENDPOINT -- the URL the workspace is holding right now, under the
     variable name the decision records.

An assignment alone is a string the repository contains, so it is never proof.
A receipt alone says what was created, not what this process is about to
connect to. The endpoint alone says nothing about whose it is. Ownership is
the agreement of all three.

TYPED OUTCOMES. Each is a distinct finding and they are not interchangeable:

  OK                              this run's own resources, proceed
  RUN_RESOURCES_LEGACY            an existing workspace explicitly listed in
                                  the platform-owned legacy assignments file;
                                  full endpoint checks still apply
  RUN_RESOURCES_UNASSIGNED        no current or authorized legacy assignment:
                                  this run was never given a database
  RUN_RESOURCES_MISSING           assigned, but the workspace holds none of
                                  the variables. The resources may not exist
                                  yet. Static analysis may continue; anything
                                  that touches the database may not
  RUN_RESOURCES_RECEIPT_MISSING   assigned, endpoint present, but the platform
                                  receipt is absent: unprovable ownership
  RUN_RESOURCES_RECEIPT_MISMATCH  the receipt describes another run
  RUN_RESOURCES_UNPARSEABLE       the endpoint is not a JDBC URL of the
                                  decided engine
  RUN_RESOURCES_MISMATCH          parsed and compared: this is not this run's
                                  database

Every outcome except OK and RUN_RESOURCES_LEGACY blocks resource-dependent
work. `blocking_for("analysis")` is False for RUN_RESOURCES_MISSING alone --
the one case the architect allows to proceed, and only for work that never
connects.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from planner.decisions import datasource, load_decisions
from planner.paths import DECISIONS, MIGRATION
from planner.yamlite import load_yaml

UNSTAMPED = "UNSTAMPED"
RECEIPT_ENV = "PARITY_RUN_RECEIPT"
RUN_NAME_ENV = "MIGRATION_RUN_NAME"
WORKSPACE_ENV = "DEVWORKSPACE_NAME"
# Platform-owned compatibility data, never a file from the destination tree.
# Empty/absent by default: a concrete datasource is not legacy authorization.
LEGACY_ASSIGNMENTS = Path("/etc/hermes/migration-legacy-assignments.json")
DEFAULT_PORTS = {"postgresql": 5432, "mysql": 3306, "mariadb": 3306, "mssql": 1433, "h2": 0}

OK = "OK"
LEGACY = "RUN_RESOURCES_LEGACY"
UNASSIGNED = "RUN_RESOURCES_UNASSIGNED"
MISSING = "RUN_RESOURCES_MISSING"
RECEIPT_MISSING = "RUN_RESOURCES_RECEIPT_MISSING"
RECEIPT_MISMATCH = "RUN_RESOURCES_RECEIPT_MISMATCH"
UNPARSEABLE = "RUN_RESOURCES_UNPARSEABLE"
MISMATCH = "RUN_RESOURCES_MISMATCH"

#: outcomes that never block; everything else blocks resource-dependent work
PERMITTED = (OK, LEGACY)
#: the one outcome that still permits work which never connects
ANALYSIS_ONLY = (MISSING,)


class Verdict:
    """One typed ownership finding. `code` is the finding; `ok` is the answer."""

    __slots__ = ("code", "detail", "assignment", "observed")

    def __init__(self, code: str, detail: str, assignment: dict | None = None,
                 observed: dict | None = None) -> None:
        self.code = code
        self.detail = detail
        self.assignment = assignment or {}
        self.observed = observed or {}

    @property
    def ok(self) -> bool:
        return self.code in PERMITTED

    def blocking_for(self, operation: str) -> bool:
        """Does this finding forbid `operation`?

        Resource-dependent operations (reset, revert, fixture, startup,
        parity) are blocked by everything but OK/LEGACY. `analysis` is the
        architect's exception and is blocked only when the endpoint is
        actively wrong, never merely absent."""
        if self.ok:
            return False
        if operation == "analysis":
            return self.code not in ANALYSIS_ONLY
        return True

    def __str__(self) -> str:
        return self.detail if self.code in PERMITTED else "%s %s" % (self.code, self.detail)


def _dict(value: Any) -> dict:
    return dict(value) if isinstance(value, dict) else {}


def _decided_datasource(root: Path) -> dict:
    """The decided datasource, read the strict way when the tree allows it.

    Whether the ADR is accepted is M2's question, not this one: an endpoint
    belongs to a run or it does not, and refusing to answer because the
    contract schemas are absent would turn a wrong target into an exception
    rather than a refusal. So the validating loader is tried first and a plain
    read is the fallback."""
    try:
        ds = datasource(load_decisions(root))
        if ds:
            return ds
    except Exception:  # noqa: BLE001 - any unreadable contract falls back
        pass
    return _dict(_dict(load_yaml(root / DECISIONS) if (root / DECISIONS).is_file() else {}).get("datasource"))


def _split_instance(instance: str) -> tuple[str, str]:
    """`<service>.<namespace>` -> (service, namespace); a bare name -> (name, "")."""
    text = str(instance or "").strip().rstrip(".")
    if "." in text:
        service, namespace = text.split(".", 1)
        namespace = namespace.split(".", 1)[0]
        return service, namespace
    return text, ""


def assignment(root: Path, environ: dict | None = None) -> dict:
    """What the platform assigned this run, or {} when nothing was assigned.

    Legacy compatibility requires an explicit platform assignment keyed by the
    actual workspace. Neither a missing resources block nor a stamped instance
    can create that authorization.
    """
    root = Path(root)
    doc = load_yaml(root / MIGRATION) if (root / MIGRATION).is_file() else {}
    res = _dict(_dict(doc).get("resources"))
    ds = _decided_datasource(root)
    if res:
        db = _dict(res.get("parity_database"))
        service, namespace = _split_instance(db.get("instance"))
        fixtures = _dict(res.get("fixture_credentials"))
        return {
            "legacy": False,
            "run": str(res.get("run") or ""),
            "namespace": str(res.get("namespace") or namespace),
            "engine": str(ds.get("db_kind") or "postgresql"),
            "instance": str(db.get("instance") or ""),
            "service": service,
            "service_namespace": namespace,
            "port": int(db.get("port") or DEFAULT_PORTS.get(str(ds.get("db_kind") or "postgresql"), 0) or 5432),
            "database": str(db.get("database") or ""),
            "server_secret": str(db.get("server_secret") or ""),
            "workspace_secret": str(db.get("workspace_secret") or ""),
            "fixture_secret": str(fixtures.get("secret") or ""),
            "fixture_env": [str(x) for x in (fixtures.get("env") or [])],
            "url_env": str(db.get("jdbc_url_env") or ds.get("jdbc_url_env") or ""),
            "user_env": str(db.get("username_env") or ds.get("username_env") or ""),
            "password_env": str(db.get("password_env") or ds.get("password_env") or ""),
        }
    env = _env(environ)
    workspace = env.get(WORKSPACE_ENV, "")
    try:
        legacy = _dict(_dict(json.loads(LEGACY_ASSIGNMENTS.read_text())).get(workspace))
    except (OSError, ValueError):
        legacy = {}
    instance = str(ds.get("instance") or "")
    if (workspace and legacy and legacy.get("instance") == instance
            and legacy.get("database") and legacy.get("port")
            and legacy.get("engine") == ds.get("db_kind")
            and env.get("DEVWORKSPACE_NAMESPACE") == _split_instance(instance)[1]
            and not env.get(RECEIPT_ENV) and not env.get(RUN_NAME_ENV)):
        service, namespace = _split_instance(instance)
        return {
            "legacy": True,
            "run": workspace,
            "namespace": namespace,
            "engine": str(ds.get("db_kind") or "postgresql"),
            "instance": instance,
            "service": service,
            "service_namespace": namespace,
            "port": int(legacy["port"]),
            "database": str(legacy["database"]),
            "server_secret": "",
            "workspace_secret": "",
            "fixture_secret": "",
            "fixture_env": [],
            "url_env": str(ds.get("jdbc_url_env") or ""),
            "user_env": str(ds.get("username_env") or ""),
            "password_env": str(ds.get("password_env") or ""),
        }
    return {}


_JDBC = re.compile(r"^jdbc:(?P<engine>[a-z0-9]+):(?P<rest>.*)$", re.IGNORECASE)


def parse_endpoint(url: str) -> dict:
    """jdbc:<engine>://<host>[:<port>]/<database>[?...|;...] -> parts, or {}.

    Query and semicolon properties are SPLIT OFF and never searched: the whole
    point is that `?ApplicationName=<this run's server>` appended to somebody
    else's host must not look like this run's database."""
    m = _JDBC.match(str(url or "").strip())
    if not m:
        return {}
    engine = m.group("engine").lower()
    rest = m.group("rest")
    if not rest.startswith("//"):
        return {}
    rest = rest[2:]
    # properties first, so nothing inside them can be read as an authority
    for sep in ("?", ";"):
        rest = rest.split(sep, 1)[0]
    if "@" in rest.split("/", 1)[0]:  # credentials in the authority: never accepted
        return {}
    authority, _, database = rest.partition("/")
    database = database.strip("/")
    host, port = authority, 0
    if authority.startswith("["):  # IPv6 literal
        close = authority.find("]")
        if close < 0:
            return {}
        host, tail = authority[: close + 1], authority[close + 1:]
        if tail.startswith(":"):
            tail = tail[1:]
            if not tail.isdigit():
                return {}
            port = int(tail)
        elif tail:
            return {}
    elif ":" in authority:
        host, _, tail = authority.partition(":")
        if not tail.isdigit():
            return {}
        port = int(tail)
    host = host.strip().rstrip(".").lower()
    if not host:
        return {}
    return {"engine": engine, "host": host, "port": port or DEFAULT_PORTS.get(engine, 0),
            "database": database}


def host_forms(service: str, namespace: str, same_namespace: bool) -> list[str]:
    """Every DNS name Kubernetes gives THIS Service, and no other.

    `same_namespace` decides whether the bare service name is one of them: a
    short name resolves in the caller's namespace, so it names this run's
    server only when the caller runs where the server does."""
    service = str(service or "").lower()
    namespace = str(namespace or "").lower()
    if not service:
        return []
    forms = []
    if same_namespace:
        forms.append(service)
    if namespace:
        forms += ["%s.%s" % (service, namespace),
                  "%s.%s.svc" % (service, namespace),
                  "%s.%s.svc.cluster.local" % (service, namespace)]
    return forms


def parse_receipt(text: str) -> dict:
    """`k=v;k=v` from the platform provisioner. Unknown keys are kept, not read."""
    out: dict[str, str] = {}
    for part in str(text or "").replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        out[key.strip().lower()] = value.strip()
    return out


def _env(environ: dict | None) -> dict:
    return dict(os.environ if environ is None else environ)


def check(root: Path, environ: dict | None = None) -> Verdict:
    """The one ownership decision. Every destructive entry point calls this."""
    env = _env(environ)
    want = assignment(root, env)
    if not want:
        return Verdict(UNASSIGNED,
                       "this destination names no parity database: migration.yaml declares no "
                       "resources.parity_database and has no platform-authorized legacy assignment. "
                       "Re-create the destination from the app-migration template; nothing may connect "
                       "to a database this run was never assigned")

    url_env = want["url_env"]
    if not url_env:
        return Verdict(UNASSIGNED,
                       "the decided datasource names no jdbc_url_env, so there is no endpoint to own")
    url = env.get(url_env, "")
    creds = [n for n in (want["user_env"], want["password_env"]) if n]
    if not url or any(not env.get(n) for n in creds):
        absent = [n for n in [url_env] + creds if not env.get(n)]
        return Verdict(MISSING,
                       "%s not set in this environment (secret %s). This run's resources may not exist "
                       "yet, or this workspace started before they did: static analysis may continue, "
                       "nothing that connects to the database may"
                       % (", ".join(absent), want["workspace_secret"] or "<the run's workspace secret>"),
                       want)

    parts = parse_endpoint(url)
    if not parts:
        return Verdict(UNPARSEABLE,
                       "%s is set but is not a JDBC URL this check can take apart; an endpoint that "
                       "cannot be parsed cannot be shown to belong to this run" % url_env, want)
    if parts["engine"] != str(want["engine"]).lower():
        return Verdict(MISMATCH,
                       "%s names a %s endpoint and the decided engine is %s"
                       % (url_env, parts["engine"], want["engine"]), want, parts)

    # The receipt: what the platform says it created, for whom. A pre-per-run
    # destination has none and is judged under the legacy exception below.
    receipt = parse_receipt(env.get(RECEIPT_ENV, ""))
    if not want["legacy"]:
        if not receipt:
            return Verdict(RECEIPT_MISSING,
                           "%s is set but %s is not: the platform issued no provisioning receipt for "
                           "this workspace, so the endpoint cannot be shown to be this run's. The "
                           "receipt is written by the platform provisioner into %s"
                           % (url_env, RECEIPT_ENV, want["workspace_secret"] or "the run's workspace secret"),
                           want, parts)
        disagreements = []
        for key, expected in (("run", want["run"]), ("namespace", want["namespace"]),
                              ("host", want["service"]), ("database", want["database"]),
                              ("port", str(want["port"])), ("workspace", want["run"]),
                              ("engine", want["engine"])):
            got = receipt.get(key, "")
            if expected and got != expected:
                disagreements.append("%s %r, assigned %r" % (key, got, expected))
        if disagreements:
            return Verdict(RECEIPT_MISMATCH,
                           "the provisioning receipt in this workspace describes a different run than "
                           "migration.yaml assigns (%s). One of the two is another run's; nothing "
                           "connects until they agree" % "; ".join(disagreements), want, parts)
        run_name = env.get(RUN_NAME_ENV, "")
        if (run_name != want["run"] or env.get(WORKSPACE_ENV) != want["run"]
                or env.get("DEVWORKSPACE_NAMESPACE") != want["namespace"]):
            return Verdict(RECEIPT_MISMATCH,
                           "workspace name, namespace and MIGRATION_RUN_NAME must match the assignment",
                           want, parts)

    same_namespace = bool(receipt.get("namespace")) and receipt.get("namespace") == want["service_namespace"]
    if want["legacy"]:
        # No receipt exists for a pre-per-run destination, and the namespace it
        # runs in is the namespace its instance names.
        same_namespace = True
    forms = host_forms(want["service"], want["service_namespace"], same_namespace)
    if parts["host"] not in forms:
        return Verdict(MISMATCH,
                       "%s names host %r, and this run's database is %s. Not a different spelling of "
                       "the same Service -- a different server. Nothing is reset, started or compared "
                       "against it" % (url_env, parts["host"], want["instance"]), want, parts)
    if want["port"] and parts["port"] and parts["port"] != want["port"]:
        return Verdict(MISMATCH,
                       "%s names port %d on this run's host and this run's database listens on %d"
                       % (url_env, parts["port"], want["port"]), want, parts)
    if want["database"] and parts["database"] != want["database"]:
        return Verdict(MISMATCH,
                       "%s names database %r on this run's server and this run was assigned %r"
                       % (url_env, parts["database"], want["database"]), want, parts)

    if want["legacy"]:
        return Verdict(LEGACY,
                       "platform-authorized legacy workspace: %s names the assigned instance (%s); "
                       "engine, host, namespace, port and database match its explicit assignment"
                       % (url_env, want["instance"]), want, parts)
    # The scaffolding push is an existing ancestor, and its resource declaration
    # must still be the one the workspace presents. No abbreviated/fabricated SHA.
    scaffold = receipt.get("scaffold", "")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", scaffold):
        return Verdict(RECEIPT_MISMATCH, "receipt has no full scaffolding commit", want, parts)
    try:
        subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", scaffold, "HEAD"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        original = subprocess.run(["git", "-C", str(root), "show", scaffold + ":" + str(MIGRATION)],
                                  check=True, capture_output=True, text=True, timeout=10).stdout
        try:
            from yaml import safe_load as yaml_loads
        except ImportError:
            from planner.yamlite import loads as yaml_loads
        if _dict(yaml_loads(original)).get("resources") != _dict(load_yaml(root / MIGRATION)).get("resources"):
            return Verdict(RECEIPT_MISMATCH, "resource assignment differs from the scaffolding commit", want, parts)
    except (OSError, subprocess.SubprocessError, ValueError):
        return Verdict(RECEIPT_MISMATCH, "scaffolding commit/assignment cannot be verified in this repository", want, parts)
    return Verdict(OK,
                   "%s names this run's own database: %s port %d database %r, agreed by the "
                   "assignment in migration.yaml and the platform receipt for run %s"
                   % (url_env, want["instance"], parts["port"], parts["database"], want["run"]),
                   want, parts)


def require(root: Path, operation: str, environ: dict | None = None) -> Verdict:
    """Raise SystemExit with the typed code when `operation` may not proceed."""
    verdict = check(root, environ)
    if verdict.blocking_for(operation):
        raise SystemExit("FAIL: %s %s cannot proceed: %s" % (verdict.code, operation, verdict.detail))
    return verdict


def fixture_gaps(root: Path, environ: dict | None = None) -> list[str]:
    """Fixture identity variables this run was assigned and did not receive."""
    env = _env(environ)
    want = assignment(root)
    return [n for n in (want.get("fixture_env") or []) if not env.get(n)]


def main(argv: list[str] | None = None) -> int:
    """`python3 -m planner.run_identity --root <dest> --operation reset`.

    The shell half of the same decision: reset-parity-db.sh and the workspace
    postStart call this before anything opens a connection. Exit 0 permitted,
    1 refused, 2 usage. The typed code is the first word of the output so a
    caller can branch on it without parsing prose."""
    import argparse

    ap = argparse.ArgumentParser(description="Refuse a database that is not this run's, before connecting.")
    ap.add_argument("--root", required=True)
    ap.add_argument("--operation", default="reset",
                    help="what is about to happen (reset, revert, fixture, startup, parity, analysis)")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("FAIL: --root must be an existing directory", file=__import__("sys").stderr)
        return 2
    verdict = check(root)
    blocked = verdict.blocking_for(args.operation)
    result = "REFUSE: " + verdict.code if blocked else verdict.code + ":"
    line = "%s %s %s" % (result, args.operation, verdict.detail)
    print(line, file=__import__("sys").stderr if blocked else None)
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
