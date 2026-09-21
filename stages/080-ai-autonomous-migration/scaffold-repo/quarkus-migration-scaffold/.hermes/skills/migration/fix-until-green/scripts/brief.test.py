#!/usr/bin/env python3
"""brief.py enrichment selftest: the brief carries the tools' facts per item kind.

pom items: advised artifacts present / unmanaged with the managed equivalent (catalog aliases).
compile items: the diagnostic, the inventory row for a missing legacy type, the Jakarta rename
for a javax.* package, the spring-to-quarkus-patterns reference that covers the symbol.
config items: the property line, the incident variables, the catalog mapping (key and value).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))
from brief import enrich  # noqa: E402
from planner.canonical import write_canonical  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _repository_inventory_case() -> int:
    """A *Repository.java brief names every declared method and what it extends."""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("brief_mod", HERE / "brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="repoinv-") as td:
        root = Path(td)
        f = root / "src" / "main" / "java" / "a" / "UserRepository.java"
        f.parent.mkdir(parents=True)
        f.write_text("package a;\npublic interface UserRepository extends JpaRepository<User, Long> {\n"
                     "    @Query(\"SELECT u FROM User u\")\n"
                     "    List<User> findAll();\n"
                     "    void save(User u);\n}\n", encoding="utf-8")
        inv = mod.repository_inventory(root, "src/main/java/a/UserRepository.java")
        names = {m["name"] for m in (inv or {}).get("methods") or []}
        if inv is None or "JpaRepository" not in (inv.get("extends") or "") or names != {"findAll", "save"}:
            return _fail("repository inventory must list extends + methods: %s" % inv)
        finder = next(m for m in inv["methods"] if m["name"] == "findAll")
        if not finder.get("query") or finder.get("modifying"):
            return _fail("findAll must be marked @Query: %s" % finder)
        if "one transformation" not in (inv.get("batch") or ""):
            return _fail("inventory must carry the batching rule: %s" % inv.get("batch"))
        if mod.repository_inventory(root, "src/main/java/a/ClinicService.java") is not None:
            return _fail("non-repository paths have no inventory")
    return 0


def _runtime_advice_case() -> int:
    """A packaging obligation names one member; the brief names the rest."""
    import importlib.util
    import tempfile
    spec = importlib.util.spec_from_file_location("brief_mod", HERE / "brief.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    with tempfile.TemporaryDirectory(prefix="rtadv-") as td:
        root = Path(td)
        f = root / "src" / "main" / "java" / "a" / "UserRepository.java"
        f.parent.mkdir(parents=True)
        f.write_text("package a;\npublic interface UserRepository {\n"
                     "    void save(User u);\n    void delete(User u);\n    User findById(int id);\n}\n", encoding="utf-8")
        item = {"source": "runtime", "gate": "package", "cause": "underivable-query-method", "member": "save",
                "path": "src/main/java/a/UserRepository.java", "message": "Method 'save' cannot be parsed"}
        adv = mod.runtime_advice(item, root)
        if adv.get("siblings") != ["delete", "findById"]:
            return _fail("the brief must name the other declared members: %s" % adv.get("siblings"))
        if "another full verification" not in adv.get("sibling_note", ""):
            return _fail("and say why fixing them together matters: %s" % adv.get("sibling_note"))
        # the answer already in the tree: the same member, annotated, elsewhere
        other = root / "src" / "main" / "java" / "a" / "SpringDataUserRepository.java"
        other.write_text("package a;\npublic interface SpringDataUserRepository extends UserRepository {\n"
                         "    @Override\n    @Query(\"SELECT u FROM User u\")\n    void save(User u);\n}\n", encoding="utf-8")
        adv = mod.runtime_advice(item, root)
        refs = adv.get("declared_elsewhere") or []
        if not refs or refs[0]["path"] != "src/main/java/a/SpringDataUserRepository.java" or "@Query" not in refs[0]["snippet"]:
            return _fail("the brief must show where the member is declared elsewhere, with its annotations: %s" % refs)
        if "already present in this destination" not in adv.get("elsewhere_note", ""):
            return _fail("and say that it is not something to invent: %s" % adv.get("elsewhere_note"))
        # the query the destination cannot see, because a retirement removed it
        frozen = root / ".derived" / "frozen-input" / "src" / "main" / "java" / "a" / "jpa" / "JpaUserRepositoryImpl.java"
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text("package a.jpa;\npublic class JpaUserRepositoryImpl {\n"
                          "    public void save(User u) {\n"
                          "        this.em.createQuery(\"SELECT u FROM User u ORDER BY u.id\");\n    }\n}\n", encoding="utf-8")
        adv = mod.runtime_advice(item, root)
        fi = adv.get("frozen_implementations") or []
        if not fi or fi[0]["query"] != "SELECT u FROM User u ORDER BY u.id":
            return _fail("the brief must carry the frozen implementation and its query: %s" % fi)
        if "rather than writing one" not in adv.get("frozen_note", ""):
            return _fail("and say why it is there: %s" % adv.get("frozen_note"))

        # a write must not be "repaired" with a bare @Query
        if "not a repair for it" not in (adv.get("caution") or ""):
            return _fail("a write needs the caution: %s" % adv.get("caution"))
        read = mod.runtime_advice({"source": "runtime", "gate": "package", "cause": "underivable-query-method",
                                   "member": "findByLastName", "path": "src/main/java/a/UserRepository.java",
                                   "message": "Method 'findByLastName' of repository"}, root)
        if read.get("caution"):
            return _fail("a finder is not a write and needs no such caution: %s" % read.get("caution"))
        bare = mod.runtime_advice({"source": "runtime", "gate": "boot", "cause": "datasource-unconfigured",
                                   "path": "src/main/resources/application.properties", "message": "x"}, root)
        if bare.get("siblings"):
            return _fail("a failure that names no member has no siblings to name: %s" % bare)
    return 0


def _issued_cluster_case() -> int:
    """After a bounce the work-list head can be empty while issued.json still
    names this card. The brief must serve THAT cluster, not LOOP_NO_OPEN_CLUSTER."""
    import io
    from contextlib import redirect_stderr

    from brief import select_cluster
    from planner.paths import LOOP_ISSUED, WORKLIST

    with tempfile.TemporaryDirectory(prefix="issued-brief-") as td:
        root = Path(td)
        cluster = {"id": "c:issued", "kind": "compile", "path": "src/main/java/A.java",
                   "write_set": ["src/main/java/A.java"], "items": ["err:1"]}
        wl = {"schema": "rhoai3.worklist/v1", "head": "", "measure": {"tuple": [0, 1, 0], "known": True, "blocked": []},
              "clusters": [cluster], "items": [{"id": "err:1", "source": "javac", "kind": "compile",
                                                "category": "mandatory", "path": "src/main/java/A.java", "line": 1,
                                                "rule_id": "compiler.err.cant.resolve.location", "message": "x"}],
              "not_counted": []}
        write_canonical(root / WORKLIST, wl)
        write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "c:issued", "task_id": "t_abc12345"})
        hit, code, _ = select_cluster(wl, root, "", "t_abc12345")
        if hit is None or hit["id"] != "c:issued" or code:
            return _fail("issued cluster must win over an empty head: %s %s" % (hit, code))
        hit, code, detail = select_cluster(wl, root, "", "t_other000")
        if hit is not None or code != "LOOP_WRONG_CARD":
            return _fail("a different HERMES_KANBAN_TASK is LOOP_WRONG_CARD: %s %s" % (code, detail))
        hit, code, detail = select_cluster(wl, root, "", "")
        if hit is not None or code != "LOOP_NO_OPEN_CLUSTER" or "kanban_block" not in detail:
            return _fail("empty head with no task env is LOOP_NO_OPEN_CLUSTER with a terminator: %s %s" % (code, detail))
        gone = dict(wl, clusters=[])
        # G2 (v9 t_55220d84): the issued card's OWN cluster is never "not open"
        # to it -- a mid-card rebuild measured its obligations gone, and
        # advance.py is the judge; the worker must not block
        hit, code, detail = select_cluster(gone, root, "", "t_abc12345")
        if hit is None or code or hit["id"] != "c:issued" or "advance.py" not in (hit.get("not_open") or {}).get("next", ""):
            return _fail("the issued cluster missing from the list is served with advance as the next step: %s %s" % (code, hit))
        hit, code, detail = select_cluster(gone, root, "c:issued", "t_abc12345")
        if hit is None or code or "kanban_block for this" not in hit["not_open"]["next"]:
            return _fail("--cluster naming the issued cluster is served the same way: %s %s" % (code, hit))
        hit, code, detail = select_cluster(gone, root, "c:other", "")
        if hit is not None or code != "LOOP_CLUSTER_NOT_OPEN" or "kanban_block" not in detail:
            return _fail("a cluster that is neither open nor issued is still LOOP_CLUSTER_NOT_OPEN: %s %s" % (code, detail))
        write_canonical(root / WORKLIST, gone)
        os.environ["HERMES_KANBAN_TASK"] = "t_abc12345"
        try:
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), __import__("contextlib").redirect_stdout(out):
                rc = __import__("brief").main(["--root", str(root)])
        finally:
            os.environ.pop("HERMES_KANBAN_TASK", None)
        if rc != 0 or '"issued_not_open"' not in out.getvalue() or "advance.py" not in out.getvalue():
            return _fail("brief.py exits 0 and tells the card to run advance: rc=%s %s %s" % (rc, out.getvalue()[:300], err.getvalue()[:300]))
        write_canonical(root / WORKLIST, wl)
        prev = os.environ.get("HERMES_KANBAN_TASK")
        os.environ.pop("HERMES_KANBAN_TASK", None)
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                rc = __import__("brief").main(["--root", str(root)])
            if rc != 1 or "LOOP_NO_OPEN_CLUSTER" not in buf.getvalue():
                return _fail("brief.py on empty head refuses LOOP_NO_OPEN_CLUSTER: rc=%s %s" % (rc, buf.getvalue()))
            os.environ["HERMES_KANBAN_TASK"] = "t_abc12345"
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), __import__("contextlib").redirect_stdout(out):
                rc = __import__("brief").main(["--root", str(root)])
            if rc != 0:
                return _fail("brief.py with matching task serves the issued cluster: rc=%s %s" % (rc, err.getvalue()))
            if '"c:issued"' not in out.getvalue():
                return _fail("brief.py must print the issued cluster: %s" % out.getvalue()[:400])
        finally:
            if prev is None:
                os.environ.pop("HERMES_KANBAN_TASK", None)
            else:
                os.environ["HERMES_KANBAN_TASK"] = prev
    return 0


def _unit_brief_case() -> int:
    """A unit card's brief carries what one coherent repair covers: the members
    grouped under the rule that formed them and each with its current verdict,
    the documented targets with the catalogue rows that document them, the
    completion checks with the tool that decides each, and the one rule that
    makes a coordinated repair possible -- intermediate regressions inside the
    sealed symbols are allowed until the checkpoint."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from planner.canonical import load_json
    from planner.paths import LOOP_DIR, LOOP_ISSUED, WORKLIST
    from planner.worklist import batch_scope_digest

    with tempfile.TemporaryDirectory(prefix="unit-brief-") as td:
        root = Path(td)
        rel = "src/main/java/p/OwnerResource.java"
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("package p;\npublic class OwnerResource { }\n", encoding="utf-8")
        scope = {
            "schema": "rhoai3.batch-scope/v4", "kind": "unit", "rule": "unit/diagnostic-family/v1",
            "cluster": "u:abc123", "unit_id": "u:abc123",
            "family_key": "org.springframework.web.util.UriComponentsBuilder",
            "writable_paths": [rel],
            "symbols": [{"kind": "type", "fqn": "org.springframework.web.util.UriComponentsBuilder", "path": rel}],
            "target_symbols": [{"from": "org.springframework.web.util.UriComponentsBuilder",
                                "to": "jakarta.ws.rs.core.UriBuilder",
                                "catalog_row": {"catalog": "compat-mapping.json", "block": "symbol_renames",
                                                "key": "org.springframework.web.util.UriComponentsBuilder",
                                                "kind": "type", "source": "https://quarkus.io/"}}],
            "members": [{"path": rel, "type": "p.OwnerResource", "member_id": "", "occurrence": 0,
                         "state": "reported", "identity": "diag:a"}],
            "evidence": [{"kind": "javac", "ref": "%s names UriComponentsBuilder" % rel}],
            "completion": [{"check": "identities-gone", "tool": "javac", "detail": "every sealed identity is gone"},
                           {"check": "unit-assessment", "tool": "worklist.assess_unit", "detail": "no member violates"}],
            "bounds": {"files": 1, "sites": 1, "symbols": 1, "max_files": 20, "max_sites": 160, "max_symbols": 8},
            "measured": ["err:1"], "inputs": {"candidate_sha256": "c0"},
        }
        scope["digest"] = batch_scope_digest(scope)
        sp = Path("evidence/planning/batch-scope/u-abc123") / ("%s.json" % scope["digest"][:32])
        write_canonical(root / sp, scope)
        cluster = {"id": "u:abc123", "kind": "compile", "path": rel, "write_set": [rel], "items": ["err:1"],
                   "label": scope["family_key"], "retry_key": "rk:unit:u:abc123",
                   "batch_scope": {"path": sp.as_posix(), "digest": scope["digest"], "rule": scope["rule"],
                                   "kind": "unit", "unit_id": "u:abc123", "members": 1}}
        wl = {"schema": "rhoai3.worklist/v1", "head": "u:abc123", "unit_formation": "v1",
              "measure": {"tuple": [0, 1, 0], "known": True, "blocked": []},
              "clusters": [cluster], "not_counted": [],
              "items": [{"id": "err:1", "source": "javac", "kind": "compile", "category": "mandatory",
                         "path": rel, "line": 1, "identity": "diag:a",
                         "rule_id": "compiler.err.cant.resolve.location",
                         "message": "cannot find symbol\n  symbol:   class UriComponentsBuilder"}]}
        write_canonical(root / WORKLIST, wl)
        write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "u:abc123",
                                             "task_id": "t_unit0001", "write_set": [rel],
                                             "revisions": [{"n": 1, "path": rel, "evidence": {"kind": "javac", "ref": "diag:a"}}]})
        prev = os.environ.get("HERMES_KANBAN_TASK")
        os.environ["HERMES_KANBAN_TASK"] = "t_unit0001"
        try:
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                rc = __import__("brief").main(["--root", str(root)])
        finally:
            if prev is None:
                os.environ.pop("HERMES_KANBAN_TASK", None)
            else:
                os.environ["HERMES_KANBAN_TASK"] = prev
        if rc != 0:
            return _fail("brief.py must serve a unit card: rc=%s %s" % (rc, err.getvalue()[:400]))
        brief = load_json(root / LOOP_DIR / "brief-u-abc123.json")
        unit = brief.get("unit") or {}
        if unit.get("unit_id") != "u:abc123" or unit.get("rule") != "unit/diagnostic-family/v1":
            return _fail("the brief must carry the unit's identity and rule: %s" % unit)
        groups = unit.get("members_by_rule") or {}
        if list(groups) != ["unit/diagnostic-family/v1"] or len(groups["unit/diagnostic-family/v1"]) != 1:
            return _fail("the members are grouped under the rule that formed them: %s" % groups)
        member = groups["unit/diagnostic-family/v1"][0]
        if member.get("path") != rel or not member.get("verdict"):
            return _fail("every member carries its locus and its current verdict: %s" % member)
        targets = unit.get("target_symbols") or []
        if len(targets) != 1 or (targets[0].get("catalog_row") or {}).get("block") != "symbol_renames":
            return _fail("every documented target carries the catalogue row that documents it: %s" % targets)
        checks = {c.get("check"): c.get("tool") for c in (unit.get("completion") or [])}
        if checks.get("identities-gone") != "javac" or checks.get("unit-assessment") != "worklist.assess_unit":
            return _fail("the completion checks name the tool that decides each: %s" % checks)
        note = str(unit.get("checkpoint") or "")
        if "judged ONCE, at its checkpoint" not in note or "INSIDE the sealed symbols are allowed" not in note:
            return _fail("the brief must state the checkpoint rule: %r" % note[:200])
        if "a failing test" not in note:
            return _fail("and what it does NOT relax: %r" % note[:300])
        if not unit.get("revisions"):
            return _fail("a revision already granted must be visible to the next attempt: %s" % unit)
        amend = str((brief.get("batch_scope") or {}).get("amend") or "")
        if "--evidence" not in amend:
            return _fail("the amend line must name --evidence for a unit: %r" % amend[:200])
    return 0


def _body_diff_brief_case() -> int:
    """H1b: the parity brief shows each body difference, where it may be produced and the amend-scope route."""
    from brief import parity_brief

    bd = {"summary": "order of $.pets[*].visits", "order_only": True, "differences": [{"path": "$.pets[0].visits", "kind": "order"}],
          "locus": "... --evidence parity:parity:x", "locus_hints": [{"path": "src/main/java/a/Pet.java", "member": "getVisits"}]}
    rows = [{"id": "parity:x", "source": "parity", "gate": "parity", "scenario": "sc:read", "entry_point": "ep:a", "advice": {"body_diff": bd}},
            {"id": "parity:y", "source": "parity", "gate": "parity", "scenario": "sc:cors", "entry_point": "ep:a", "advice": {}}]
    out = parity_brief(rows, {"gate": "parity"})
    got = out.get("body_diffs") or []
    if len(got) != 1 or got[0]["obligation"] != "parity:x" or got[0]["locus_hints"][0]["member"] != "getVisits" or "--evidence parity:" not in got[0]["locus"]:
        return _fail("the parity brief shows the body difference and its producer: %s" % got)
    return 0


def _scope_rule_brief_case() -> int:
    """H5a: ONE scope rule, stated once in the procedure the worker reads and
    again on the parity brief -- no "never touch a path outside the write set"
    beside "add it with amend-scope.py"; block only on a refusal or a path the
    loop never grants. H5b: the parity brief shows each server error with the
    product file its stack names."""
    import brief as mod

    proc, rule = mod.PROCEDURE, mod.SCOPE_RULE
    if "never touch a path outside the write set" in proc or rule not in proc:
        return _fail("the procedure states the single scope rule and no longer forbids the path it tells the worker to amend: %s" % proc[:300])
    for must in ("for every parity item", "amend-scope.py", "--evidence parity:<item id>", "BEFORE editing",
                 "ONLY when amend-scope.py REFUSES", "REFUSE: SCOPE_AMENDMENT", "tests, evidence/, decisions.yaml",
                 "outside the amended write set is reverted"):
        if must not in rule:
            return _fail("the scope rule must say %r: %s" % (must, rule))
    se = {"status": 500, "expected_status": 204, "exception": "jakarta.persistence.PersistenceException", "message": "bad path",
          "locus": "the failure is in src/main/java/a/RepoImpl.java: ... --evidence parity:parity:e",
          "locus_hints": [{"path": "src/main/java/a/RepoImpl.java", "type": "a.RepoImpl", "member": "delete", "line": 42}]}
    rows = [{"id": "parity:e", "source": "parity", "gate": "parity", "scenario": "sc:delete", "entry_point": "ep:a", "advice": {"server_error": se}},
            {"id": "parity:y", "source": "parity", "gate": "parity", "scenario": "sc:read", "entry_point": "ep:a", "advice": {}}]
    out = mod.parity_brief(rows, {"gate": "parity"})
    got = out.get("server_errors") or []
    if (len(got) != 1 or got[0]["obligation"] != "parity:e" or got[0]["scenario"] != "sc:delete"
            or got[0]["locus_hints"][0]["path"] != "src/main/java/a/RepoImpl.java" or not got[0]["locus"].startswith("the failure is in")):
        return _fail("the parity brief shows the server error and the file its stack names: %s" % got)
    if out.get("scope") != rule or out.get("body_diffs") != []:
        return _fail("the parity brief carries the scope rule: %s" % out.get("scope"))
    return 0


def _request_rejection_brief_case() -> int:
    """H6b: the parity brief shows each boundary refusal, and the handler's
    classification, first action, files and catalog rows ONCE per handler
    (v9 t_d280284d: seven obligations at one handler; the worker's context is
    the scarce resource). Each item names its handler and keeps only what is
    its own; the item rows of the brief point at the handler entry too."""
    import brief as mod
    from brief import parity_brief

    key = "a.AccountResource#create(a.AccountDto,org.springframework.validation.BindingResult)"
    note = "x" * 400
    rr = {"status": "400", "expected_status": "201", "observed_body": "empty body", "handler_key": key,
          "handler": {"type": "a.AccountResource", "member": "create(a.AccountDto,org.springframework.validation.BindingResult)", "params": []},
          "classification": ["a.AccountDto dto @RequestBody @Valid: request body parameter (a.AccountDto): @RequestBody is a supported annotation; @Valid on this parameter is undocumented -- " + note,
                             "org.springframework.validation.BindingResult binding: undocumented -- " + note],
          "first_action": "an undocumented parameter kind is present: org.springframework.validation.BindingResult (parameter binding) -- " + note,
          "next_actions": ["an undocumented annotation is present: @Valid on a.AccountDto dto -- " + note],
          "generated_body": {"generated": True, "type": "a.AccountDto", "missing_required": ["pets"], "text": "the request body type a.AccountDto is GENERATED by " + note},
          "locus": "the destination refused the request before or at the handler boundary (status 400, empty body) ... FIRST ACTION: ... --evidence parity:parity:r0",
          "locus_hints": [{"path": "src/main/java/a/AccountResource.java", "member": "create(a.AccountDto)"}, {"path": "src/main/java/a/AccountDto.java", "member": ""}],
          "catalog_rows": [{"key": "org.springframework.validation.BindingResult", "source": "https://quarkus.io/version/3.27/guides/spring-web", "note": note, "action": note}]}
    rows = [{"id": "parity:r%d" % n, "source": "parity", "gate": "parity", "scenario": "sc:create-%d" % n, "entry_point": "ep:a",
             "advice": {"request_rejection": dict(rr, status="400" if n else "422")}} for n in range(7)]
    rows.append({"id": "parity:y", "source": "parity", "gate": "parity", "scenario": "sc:read", "entry_point": "ep:a", "advice": {}})
    out = parity_brief(rows, {"gate": "parity"})
    got = out.get("request_rejections") or []
    if (len(got) != 7 or [g["obligation"] for g in got] != ["parity:r%d" % n for n in range(7)] or got[1]["scenario"] != "sc:create-1"
            or got[0]["status"] != "422" or got[1]["status"] != "400" or any(g["handler"] != key for g in got)
            or any(k in got[0] for k in ("classification", "first_action", "locus_hints", "catalog_rows", "locus"))):
        return _fail("each item keeps its own status pair and observed body and names its handler, nothing more: %s" % got[:2])
    h = (out.get("handlers") or {}).get(key) or {}
    if (list(out.get("handlers") or {}) != [key] or h.get("obligations") != ["parity:r%d" % n for n in range(7)]
            or [x["path"] for x in h.get("locus_hints") or []] != ["src/main/java/a/AccountResource.java", "src/main/java/a/AccountDto.java"]
            or h.get("catalog_rows", [{}])[0].get("key") != "org.springframework.validation.BindingResult"
            or h.get("classification") != rr["classification"] or h.get("first_action") != rr["first_action"]
            or h.get("next_actions") != rr["next_actions"] or h.get("generated_body") != rr["generated_body"]
            or "locus" in h or not h.get("boundary", "").startswith("the destination refused")
            or "--evidence parity:parity:r0" not in h.get("amend", "")):
        return _fail("the handler entry carries the classification, the first action, the files and the rows once, the boundary "
                     "and the amend line, and not the prose that repeats them: %s" % list(h))
    if len(json.dumps(out["request_rejections"]) + json.dumps(out["handlers"])) > len(json.dumps(rr)) + 2500:
        return _fail("seven items at one handler must not render the handler seven times")
    if out.get("server_errors") != [] or out.get("body_diffs") != []:
        return _fail("the other advice lists stay empty: %s" % out)
    if out.get("evidence") != mod.EVIDENCE_RULE or out.get("stop") != mod.STOP_RULE:
        return _fail("the parity brief carries the evidence rule and the stop rule")
    # the item rows of the brief point at the handler entry instead of repeating it
    mod.slim_item_rejections(rows)
    slim = rows[0]["advice"]["request_rejection"]
    if (slim.get("handler") != key or "parity.handlers[%s]" % key not in slim.get("see", "") or slim.get("status") != "422"
            or any(k in slim for k in ("classification", "first_action", "locus_hints", "catalog_rows", "locus"))):
        return _fail("an item row names its handler and points at parity.handlers: %s" % slim)
    # a row without handler_key (an older work list) still groups by its handler row, then by its first locus
    old = {"status": "400", "expected_status": "201", "handler": {"type": "a.R", "member": "m()"}, "locus_hints": [{"path": "p", "type": "a.R", "member": "m()"}]}
    if mod.rejection_handler_key(old) != "a.R#m()" or mod.rejection_handler_key({"locus_hints": old["locus_hints"]}) != "a.R#m()":
        return _fail("the handler key falls back to the handler row, then to the first locus")
    return 0


def _verify_runs_brief_case() -> int:
    """The stop rule needs a count the worker does not keep: run-verify.sh
    records each run for the issued card (record_verify_run), and the brief
    renders verify_runs -- the count, the obligations still reported, whether
    they are unchanged since the previous acceptance run, and whether the rule
    applies (two acceptance runs, the same non-empty obligations after both).
    A diagnostic run counts as a run but not toward the rule; a run that
    reports different obligations resets it."""
    import io
    from contextlib import redirect_stderr, redirect_stdout

    import brief as mod
    from _loop_common import load_verify_runs, record_verify_run, verify_runs_for, verify_runs_line
    from planner.paths import LOOP_ISSUED, VERIFY_RUN, WORKLIST

    for must in ("Evidence rule:", "mvn quarkus:dev", "NOT evidence", "run-verify.sh --mode acceptance", "verification/parity",
                 "Stop rule:", "After two acceptance runs with the same obligations still reported", "typed diagnosis",
                 "kanban_block kind=needs_input", "Do not run a third verify without a new edit", "Never start a server to explore",
                 "Read a product file at most once per edit cycle", "Do not read receipt.json, _run.json or verdict files"):
        if must not in mod.PROCEDURE:
            return _fail("the procedure must state %r once: %s" % (must, mod.PROCEDURE[:200]))
    with tempfile.TemporaryDirectory(prefix="verify-runs-") as td:
        root = Path(td)
        items = [{"id": "parity:a", "source": "parity", "kind": "parity", "gate": "parity", "category": "mandatory",
                  "path": "src/main/java/A.java", "line": 0, "rule_id": "PARITY", "message": "a", "scenario": "sc:a", "entry_point": "ep:a", "advice": {}},
                 {"id": "parity:b", "source": "parity", "kind": "parity", "gate": "parity", "category": "mandatory",
                  "path": "src/main/java/A.java", "line": 0, "rule_id": "PARITY", "message": "b", "scenario": "sc:b", "entry_point": "ep:a", "advice": {}}]
        cluster = {"id": "c:par", "kind": "parity", "gate": "parity", "path": "src/main/java/A.java",
                   "write_set": ["src/main/java/A.java"], "items": ["parity:a", "parity:b"]}
        wl = {"schema": "rhoai3.worklist/v1", "head": "c:par", "measure": {"tuple": [0, 0, 0], "known": True, "blocked": [], "parity_mismatches": 2},
              "clusters": [cluster], "items": items, "not_counted": []}
        write_canonical(root / WORKLIST, wl)
        write_canonical(root / VERIFY_RUN, {"schema": "rhoai3.verify-run/v1", "candidate_sha256": "c1" * 32})
        if record_verify_run(root, mode="acceptance")["count"] != 0 or (root / "verification/loop/verify-runs.json").is_file():
            return _fail("nothing is recorded without an issued card")
        write_canonical(root / LOOP_ISSUED, {"schema": "rhoai3.loop-issued/v1", "cluster": "c:par", "task_id": "t_card0001",
                                             "items": ["parity:a", "parity:b"], "gate": "parity", "gate_items": ["parity:a", "parity:b"]})
        r1 = record_verify_run(root, mode="acceptance")
        if (r1["count"] != 1 or r1["obligations_reported"] != ["parity:a", "parity:b"] or r1["stop_rule_applies"]
                or "verify runs on card t_card0001: 1 (1 acceptance); obligations of the issued card still reported: parity:a, parity:b" not in r1["line"]
                or "STOP RULE" in r1["line"]):
            return _fail("the first run is counted and printed, and the rule does not apply: %s" % r1)
        r2 = record_verify_run(root, mode="diagnostic")
        if r2["count"] != 2 or r2["acceptance_count"] != 1 or r2["stop_rule_applies"]:
            return _fail("a diagnostic run counts as a run, not toward the rule: %s" % r2)
        r3 = record_verify_run(root, mode="acceptance")
        if (r3["count"] != 3 or not r3["unchanged_since_previous"] or not r3["stop_rule_applies"]
                or "STOP RULE APPLIES" not in r3["line"] or "typed diagnosis" not in r3["line"] or "kanban_block kind=needs_input" not in r3["line"]):
            return _fail("two acceptance runs with the same obligations reported: the rule applies and the line says so: %s" % r3)
        # the brief renders it for THIS card, with the rule text beside it
        os.environ["HERMES_KANBAN_TASK"] = "t_card0001"
        try:
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                rc = mod.main(["--root", str(root)])
        finally:
            os.environ.pop("HERMES_KANBAN_TASK", None)
        if rc != 0:
            return _fail("brief.py serves the issued card: %s" % err.getvalue()[:300])
        b = json.loads(out.getvalue())
        vr = b.get("verify_runs") or {}
        if (vr.get("card") != "t_card0001" or vr.get("count") != 3 or vr.get("acceptance_count") != 2 or not vr.get("stop_rule_applies")
                or vr.get("obligations_reported") != ["parity:a", "parity:b"] or vr.get("rule") != mod.STOP_RULE
                or [r["mode"] for r in vr.get("runs") or []] != ["acceptance", "diagnostic", "acceptance"]
                or b.get("evidence_rule") != mod.EVIDENCE_RULE or b.get("stop_rule") != mod.STOP_RULE):
            return _fail("the brief carries verify_runs for this card and the two rules: %s" % vr)
        # a repair that discharges one obligation: the reported set changed, the rule no longer applies
        wl2 = dict(wl, items=items[:1], clusters=[dict(cluster, items=["parity:a"])])
        write_canonical(root / WORKLIST, wl2)
        r4 = record_verify_run(root, mode="acceptance")
        if r4["obligations_reported"] != ["parity:a"] or r4["unchanged_since_previous"] or r4["stop_rule_applies"]:
            return _fail("a changed set of reported obligations resets the rule: %s" % r4)
        # the next card (a new task id) starts at zero; the record is per card
        other = verify_runs_for(root, "t_card0002")
        if other["count"] != 0 or other["stop_rule_applies"] or verify_runs_line(other) != "":
            return _fail("the count is per card: %s" % other)
        if len(load_verify_runs(root)["runs"]) != 4:
            return _fail("every run is on the record")
    return 0


def main() -> int:
    if _scope_rule_brief_case():
        return 1
    if _request_rejection_brief_case():
        return 1
    if _verify_runs_brief_case():
        return 1
    if _repository_inventory_case():
        return 1
    if _unit_brief_case():
        return 1
    if _runtime_advice_case():
        return 1
    if _body_diff_brief_case():
        return 1

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cat_src = GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
        (root / ".hermes" / "planning" / "catalogs").mkdir(parents=True)
        shutil.copy(cat_src, root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json")
        refs_src = GOLDEN / ".hermes" / "skills" / "migration" / "spring-to-quarkus-patterns" / "references"
        shutil.copytree(refs_src, root / ".hermes" / "skills" / "migration" / "spring-to-quarkus-patterns" / "references")
        write_canonical(root / "evidence" / "build" / "bom-managed.json", {"managed": ["io.quarkus:quarkus-rest", "io.quarkus:quarkus-rest-jackson"]})
        write_canonical(root / "evidence" / "type-inventory.json", {"schema": "rhoai3.type-inventory/v1", "types": [
            {"fqn": "org.acme.dto.PetDto", "layer": "dto", "legacy_file": "src/main/java/org/acme/dto/PetDto.java", "dest_file": "src/main/java/org/acme/dto/PetDto.java", "generated": False},
            {"fqn": "org.acme.model.Owner", "layer": "model", "legacy_file": "src/main/java/org/acme/model/Owner.java", "dest_file": "src/main/java/org/acme/model/Owner.java", "generated": False},
        ]})
        (root / "src" / "main" / "java" / "org" / "acme" / "model").mkdir(parents=True)
        (root / "src" / "main" / "java" / "org" / "acme" / "model" / "Owner.java").write_text("class Owner {}\n", encoding="utf-8")
        (root / "src" / "main" / "java" / "org" / "acme" / "rest").mkdir(parents=True)
        (root / "src" / "main" / "java" / "org" / "acme" / "rest" / "PetResource.java").write_text(
            "package org.acme.rest;\nimport javax.persistence.Id;\nimport javax.validation.*;\nimport org.acme.dto.PetDto;\nimport org.springframework.validation.BindingResult;\nclass PetResource {}\n", encoding="utf-8")
        (root / "src" / "main" / "resources").mkdir(parents=True)
        (root / "src" / "main" / "resources" / "application.properties").write_text(
            "# db\nspring.datasource.url=jdbc:h2:mem:x\nspring.jpa.hibernate.ddl-auto=create-drop\nlogging.level.org.acme=DEBUG\n", encoding="utf-8")
        (root / "pom.xml").write_text("<project><dependencies><dependency><groupId>io.quarkus</groupId><artifactId>quarkus-rest-jackson</artifactId></dependency></dependencies></project>\n", encoding="utf-8")
        findings = {"violations": {
            "springboot-web-to-quarkus-00010": {"description": "web", "incidents": [{"uri": "file:///x/pom.xml", "lineNumber": 1, "message": "Add `quarkus-resteasy-reactive-jackson`."}], "links": []},
            "springboot-properties-to-quarkus-00001": {"description": "props", "incidents": [
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 2, "message": "Replace the property.", "variables": {"property": "spring.datasource.url"}},
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 3, "message": "Replace the property.", "variables": {}},
                {"uri": "file:///x/src/main/resources/application.properties", "lineNumber": 4, "message": "Replace the property.", "variables": {}},
            ], "links": []},
        }}
        write_canonical(root / "evidence" / "mta-findings.json", findings)

        # the rule's own condition, verbatim from the pinned rulesets (MTA_CLI_HOME)
        rs = root / "mta" / "rulesets" / "java" / "quarkus"; rs.mkdir(parents=True)
        (rs / "236-springboot-web-to-quarkus.windup.yaml").write_text(
            "- category: mandatory\n  ruleID: springboot-web-to-quarkus-00000\n  when:\n    java.dependency:\n      name: x\n"
            "- category: mandatory\n  description: Add jackson\n  ruleID: springboot-web-to-quarkus-00010\n  when:\n    or:\n    - and:\n      - java.dependency:\n          name: io.quarkus.quarkus-spring-web\n      - java.dependency:\n          name: io.quarkus.quarkus-resteasy-reactive-jackson\n        not: true\n  message: m\n- category: optional\n  ruleID: other\n", encoding="utf-8")
        os.environ["MTA_CLI_HOME"] = str(root / "mta")
        pom_cluster = {"id": "c:pom", "kind": "build", "path": "pom.xml", "write_set": ["pom.xml"]}
        rows = enrich([{"id": "inc:1", "source": "mta", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 1, "rule_id": "springboot-web-to-quarkus-00010"}], root, pom_cluster)
        r = rows[0]
        if r.get("advice_unmanaged") != ["quarkus-resteasy-reactive-jackson"] or r.get("advice_managed_equivalent", {}).get("quarkus-resteasy-reactive-jackson") != "io.quarkus:quarkus-rest-jackson":
            return _fail("pom advice must flag the unmanaged Quarkus 2 name with the managed equivalent: %s" % r)
        if r.get("advice_managed_present") != ["io.quarkus:quarkus-rest-jackson"]:
            return _fail("the managed equivalent already in the pom must be reported present: %s" % r.get("advice_managed_present"))
        g = enrich([{"id": "err:g", "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "GENERATED_SOURCE_ERROR",
                     "message": "target/generated-sources/openapi/src/main/java/a/PetDto.java:9: package javax.validation does not exist", "generated_path": "target/generated-sources/openapi/src/main/java/a/PetDto.java"}], root, pom_cluster)[0]
        ga = g.get("advice") or {}
        if ga.get("plugin") != "org.openapitools:openapi-generator-maven-plugin" or (ga.get("plugin_config") or {}).get("configuration", {}).get("generatorName") != "jaxrs-spec" or "generated file" not in ga.get("description", ""):
            return _fail("a generated-source error must point at the generator plugin and the catalog's documented configuration: %s" % ga)
        from brief import collapse_generated
        gens = [{"id": "err:%d" % i, "source": "javac", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 0, "rule_id": "GENERATED_SOURCE_ERROR",
                 "message": "target/generated-sources/openapi/src/main/java/a/D%d.java:9: package javax.validation does not exist" % i, "generated_path": "target/generated-sources/openapi/src/main/java/a/D%d.java" % (i % 3)} for i in range(7)]
        col = collapse_generated(gens + [{"id": "inc:x", "source": "mta", "kind": "build", "category": "mandatory", "path": "pom.xml", "line": 1, "rule_id": "r"}])
        if len(col) != 2 or col[0].get("count") != 7 or len(col[0].get("item_ids") or []) != 7 or len(col[0].get("generated_files") or []) != 3 or col[0]["generated_root"] != "target/generated-sources/openapi" or col[1]["id"] != "inc:x":
            return _fail("generated-source errors must collapse to one item per generated root with count, files and ids: %s" % [(c.get("id"), c.get("count")) for c in col])
        cond = r.get("rule_condition") or ""
        if not cond.startswith("when:") or "quarkus-resteasy-reactive-jackson" not in cond or "not: true" not in cond or "message: m" in cond or "ruleID: other" in cond:
            return _fail("the brief must carry the rule's when-block verbatim and nothing else: %r" % cond)

        java_cluster = {"id": "c:java", "kind": "compile", "path": "src/main/java/org/acme/rest/PetResource.java", "write_set": ["src/main/java/org/acme/rest/PetResource.java"]}
        items = [
            {"id": "err:1", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 5, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class PetDto\n  location: class org.acme.rest.PetResource"},
            {"id": "err:2", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 3, "rule_id": "compiler.err.doesnt.exist",
             "message": "package javax.persistence does not exist"},
            {"id": "err:3", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 9, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class NamedParameterJdbcTemplate\n  location: class org.acme.rest.PetResource"},
            {"id": "err:4", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 12, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class Owner\n  location: class org.acme.rest.PetResource"},
            {"id": "err:5", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 2, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class Id\n  location: class org.acme.rest.PetResource"},
            {"id": "err:6", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 3, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class NotNull\n  location: class org.acme.rest.PetResource"},
            {"id": "err:7", "source": "javac", "kind": "compile", "category": "mandatory", "path": java_cluster["path"], "line": 4, "rule_id": "compiler.err.cant.resolve.location",
             "message": "cannot find symbol\n  symbol:   class BindingResult\n  location: class org.acme.rest.PetResource"},
        ]
        rows = enrich(items, root, java_cluster)
        a = rows[0]["advice"]
        if a.get("symbol") != {"kind": "class", "name": "PetDto"} or (a.get("inventory") or {}).get("fqn") != "org.acme.dto.PetDto" or a["inventory"].get("present_in_destination") is not False:
            return _fail("a missing legacy type must carry its inventory row and that it is not in the destination yet: %s" % a)
        if (rows[3]["advice"].get("inventory") or {}).get("present_in_destination") is not True:
            return _fail("a type already in the destination tree must say so: %s" % rows[3]["advice"])
        b = rows[1]["advice"]
        if b.get("package") != "javax.persistence" or b.get("rename") != {"from": "javax.persistence", "to": "jakarta.persistence"}:
            return _fail("a javax.* package must carry the documented Jakarta rename: %s" % b)
        c = rows[2]["advice"]
        if not any(ref.endswith("jdbc-anti-essay.md") for ref in c.get("references") or []):
            return _fail("a Spring symbol must cite the reference file that covers it: %s" % c)
        if "message" not in a or "cannot find symbol" not in a["message"]:
            return _fail("the compiler's own words must be in the advice")
        d = rows[4]["advice"]
        if d.get("imported_as") != "javax.persistence.Id" or d.get("rename") != {"from": "javax.persistence", "to": "jakarta.persistence"}:
            return _fail("a bare symbol bound by an explicit javax import must carry the rename: %s" % d)
        e = rows[5]["advice"]
        if e.get("imported_as") != "javax.validation.*" or (e.get("rename") or {}).get("to") != "jakarta.validation":
            return _fail("a bare symbol bound by a javax wildcard import must carry the rename: %s" % e)
        if "Do not add this import again" not in (e.get("do_not") or "") or e.get("already_imported") is not True:
            return _fail("a javax symbol already imported must carry already_imported and do_not: %s" % e)
        br = rows[6]["advice"]
        if br.get("imported_as") != "org.springframework.validation.BindingResult" or br.get("already_imported") is not True:
            return _fail("an explicit Spring import of the unresolved symbol is already_imported: %s" % br)
        if br.get("rename") or "not on the destination classpath" not in (br.get("do_not") or ""):
            return _fail("BindingResult is a classpath replacement, not a Jakarta rename: %s" % br)
        if not br.get("references"):
            return _fail("BindingResult must cite a spring-to-quarkus-patterns reference: %s" % br)

        cfg_cluster = {"id": "c:cfg", "kind": "config", "path": "src/main/resources/application.properties", "write_set": ["src/main/resources/application.properties"]}
        items = [
            {"id": "inc:c1", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 2, "rule_id": "springboot-properties-to-quarkus-00001"},
            {"id": "inc:c2", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 3, "rule_id": "springboot-properties-to-quarkus-00001"},
            {"id": "inc:c3", "source": "mta", "kind": "config", "category": "mandatory", "path": cfg_cluster["path"], "line": 4, "rule_id": "springboot-properties-to-quarkus-00001"},
        ]
        rows = enrich(items, root, cfg_cluster)
        c1 = rows[0].get("config") or {}
        if c1.get("line_text") != "spring.datasource.url=jdbc:h2:mem:x" or c1.get("property") != "spring.datasource.url" or (c1.get("mapping") or {}).get("to") != "quarkus.datasource.jdbc.url" or c1.get("variables") != {"property": "spring.datasource.url"}:
            return _fail("a config item must carry the line, the key, the incident variables and the catalog mapping: %s" % c1)
        c2 = rows[1].get("config") or {}
        if (c2.get("mapping") or {}).get("to") != "quarkus.hibernate-orm.database.generation" or c2.get("value_mapping") != {"from": "create-drop", "to": "drop-and-create"}:
            return _fail("a mapped key with a documented value mapping must carry both: %s" % c2)
        c3 = rows[2].get("config") or {}
        if (c3.get("mapping") or {}).get("to") != 'quarkus.log.category."org.acme".level':
            return _fail("a prefix mapping must expand the rest of the key: %s" % c3)
        # a file-level incident on a profile file lists every Spring key with its mapping
        (root / "src" / "main" / "resources" / "application-hsqldb.properties").write_text(
            "# db\nquarkus.datasource.jdbc.url=jdbc:hsqldb:mem:x\nspring.jpa.database=HSQL\nspring.datasource.username=sa\n", encoding="utf-8")
        prof = {"id": "c:prof", "kind": "config", "path": "src/main/resources/application-hsqldb.properties", "write_set": ["src/main/resources/application-hsqldb.properties"]}
        rows = enrich([{"id": "inc:p1", "source": "mta", "kind": "config", "category": "mandatory", "path": prof["path"], "line": 0, "rule_id": "springboot-properties-to-quarkus-00001"}], root, prof)
        c4 = rows[0].get("config") or {}
        if c4.get("profile") != "hsqldb" or [k["key"] for k in c4.get("spring_keys") or []] != ["spring.jpa.database", "spring.datasource.username"] or c4["spring_keys"][1]["to"] != "quarkus.datasource.username":
            return _fail("a file-level profile incident must name the profile and the remaining Spring keys with their mappings: %s" % c4)
    if _issued_cluster_case():
        return 1
    print("OK: brief enrichment (pom unmanaged→managed; compile: inventory hit / present flag / Jakarta rename / reference file / already_imported classpath; config: line, key, variables, key+value mapping, prefix expansion; runtime: the cause, the member, and the siblings likely to carry it; issued cluster over empty head; a UNIT card's brief carries the members grouped under the rule that formed them with each one's current verdict, the documented targets with their catalogue rows, the completion checks naming the tool that decides each, the revisions already granted, an amend line that names --evidence, and the checkpoint rule -- judged once, intermediate regressions inside the sealed symbols allowed until then, and nothing else relaxed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
