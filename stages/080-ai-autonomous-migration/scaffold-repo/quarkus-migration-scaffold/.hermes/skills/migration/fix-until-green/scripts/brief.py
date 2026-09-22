#!/usr/bin/env python3
"""Print this card's brief: the only thing a worker edits.

The brief is derived from the sealed work list (never written by a
model): cluster id, kind, write set, and every item (rule / compiler
code, line, detail). The cluster is this card's issued cluster
(``verification/loop/issued.json`` when ``$HERMES_KANBAN_TASK`` matches,
or ``--cluster``), not whatever the work-list head is after a bounce.
Exit 0 with the brief; 1 when this card has no cluster to brief
(``LOOP_WRONG_CARD`` / ``LOOP_CLUSTER_NOT_OPEN`` / ``LOOP_NO_OPEN_CLUSTER``).
"""
from __future__ import annotations

import argparse
import os
import re
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _loop_common import budget as _budget, ensure_hermes_lib, pending_for, verify_runs_for  # noqa: E402

ensure_hermes_lib()
from planner.canonical import load_json, write_canonical  # noqa: E402
from planner.paths import LOOP_DIR, LOOP_ISSUED, MTA_FINDINGS, MTA_RESCAN_FINDINGS, WORKLIST, BOM_MANAGED, TYPE_INVENTORY  # noqa: E402
from planner.worklist import CHECKED_FAMILY_RULE, UNIT_KIND, UNIT_MAX_FILES, assess_unit, head_cluster, items_of  # noqa: E402

# H5a: the ONE scope rule, stated once, the same words the M3 skill uses. It
# replaces "never touch a path outside the write set" beside "add it with
# amend-scope.py rather than blocking" -- two rules that sent v9 c:67bfc8d7483e
# to the wrong file and then to a block.
SCOPE_RULE = (
    "Scope rule, for every parity item and for any runtime obligation whose producing file is outside the write set: "
    "find the producing file (the item's locus_hints -- a body_diff's producer, a server_error's first product frame -- "
    "name it), record it BEFORE editing it with amend-scope.py --root . --cluster <id> --card $HERMES_KANBAN_TASK "
    "--path <file> --reason <why> --evidence parity:<item id> (bounded by the card's own bounds: two amendments, a "
    "unit's four and never past its file bound), then edit it. The configuration file "
    "(src/main/resources/application.properties) is amendable the same way when the obligation's advice names a "
    "property that lives there (a navigation obligation: quarkus.swagger-ui.*); the fix is that property, never a "
    "handler that serves a substitute page. kanban_block kind=needs_input ONLY when amend-scope.py "
    "REFUSES (quote its REFUSE: SCOPE_AMENDMENT line) or when the fix is in a path the loop never grants: tests, "
    "evidence/, decisions.yaml, a plugin or dependency the brief did not ask for. A path outside the amended write "
    "set is reverted by advance.py."
)

# The evidence rule and the stop rule, stated once here and once in the M3
# skill in the same words. v9 t_d280284d (OwnerRestController, 7 boundary
# refusals): 84 tool calls, the controller read 4 times, 2 verifies, then the
# last third of the hour on `mvn quarkus:dev` and curl -- a dev-profile build
# that is not the measured artifact (ADR-011: the packaged build under the
# declared profiles is).
EVIDENCE_RULE = (
    "Evidence rule: the measured artifact is the packaged application run-verify.sh builds under the declared build "
    "profiles (decisions.yaml build_profiles) and starts exactly as the parity phase starts it. mvn quarkus:dev, a "
    "dev-profile build, java -jar, or any server you start yourself is NOT evidence and must not be used (K2 refuses it "
    "on a loop card): a dev build activates other beans and config than the packaged declared-profile build, so what it "
    "shows is not what is measured. The ONLY way to observe the destination is run-verify.sh --mode acceptance: it "
    "packages, starts, replays this card's scenarios and re-runs its read oracles, and leaves the verdicts, the "
    "destination log and -- for a 5xx -- the exception under verification/parity; this brief is their digest."
)

STOP_RULE = (
    "Stop rule: verify_runs counts the run-verify.sh runs on THIS card and lists the obligations still reported after "
    "each. After two acceptance runs with the same obligations still reported, stop exploring: write a typed diagnosis "
    "-- what you changed, what each verify measured, the one hypothesis you could not test and the evidence that would "
    "test it -- and kanban_block kind=needs_input carrying it. Do not run a third verify without a new edit. Never "
    "start a server to explore."
)

READS_RULE = (
    "Reads: this brief carries every diff, the advice, the loci and the catalog rows. Read a product file at most once "
    "per edit cycle. Do not read receipt.json, _run.json or verdict files: the brief is their digest."
)

# H9b (v9 t_2da2458b): the terminal tool's default timeout (180 s) killed a
# 30 s advance.py after it had accepted; a second call refused; the worker
# blocked an ACCEPTED card.
ADVANCE_RULE = (
    "advance.py rule: run it ONCE per verify, through the terminal tool with its `timeout` parameter set to 600 (the "
    "tool's foreground maximum; the default 180 is not enough for a rebuild and a mint). It prints one `advance: ...` "
    "progress line per phase, and the verdict line (OK: ACCEPTED / REVERTED / CONTINUE / VERIFICATION_PENDING / "
    "DEFERRED) is on the record the moment it is printed. After ANY non-zero, killed or truncated advance.py, do not "
    "decide from the exit code: run advance.py again -- it is idempotent and answers `OK: ACCEPTED already (step N, "
    "commit X)` or `REVERTED already` -- or read verification/loop/steps.json. Never kanban_block a card whose step is "
    "recorded accepted (K2 refuses it): kanban_complete is its terminator."
)

PROCEDURE = (
    "Patch the write set one item at a time (targeted edits; never rewrite a whole file, never tests). "
    + SCOPE_RULE + " " + EVIDENCE_RULE + " " + STOP_RULE + " " + READS_RULE + " " + ADVANCE_RULE
    + " Each item names its rule, its advice (the rule's own guidance), "
    "and for pom.xml the exact element at the reported line. An item whose advice names an artifact that is "
    "already in the pom is marked advice_present: verify and move on, do not add it twice. A compile item "
    "with already_imported: true is a classpath/API replacement, not a missing import — follow do_not; do "
    "not add the same import again. For a "
    "*Repository.java, inventory every method and repair the applicable ones together (one transformation); "
    "compile-only is not an exit. Do not run extra mvn compile/test/verify beside run-verify.sh. "
    "Optional --mode diagnostic is classpath + compiler only and cannot feed advance.py. Then run "
    "run-verify.sh --mode acceptance and advance.py; the measure decides, not you. advance.py may answer "
    "CONTINUE (exit 3) on a repair-family card: the candidate stays on the tree, no attempt is spent, and "
    "you keep working THIS card on the members it names, then verify and advance again."
)


def pom_elements(pom_path: Path) -> list[dict]:
    """Every <dependency>/<plugin>/<extension> element of a pom with its line
    span and GAV, from the XML parser's own line numbers (no text matching)."""
    import xml.parsers.expat

    els: list[dict] = []
    stack: list[dict] = []
    parser = xml.parsers.expat.ParserCreate()

    def start(name: str, _attrs: dict) -> None:
        stack.append({"name": name, "line": parser.CurrentLineNumber, "children": {}, "text": ""})

    def end(name: str) -> None:
        el = stack.pop()
        if stack and name in ("groupId", "artifactId", "version", "scope"):
            stack[-1]["children"][name] = el["text"].strip()
        if name in ("dependency", "plugin", "extension"):
            c = el["children"]
            els.append({"kind": name, "gav": "%s:%s" % (c.get("groupId", ""), c.get("artifactId", "")), "version": c.get("version", ""), "scope": c.get("scope", ""), "line_start": el["line"], "line_end": parser.CurrentLineNumber})

    def chars(data: str) -> None:
        if stack:
            stack[-1]["text"] += data

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    try:
        parser.Parse(pom_path.read_bytes(), True)
    except xml.parsers.expat.ExpatError:
        return []
    return els


def element_at(els: list[dict], line: int) -> dict | None:
    hits = [e for e in els if e["line_start"] <= line <= e["line_end"]]
    return min(hits, key=lambda e: e["line_end"] - e["line_start"]) if hits else None


def _backticked(text: str) -> list[str]:
    parts = text.split("`")
    return [parts[i].strip() for i in range(1, len(parts), 2) if parts[i].strip()]


def bom_managed(root: Path) -> set[str]:
    """group:artifact ids the pinned BOM manages (probe-bom-managed.py), or empty when unprobed."""
    p = root / BOM_MANAGED
    if not p.is_file():
        return set()
    return {str(x) for x in (load_json(p).get("managed") or [])}


def catalog(root: Path) -> dict:
    p = root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json"
    return load_json(p) if p.is_file() else {}


def _catalog_map(root: Path, key: str) -> dict[str, str]:
    rows = catalog(root).get(key) or {}
    return {k: str(v) for k, v in rows.items() if k != "note" and isinstance(v, str)}


def artifact_aliases(root: Path) -> dict[str, str]:
    """Documented renames from the bootstrap catalog (old group:artifact → managed group:artifact)."""
    return _catalog_map(root, "artifact_aliases")


def package_renames(root: Path) -> dict[str, str]:
    """Documented Jakarta namespace renames (javax.* → jakarta.*)."""
    return _catalog_map(root, "package_renames")


_SYMBOL_RE = re.compile(r"symbol:\s+(class|variable|method|interface|enum)\s+([A-Za-z_$][\w$]*)")
_PACKAGE_RE = re.compile(r"package ([\w.]+) does not exist")
_LOCATION_RE = re.compile(r"location:\s+(?:class|interface|package)\s+([\w.$]+)")
REFERENCES_DIR = Path(".hermes") / "skills" / "migration" / "spring-to-quarkus-patterns" / "references"


def rulesets_dir() -> Path | None:
    home = os.environ.get("MTA_CLI_HOME") or "/opt/mta-cli"
    d = Path(home) / "rulesets"
    return d if d.is_dir() else None


_RULE_CACHE: dict[str, str] = {}


def rule_condition(rule_id: str) -> str:
    """The `when:` block of an MTA rule, verbatim from the pinned rulesets: what
    makes the incident appear, hence exactly what makes it disappear (an xpath
    on the pom, a dependency name). Empty when the rulesets are not on this seat."""
    if not rule_id:
        return ""
    if rule_id in _RULE_CACHE:
        return _RULE_CACHE[rule_id]
    d = rulesets_dir()
    text = ""
    if d is not None:
        needle = "ruleID: " + rule_id
        for f in sorted(d.rglob("*.yaml")):
            try:
                raw = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle not in raw:
                continue
            lines = raw.splitlines()
            start = next((i for i, ln in enumerate(lines) if ln.strip() == needle), -1)
            if start < 0:
                continue
            # the rule item spans from its first key to the next list item at the same indent
            item_indent = len(lines[start]) - len(lines[start].lstrip())
            j = start
            while j > 0 and not lines[j].lstrip().startswith("- ") and (len(lines[j]) - len(lines[j].lstrip())) >= item_indent - 2:
                j -= 1
            k = start + 1
            while k < len(lines) and not (lines[k].lstrip().startswith("- ") and (len(lines[k]) - len(lines[k].lstrip())) <= item_indent - 2):
                k += 1
            block = lines[j:k]
            w = next((i for i, ln in enumerate(block) if ln.strip() == "when:"), -1)
            if w >= 0:
                wi = len(block[w]) - len(block[w].lstrip())
                out = [block[w]]
                for ln in block[w + 1:]:
                    if ln.strip() and (len(ln) - len(ln.lstrip())) <= wi:
                        break
                    out.append(ln)
                text = textwrap.dedent("\n".join(out[:40]))
            break
    _RULE_CACHE[rule_id] = text
    return text


def load_inventory(root: Path) -> list[dict]:
    p = root / TYPE_INVENTORY
    if not p.is_file():
        return []
    rows = load_json(p).get("types") or []
    return [r for r in rows if isinstance(r, dict) and r.get("fqn")]


def _references(root: Path) -> list[tuple[Path, str]]:
    d = root / REFERENCES_DIR
    if not d.is_dir():
        return []
    return [(p, p.read_text(encoding="utf-8", errors="replace")) for p in sorted(d.glob("*.md"))]


def reference_hits(refs: list[tuple[Path, str]], token: str, root: Path) -> list[str]:
    """The reference files that mention the symbol or package by name, most mentions first."""
    if not token:
        return []
    pat = re.compile(r"(?<![\w.])" + re.escape(token) + r"(?![\w])")
    scored = [(len(pat.findall(text)), str(p.relative_to(root))) for p, text in refs]
    return [path for n, path in sorted(scored, key=lambda x: (-x[0], x[1])) if n > 0][:3]


def compile_advice(item: dict, root: Path, inventory: list[dict], renames: dict[str, str], refs: list[tuple[Path, str]]) -> dict:
    """What the compiler said, and the facts the tools hold about the name it could not resolve:
    the inventory row (a legacy type not yet in the destination tree), the documented Jakarta
    rename for a javax.* package, and the spring-to-quarkus-patterns reference that covers the symbol."""
    msg = str(item.get("message") or item.get("detail") or "")
    out: dict = {"description": "compiler diagnostic", "message": msg}
    sym = _SYMBOL_RE.search(msg)
    pkg = _PACKAGE_RE.search(msg)
    token = ""
    if sym:
        out["symbol"] = {"kind": sym.group(1), "name": sym.group(2)}
        token = sym.group(2)
        hits = [r for r in inventory if str(r["fqn"]).rsplit(".", 1)[-1] == token]
        if hits:
            r = hits[0]
            dest = str(r.get("dest_file") or "")
            out["inventory"] = {"fqn": r["fqn"], "layer": r.get("layer"), "legacy_file": r.get("legacy_file"), "dest_file": dest,
                                "present_in_destination": bool(dest) and (root / dest).is_file()}
    elif pkg:
        token = pkg.group(1)
        out["package"] = token
        members = [r["fqn"] for r in inventory if str(r["fqn"]).startswith(token + ".")]
        if members:
            out["inventory_package"] = {"types": len(members), "present_in_destination": sorted(m for m in members if any((root / str(r.get("dest_file") or "x")).is_file() for r in inventory if r["fqn"] == m))[:5]}
    # a bare symbol ("class Id") names its package only through the file's imports:
    # `import javax.persistence.Id;` or `import javax.persistence.*;` binds the rename.
    # An explicit import of the unresolved token (Spring BindingResult, UriInfo, …)
    # is already_imported: adding it again cannot satisfy the diagnostic.
    imported = ""
    if sym:
        src = root / str(item.get("path") or "")
        if src.is_file():
            exact = ""
            wild = ""
            for ln in src.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln.startswith("import "):
                    continue
                spec = ln[len("import "):].rstrip(";").strip()
                if spec.endswith("." + token):
                    exact = spec
                    break
                if not wild and spec.endswith(".*"):
                    head = spec.rsplit(".", 1)[0]
                    if any(head == old or head.startswith(old + ".") for old in renames):
                        wild = spec
            imported = exact or wild
        if imported:
            out["imported_as"] = imported
            out["already_imported"] = True
    for old, new in renames.items():
        if (pkg and token.startswith(old)) or (imported and (imported == old + "." + token or imported.startswith(old + "."))) \
                or (sym and re.search(r"\b" + re.escape(old) + r"\.[\w.]*" + re.escape(token) + r"\b", msg)):
            out["rename"] = {"from": old, "to": new}
            break
    hits = reference_hits(refs, token, root)
    if hits:
        out["references"] = hits
    if out.get("already_imported"):
        if out.get("rename"):
            repl = "%s.%s" % (out["rename"]["to"], token) if not imported.endswith(".*") else out["rename"]["to"] + ".*"
            out["do_not"] = ("Do not add this import again; it is already in the file. Replace %s with the "
                             "documented rename %s." % (imported, repl))
        else:
            out["do_not"] = ("Do not add this import again; it is already in the file. The compiler cannot "
                             "resolve it because the type is not on the destination classpath. Follow "
                             "references[]; do not add a dependency or plugin the write set does not list.")
    return out


DECL_RE = re.compile(r"^\s*(?:@[\w.]+(?:\([^)]*\))?\s+)*[\w.<>,\[\]\s]+?\s+(\w+)\s*\(", re.M)
# the same structured patterns the work list uses, read here from the message so
# the brief helps whatever produced the item
MEMBER_RES = (re.compile(r"Method '([A-Za-z_][A-Za-z0-9_]*)' of repository"),
              re.compile(r"method '([A-Za-z_][A-Za-z0-9_]*)' of class"))


def frozen_member_implementations(root: Path, member: str, limit: int = 2) -> list[dict]:
    """How the FROZEN SOURCE implemented this member, with its query.

    A retirement removes the code and the frozen copy keeps it: pilot v7's
    repositories needed the JPQL that lived only in the JPA implementations
    ADR-004 retired, could not see it, and invented @Query text that silenced
    the build and meant nothing. This is the evidence that stops that."""
    out: list[dict] = []
    base = Path(root) / ".derived" / "frozen-input" / "src" / "main" / "java"
    if not member or not base.is_dir():
        return out
    rx = re.compile(r"^.*\b%s\s*\(" % re.escape(member), re.M)
    for f in sorted(base.rglob("*.java")):
        text = f.read_text(encoding="utf-8", errors="replace")
        m = rx.search(text)
        if not m:
            continue
        lines = text.splitlines()
        idx = text[: m.start()].count("\n")
        body = "\n".join(lines[idx: idx + 12]).strip()
        row = {"path": f.relative_to(Path(root) / ".derived" / "frozen-input").as_posix(), "snippet": body[:600]}
        q = re.search(r'"(SELECT|UPDATE|DELETE|INSERT)\s[^"]{4,300}"', body, re.I)
        if q:
            row["query"] = q.group(0).strip('"')
        out.append(row)
        if len(out) >= limit:
            break
    # an implementation carrying a query is the one worth reading first
    out.sort(key=lambda r: 0 if r.get("query") else 1)
    return out


def member_references(root: Path, member: str, exclude: str, limit: int = 3) -> list[dict]:
    """Where else this member is declared in the destination's own sources,
    with the lines around it (annotations included)."""
    out: list[dict] = []
    base = Path(root) / "src" / "main" / "java"
    if not member or not base.is_dir():
        return out
    rx = re.compile(r"^.*\b%s\s*\(" % re.escape(member), re.M)
    for f in sorted(base.rglob("*.java")):
        rel = f.relative_to(root).as_posix()
        if rel == exclude:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        m = rx.search(text)
        if not m:
            continue
        lines = text.splitlines()
        idx = text[: m.start()].count("\n")
        snippet = "\n".join(lines[max(0, idx - 3): idx + 2]).strip()
        out.append({"path": rel, "snippet": snippet[:400]})
        if len(out) >= limit:
            break
    return out


REPO_EXTENDS_RE = re.compile(r"\binterface\s+(?P<name>\w+)\s+extends\s+(?P<ext>[^{]+)")
REPO_METHOD_RE = re.compile(
    r"(?P<prefix>(?:@[\w.]+(?:\([^)]*\))?\s+)*)"
    r"(?:public\s+)?(?P<ret>[\w.<>,\[\]\s]+?)\s+(?P<name>\w+)\s*\((?P<args>[^)]*)\)\s*;",
    re.S,
)


def repository_inventory(root: Path, path: str) -> dict | None:
    """Every method this repository declares, plus what it extends.

    The platform names one member per obligation. Repairing only that member
    returns the next sibling as a new card (pilot v7). The brief lists them
    so one candidate can apply one transformation across the file."""
    if not str(path).endswith("Repository.java"):
        return None
    f = Path(root) / path
    if not f.is_file():
        return None
    text = f.read_text(encoding="utf-8", errors="replace")
    ext = REPO_EXTENDS_RE.search(text)
    methods: list[dict] = []
    for m in REPO_METHOD_RE.finditer(text):
        name = m.group("name")
        if name in ("if", "for", "while", "switch", "return", "new"):
            continue
        prefix = m.group("prefix") or ""
        methods.append({
            "name": name,
            "returns": " ".join((m.group("ret") or "").split()),
            "args": " ".join((m.group("args") or "").split()),
            "query": "@Query" in prefix,
            "modifying": "@Modifying" in prefix,
        })
    if not ext and not methods:
        return None
    return {
        "path": path,
        "extends": " ".join((ext.group("ext") if ext else "").split()),
        "methods": methods,
        "batch": ("Repair every applicable method in this repository in this candidate, using one "
                  "transformation. Compile-only is not an exit: the acceptance pass must include "
                  "successful augmentation. Do not repeat a previous_attempts strategy."),
        "playbook": "spring-to-quarkus-patterns/references/spring-data-jpa.md",
    }


def runtime_advice(item: dict, root: Path) -> dict:
    """Advice for a packaging or startup obligation.

    The platform reports ONE member at a time, so a card that fixes only the
    named one comes straight back with the next. The other members declared in
    the same file are listed here: they are where the same cause is likely to
    be waiting, and fixing them together is one verification instead of five
    (measured on pilot v7, where a repository's save, delete, findById and
    findAll each cost a full cycle)."""
    out = {
        "description": "the destination did not build or did not start; repair the cause the platform named, at the file it named",
        "message": str(item.get("message") or item.get("detail") or ""),
        "cause": str(item.get("cause") or ""),
        "member": str(item.get("member") or ""),
        "links": ["https://quarkus.io/version/3.27/guides/spring-data-jpa", "https://quarkus.io/version/3.27/guides/maven-tooling"],
    }
    WRITE_PREFIXES = ("save", "delete", "remove", "update", "insert", "persist", "merge")
    path = str(item.get("path") or "")
    member = str(item.get("member") or "")
    if not member:
        blob = "%s\n%s" % (item.get("message") or "", item.get("detail") or "")
        for rx in MEMBER_RES:
            m = rx.search(blob)
            if m:
                member = m.group(1)
                out["member"] = member
                break
    if member and str(item.get("cause") or "") == "underivable-query-method" and member.lower().startswith(WRITE_PREFIXES):
        # Documented Spring Data naming: these are writes, and the platform's
        # own suggestion ("did you forget @Query?") is wrong for them. A bare
        # @Query with no query and no @Modifying silences the derivation check
        # and proves nothing; pilot v7 annotated ten methods that way and the
        # build kept moving while the repositories stopped meaning anything.
        out["caution"] = ("%s is a write. A bare @Query is not a repair for it: the platform stops complaining and the method stops working. "
                          "Make the interface extend CrudRepository<T, ID>, which PROVIDES save and delete, and drop the local declaration; "
                          "annotate only a real query, and a modifying one with @Modifying." % member)
        out["links"] = ["https://quarkus.io/version/3.27/guides/spring-data-jpa#repository-fragments",
                        "https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html"]
    if member:
        # The same member declared elsewhere in the destination: for a query
        # method the platform cannot derive, the annotation that makes it
        # derivable is usually already in the tree, on the interface that
        # overrides it (pilot v7: PetRepository.findPetTypes could not be
        # derived while SpringDataPetRepository carried its @Query two files
        # away). Reading is not writing; the worker still edits only its own
        # write set.
        frozen = frozen_member_implementations(root, member)
        if frozen:
            out["frozen_implementations"] = frozen
            with_query = [r for r in frozen if r.get("query")]
            out["frozen_note"] = ("the frozen source implements %s in %s%s. A retirement removes the code and the frozen copy keeps it: "
                                  "take the query from there rather than writing one"
                                  % (member, ", ".join(r["path"].rsplit("/", 1)[-1] for r in frozen),
                                     (' — for example %s' % with_query[0]["query"]) if with_query else ""))
        elsewhere = member_references(root, member, path)
        if elsewhere:
            out["declared_elsewhere"] = elsewhere
            out["elsewhere_note"] = ("%s is also declared in %s; if it carries the annotation or query this one needs, that is the answer "
                                     "already present in this destination, not something to invent"
                                     % (member, ", ".join(e["path"] for e in elsewhere)))
    if member and path.endswith(".java"):
        f = root / path
        if f.is_file():
            others = sorted({m for m in DECL_RE.findall(f.read_text(encoding="utf-8", errors="replace")) if m != member})
            if others:
                out["siblings"] = others
                out["sibling_note"] = ("the platform names one member at a time; %s declares %s as well, and the same cause is likely to apply to them. "
                                       "Repair them together: each one left costs another full verification." % (path.rsplit("/", 1)[-1], ", ".join(others)))
    return out


def config_advice(item: dict, root: Path, rules: dict, cat: dict) -> dict:
    """The property line the incident points at, the incident variables, and the
    catalog's documented mapping for that key (properties / property_prefixes)."""
    out: dict = {}
    path, line = str(item.get("path") or ""), int(item.get("line") or 0)
    p = root / path
    text = ""
    name = path.rsplit("/", 1)[-1]
    if name.startswith("application-") and "." in name:
        out["profile"] = name[len("application-"):].split(".", 1)[0]
    if p.is_file() and line > 0:
        rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if line <= len(rows):
            text = rows[line - 1].strip()
            out["line_text"] = text
    elif p.is_file() and line == 0:
        # a file-level incident (profile file, missing single-file layout): every
        # Spring key still in the file, each with the catalog mapping it has
        keys = []
        props = cat.get("properties") or {}
        prefixes = cat.get("property_prefixes") or {}
        for n, raw in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            ln = raw.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k = ln.split("=", 1)[0].strip()
            if k.startswith("quarkus.") or k.startswith("%"):
                continue
            to = props.get(k) or ""
            if not to:
                for prefix, row in prefixes.items():
                    if k.startswith(prefix) and isinstance(row, dict):
                        to = str(row.get("to") or "").replace("{rest}", k[len(prefix):])
                        break
            keys.append({"line": n, "key": k, "to": to})
            if len(keys) >= 20:
                break
        if keys:
            out["spring_keys"] = keys
    rule = rules.get(str(item.get("rule_id")))
    if isinstance(rule, dict):
        for inc in rule.get("incidents") or []:
            if not isinstance(inc, dict):
                continue
            uri = str(inc.get("uri") or "")
            if uri.endswith(path) and int(inc.get("lineNumber") or 0) == line and isinstance(inc.get("variables"), dict):
                out["variables"] = inc["variables"]
                break
    key = ""
    if text and not text.startswith("#") and "=" in text:
        key = text.split("=", 1)[0].strip()
    elif isinstance(out.get("variables"), dict):
        key = str(out["variables"].get("property") or out["variables"].get("key") or "")
    if key:
        out["property"] = key
        props = cat.get("properties") or {}
        if key in props:
            out["mapping"] = {"to": props[key], "source": "compat-mapping.json properties"}
        else:
            for prefix, row in (cat.get("property_prefixes") or {}).items():
                if key.startswith(prefix) and isinstance(row, dict):
                    rest = key[len(prefix):]
                    out["mapping"] = {"to": str(row.get("to") or "").replace("{rest}", rest), "source": str(row.get("source") or "")}
                    break
        vals = (cat.get("property_values") or {}).get(out.get("mapping", {}).get("to") or key)
        if isinstance(vals, dict) and "=" in text:
            v = text.split("=", 1)[1].strip()
            if v in vals:
                out["value_mapping"] = {"from": v, "to": vals[v]}
    return out


def collapse_generated(items: list[dict]) -> list[dict]:
    """Errors in generated sources are one obligation per generator, not one
    per line: a card that changes the plugin configuration clears them all.
    The brief shows one item per generated root with the count, the files
    and a sample of the compiler's words (pilot v6: 240 such items on one
    pom card)."""
    groups: dict[str, list[dict]] = {}
    rest: list[dict] = []
    for it in items:
        if it.get("rule_id") == "GENERATED_SOURCE_ERROR":
            gen = str(it.get("generated_path") or "")
            key = "/".join(gen.split("/")[:3]) if gen.startswith("target/generated-sources/") else "target/generated-sources"
            groups.setdefault(key, []).append(it)
        else:
            rest.append(it)
    out: list[dict] = []
    for key, rows in sorted(groups.items()):
        first = dict(rows[0])
        files = sorted({str(r.get("generated_path") or "") for r in rows})
        first["id"] = "err:generated:%s" % key.rsplit("/", 1)[-1]
        first["item_ids"] = [r["id"] for r in rows]
        first["count"] = len(rows)
        first["generated_root"] = key
        first["generated_files"] = files[:12] + (["… %d more" % (len(files) - 12)] if len(files) > 12 else [])
        first["sample"] = [str(r.get("message") or "")[:160] for r in rows[:5]]
        first["message"] = "%d compiler errors in %d generated files under %s (one obligation: the generator's configuration)" % (len(rows), len(files), key)
        out.append(first)
    return out + rest


def enrich(items: list[dict], root: Path, cluster: dict) -> list[dict]:
    """Attach the rule's advice/links (from the findings the work list was
    built on) and, for pom.xml loci, the element at the reported line plus
    which advised artifacts the pom already carries."""
    findings_p = next((root / rel for rel in (MTA_RESCAN_FINDINGS, MTA_FINDINGS) if (root / rel).is_file()), None)
    rules = (load_json(findings_p).get("violations") or {}) if findings_p else {}
    pom_p = root / "pom.xml"
    els = pom_elements(pom_p) if cluster.get("path") == "pom.xml" and pom_p.is_file() else []
    artifacts = {e["gav"].split(":")[-1] for e in els} | {e["gav"] for e in els}
    managed, aliases = bom_managed(root), artifact_aliases(root)
    inventory, renames, refs, cat = load_inventory(root), package_renames(root), _references(root), catalog(root)
    out: list[dict] = []
    for it in items:
        row = dict(it)
        rule = rules.get(str(it.get("rule_id")))
        if it.get("source") == "javac" and it.get("rule_id") == "GENERATED_SOURCE_ERROR":
            # the generator's configuration owns this error; the catalog documents the platform's generator settings
            pc = {k: v for k, v in (cat.get("plugin_config") or {}).items() if k != "note" and isinstance(v, dict)}
            gen = str(it.get("generated_path") or "")
            owner = next((k for k in pc if ("openapi" in k and "/openapi/" in gen)), "")
            row["advice"] = {"description": "an error in generated source: fix the generator's configuration in the pom, never the generated file",
                             "message": str(it.get("message") or ""), "generated_path": gen,
                             "plugin": owner, "plugin_config": pc.get(owner) or {}, "links": [str((pc.get(owner) or {}).get("docs") or "")] if owner else []}
        elif it.get("source") == "javac" and it.get("rule_id") != "BUILD_UNRESOLVABLE":
            row["advice"] = compile_advice(it, root, inventory, renames, refs)
        if it.get("source") == "mta" and it.get("kind") == "config":
            cfg = config_advice(it, root, rules, cat)
            if cfg:
                row["config"] = cfg
        if it.get("source") == "runtime":
            row["advice"] = runtime_advice(it, root)
        if it.get("rule_id") == "BUILD_UNRESOLVABLE":
            # the resolver's own words; nothing else is measurable until Maven resolves the pom
            row["advice"] = {"description": "Maven cannot resolve the pom: fix the named coordinate (a BOM-managed artifact needs no version; an artifact the BOM does not manage must not be added under an old name)", "message": str(it.get("message") or it.get("detail") or ""), "links": ["https://quarkus.io/guides/maven-tooling"]}
        if isinstance(rule, dict) and it.get("source") == "mta":
            incs = rule.get("incidents") if isinstance(rule.get("incidents"), list) else []
            msg = next((str(i.get("message")) for i in incs if isinstance(i, dict) and i.get("message")), "")
            row["advice"] = {"description": str(rule.get("description") or ""), "message": msg, "links": [l.get("url") for l in (rule.get("links") or []) if isinstance(l, dict) and l.get("url")]}
            cond = rule_condition(str(it.get("rule_id") or ""))
            if cond:
                row["rule_condition"] = cond
            present = sorted(t for t in _backticked(msg) if t in artifacts or t.split(":")[-1] in artifacts)
            if present:
                row["advice_present"] = present
            if managed:
                # advice written for Quarkus 2 names artifacts the pinned BOM does not manage
                # (as `io.quarkus:quarkus-resteasy-reactive` or bare `quarkus-resteasy-reactive-jackson`);
                # say so, and name the managed artifact the catalog documents for it
                managed_ids = {m.split(":")[-1] for m in managed}
                alias_ids = {k.split(":")[-1]: v for k, v in aliases.items()}
                unmanaged = sorted(t for t in _backticked(msg)
                                   if (t.startswith("io.quarkus:") and t not in managed) or (":" not in t and t.startswith("quarkus-") and t not in managed_ids))
                if unmanaged:
                    row["advice_unmanaged"] = unmanaged
                    eq = {t: (aliases.get(t) or alias_ids.get(t.split(":")[-1])) for t in unmanaged}
                    eq = {t: v for t, v in eq.items() if v}
                    if eq:
                        row["advice_managed_equivalent"] = eq
                        row["advice_managed_present"] = sorted(v for v in eq.values() if v in artifacts or v.split(":")[-1] in artifacts)
        if els:
            el = element_at(els, int(it.get("line") or 0))
            row["element"] = el or {"kind": "project", "gav": "", "line_start": 1, "line_end": 0}
        out.append(row)
    return out


HANDLER_ITEM_FIELDS = ("status", "expected_status", "observed_body")
# what the handler entry carries ONCE: the structured advice (each line and
# each action verbatim), never the prose `locus` that repeats them, and the
# parameter rows without their catalog rows (`catalog_rows` has each once)
HANDLER_SHARED_FIELDS = ("handler", "classification", "first_action", "next_actions", "catalog_rows",
                         "catalog_source", "locus_hints", "body_type", "generated_body")


def rejection_handler_key(rr: dict) -> str:
    """The handler a request-rejection advice is about: the planner's
    handler_key, else type#member from its handler row, else its first locus."""
    if rr.get("handler_key"):
        return str(rr["handler_key"])
    h = rr.get("handler") if isinstance(rr.get("handler"), dict) else {}
    if h.get("type") or h.get("member"):
        return "%s#%s" % (h.get("type") or "", h.get("member") or "")
    hints = rr.get("locus_hints") or []
    if hints and isinstance(hints[0], dict):
        return "%s#%s" % (hints[0].get("type") or hints[0].get("path") or "", hints[0].get("member") or "")
    return ""


def group_request_rejections(rows: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """(one slim row per item, the shared advice once per handler).

    Seven obligations at one handler carry the same classification, the same
    catalog rows and the same first action; rendering it seven times is seven
    times the worker's context for nothing. Each item keeps what is its own
    (obligation, scenario, the status pair, the observed body) and names its
    handler; `handlers[key]` carries the rest verbatim, once."""
    slim: list[dict] = []
    handlers: dict[str, dict] = {}
    for i in rows:
        rr = (i.get("advice") or {}).get("request_rejection")
        if not rr:
            continue
        key = rejection_handler_key(rr) or str(i.get("id") or "")
        if key not in handlers:
            entry = dict({k: rr[k] for k in HANDLER_SHARED_FIELDS if k in rr}, obligations=[])
            if isinstance(entry.get("handler"), dict):
                entry["handler"] = dict(entry["handler"], params=[{k: v for k, v in p.items() if k != "catalog_rows"}
                                                                  for p in (entry["handler"].get("params") or []) if isinstance(p, dict)])
            entry["boundary"] = ("the destination refused these requests before or at the handler boundary while the source "
                                 "accepted them; nothing in the destination log at default level explains a 4xx: the answer is "
                                 "in the handler signature above, not in a stack. Apply FIRST ACTION, then next_actions, in one edit.")
            entry["amend"] = ("a file outside the write set (a locus_hints path) is amended BEFORE editing it: python3 "
                              ".hermes/skills/migration/fix-until-green/scripts/amend-scope.py --root . --cluster <this cluster> "
                              "--card $HERMES_KANBAN_TASK --path <that file> --reason <what binds there> --evidence parity:%s"
                              % str(i.get("id") or ""))
            handlers[key] = entry
        handlers[key]["obligations"].append(str(i.get("id") or ""))
        slim.append(dict({k: rr[k] for k in HANDLER_ITEM_FIELDS if k in rr}, obligation=str(i.get("id") or ""),
                         scenario=str(i.get("scenario") or ""), handler=key))
    return slim, handlers


def slim_item_rejections(items: list[dict]) -> None:
    """On the brief's item rows, replace each request_rejection advice by a
    pointer to its handler entry (the parity brief renders it once)."""
    for i in items:
        adv = i.get("advice") if isinstance(i.get("advice"), dict) else None
        rr = (adv or {}).get("request_rejection")
        if not rr:
            continue
        key = rejection_handler_key(rr) or str(i.get("id") or "")
        adv["request_rejection"] = dict({k: rr[k] for k in HANDLER_ITEM_FIELDS if k in rr}, handler=key,
                                        see="parity.handlers[%s]: the parameter classification, FIRST ACTION, locus_hints "
                                            "and catalog rows, rendered once for every item at this handler" % key)


def parity_brief(items: list[dict], cluster: dict) -> dict:
    """What a PARITY card is measured by, on the card itself.

    A parity repair leaves the compile/test tuple where it was, so "the measure
    decides" would read as "nothing can ever accept this card" (v9 card
    t_77cae2b2: the CORS properties the brief asked for were written, the
    acceptance pass was green, and advance.py reverted them because [0,0,0] did
    not decrease). What decides is the comparison itself, re-run for this
    card's own scenarios by the SAME acceptance command -- so the card says so,
    and names the scenarios that have to come back PASS."""
    rows = [i for i in items or [] if str(i.get("source") or "") == "parity"]
    if not rows and str(cluster.get("gate") or "") != "parity":
        return {}
    scenarios = sorted({str(s) for i in rows for s in (i.get("scenarios") or []) if str(s)})
    entry_points = sorted({str(i.get("entry_point") or "") for i in rows if i.get("entry_point")})
    rejections, handlers = group_request_rejections(rows)
    return {
        "gate": "parity",
        "scenarios": scenarios,
        "entry_points": entry_points,
        # H1b: what the body difference IS, where it may be produced, and how
        # the card reaches that file -- a digest alone sent v9 t_a755c0a1 to
        # the wrong layer for 74 minutes
        "body_diffs": [dict((i.get("advice") or {}).get("body_diff") or {}, obligation=str(i.get("id") or ""),
                            scenario=str(i.get("scenario") or ""))
                       for i in rows if (i.get("advice") or {}).get("body_diff")],
        # H5b: a 5xx the source did not answer carries the destination's own
        # exception and the product file its stack names -- the body was only
        # an error id, and the exception lived only in the destination's log
        "server_errors": [dict((i.get("advice") or {}).get("server_error") or {}, obligation=str(i.get("id") or ""),
                               scenario=str(i.get("scenario") or ""))
                          for i in rows if (i.get("advice") or {}).get("server_error")],
        # H6b: a 4xx with an empty (or platform) body where the source accepted
        # the same body-carrying request is a refusal before or at the handler
        # boundary -- the card gets the handler's parameter binding against the
        # compat catalog and the handler and DTO files, not a stack it does not
        # have. The classification is rendered ONCE per handler under
        # `handlers`; each item names its handler (v9 t_d280284d carried seven
        # items at one handler, and the worker's context is the scarce resource)
        "request_rejections": rejections,
        "handlers": handlers,
        "scope": SCOPE_RULE,
        "evidence": EVIDENCE_RULE,
        "stop": STOP_RULE,
        "measured_by": (
            "run-verify.sh --mode acceptance re-runs the scenario comparison for this card (run-parity.py, scoped to %s, "
            "and the read oracle of %s) after the packaging and startup gates, and re-composes "
            "verification/parity/receipt.json. You run the same command you always run; nothing extra."
            % (", ".join(scenarios) if scenarios else "this card's entry points, read oracles included",
               ", ".join(entry_points) if entry_points else "its entry point(s)")),
        "discharged_when": (
            "the re-composed receipt records %s as PASS. Disappearing from the work list is not enough: a scenario that "
            "became INCONCLUSIVE disappears too, and that is not a repair." %
            (", ".join(scenarios) if scenarios else "the entry point(s) this card names")),
        "refused_when": (
            "the same obligation is still reported, or an entry point the receipt recorded PASS before this card is no "
            "longer PASS -- a parity repair may not break another scenario. If the comparison could not run or the "
            "receipt could not be composed, nothing was measured: the candidate is retained (VERIFICATION_PENDING) and "
            "no attempt is spent."),
    }


def _card_of(root: Path, cluster: dict, task_env: str) -> str:
    """The card this brief is for: the issued card when it carries this
    cluster, else the task the environment names."""
    issued = load_issued(root)
    if str(issued.get("cluster") or "") == str(cluster.get("id") or "") and issued.get("task_id"):
        return str(issued["task_id"])
    return (task_env or "").strip()


def _max_attempts(root: Path) -> int:
    try:
        from planner.decisions import load_decisions, max_attempts

        return int(max_attempts(load_decisions(root)))
    except Exception:
        return 3


def _refuse(code: str, detail: str) -> int:
    print("REFUSE: %s %s" % (code, detail), file=sys.stderr)
    return 1


def load_issued(root: Path) -> dict:
    p = root / LOOP_ISSUED
    if not p.is_file():
        return {}
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


NOT_OPEN_NEXT = ("Your issued cluster is no longer on the open work list: the last verification measured its "
                 "obligations as gone. That is for advance.py to judge, not for you: run "
                 "`bash .hermes/skills/migration/fix-until-green/scripts/run-verify.sh --root . --mode acceptance` if the "
                 "candidate changed since, then `python3 .hermes/skills/migration/fix-until-green/scripts/advance.py "
                 "--root . --cluster %s --card $HERMES_KANBAN_TASK`, and follow its verdict. Do not kanban_block for this.")


def _issued_not_open(issued: dict, doc: dict) -> dict:
    """G2: the ISSUED card's own cluster is never "not open" to that card. A
    mid-card rebuild that no longer lists it is a measurement of the
    candidate (the obligations may be discharged); the issued record is the
    plan, and advance.py is the judge."""
    cid = str(issued.get("cluster") or "")
    ws = [str(w) for w in (issued.get("write_set") or [])]
    return {"id": cid, "path": ws[0] if ws else "", "kind": str(issued.get("kind") or ""),
            "items": [str(i) for i in (issued.get("items") or [])], "write_set": ws,
            "gate": str(issued.get("gate") or ""), "status": "issued",
            "retry_key": str(issued.get("retry_key") or cid), "batch_scope": dict(issued.get("batch_scope") or {}),
            "not_open": {"head": str(doc.get("head") or ""), "next": NOT_OPEN_NEXT % cid}}


def select_cluster(doc: dict, root: Path, cluster_arg: str, task_env: str) -> tuple[dict | None, str, str]:
    """This card's cluster, or (None, LOOP_* code, detail).

    Measured live on destination v9 (2026-09-15), card t_cc3b6aac: after a
    workspace bounce the work-list head was empty, brief.py printed
    LOOP_NO_OPEN_CLUSTER, and the worker rummaged issued.json / steps.json
    for ~20 minutes. The issued card is the plan; the head after a rebuild
    is not this card.
    """
    clusters = {str(c["id"]): c for c in (doc.get("clusters") or []) if isinstance(c, dict) and c.get("id")}
    issued = load_issued(root)
    issued_cid = str(issued.get("cluster") or "")
    issued_tid = str(issued.get("task_id") or "")
    task = (task_env or "").strip()
    terminator = ("Terminator: kanban_block kind=needs_input naming the cluster. "
                  "Do not rummage verification/loop/. Do not patch a different cluster's write set.")

    if cluster_arg:
        if issued_tid and task and issued_tid != task:
            return None, "LOOP_WRONG_CARD", (
                "--card env %r is not the minted card %s; %s" % (task, issued_tid, terminator))
        if issued_cid and issued_tid and task == issued_tid and cluster_arg != issued_cid:
            return None, "LOOP_WRONG_CARD", (
                "--cluster %r is not the issued cluster %s for this card; %s" % (cluster_arg, issued_cid, terminator))
        hit = clusters.get(cluster_arg)
        if hit is None and issued_cid and cluster_arg == issued_cid:
            return _issued_not_open(issued, doc), "", ""
        if hit is None:
            return None, "LOOP_CLUSTER_NOT_OPEN", (
                "cluster %s is not on the open work list; %s" % (cluster_arg, terminator))
        return hit, "", ""

    if task and issued_tid:
        if issued_tid != task:
            return None, "LOOP_WRONG_CARD", (
                "this task %r is not the issued loop card %s; terminator kanban_complete if the loop record "
                "already names this card, else %s" % (task, issued_tid, terminator))
        if issued_cid:
            hit = clusters.get(issued_cid)
            if hit is None:
                return _issued_not_open(issued, doc), "", ""
            return hit, "", ""

    head = head_cluster(doc)
    if head is not None:
        return head, "", ""
    extra = ""
    if issued_cid:
        extra = " issued card is %s cluster %s;" % (issued_tid or "(unbound)", issued_cid)
    return None, "LOOP_NO_OPEN_CLUSTER", (
        "(work list head is empty);%s pass --cluster <id> or set HERMES_KANBAN_TASK to the issued card. %s"
        % (extra, terminator))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True)
    ap.add_argument("--cluster", default="", help="this card's cluster id (default: issued.json when $HERMES_KANBAN_TASK matches, else the head)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    doc = load_json(root / WORKLIST)
    cluster, code, detail = select_cluster(doc, root, args.cluster, os.environ.get("HERMES_KANBAN_TASK") or "")
    if cluster is None:
        return _refuse(code, detail)
    write_set = list(cluster.get("write_set") or [])
    items = collapse_generated(enrich(items_of(doc, cluster), root, cluster))
    steps_p = root / LOOP_DIR / "steps.json"
    steps = load_json(steps_p) if steps_p.is_file() else {}
    # what this cluster's earlier attempts did and why the transaction refused
    # them: the retry card must not repeat them (v6 t_fc2b54c5 copied the
    # previous card's deletion and was vetoed for the same reason)
    previous = []
    rk = str(cluster.get("retry_key") or cluster["id"])
    retry_map = steps.get("retry_keys") or {}
    for r in (steps.get("rejected") or []):
        if not isinstance(r, dict) or r.get("rewound"):
            continue
        cid = str(r.get("cluster") or "")
        rkey = str(r.get("retry_key") or retry_map.get(cid) or "")
        if cid != cluster["id"] and rkey != rk:
            continue
        previous.append({
            "card": r.get("card"),
            "reason": r.get("reason"),
            "changed": r.get("changed"),
            "measure": (r.get("measure") or {}).get("tuple"),
            "loci_before": list(r.get("loci_before") or []),
            "loci_after": list(r.get("loci_after") or []),
            "patch_summary": list(r.get("patch_summary") or r.get("changed") or []),
            "legal_next": str(r.get("legal_next") or ""),
            "write_set": list(r.get("write_set") or []),
        })
    pending = pending_for(steps, cluster["id"])
    repo = repository_inventory(root, str(cluster.get("path") or ""))
    brief = {
        "schema": "rhoai3.loop-brief/v1",
        "cluster": cluster,
        "write_set": write_set,
        "items": items,
        "not_counted": [n for n in (doc.get("not_counted") or []) if str(n.get("path") or "") in write_set],
        "previous_attempts": previous,
        # the one budget answer (planner.budget): the same numbers the issued
        # card, a rejection and a deferral carry
        "budget": _budget(steps, cluster["id"], rk, int(_max_attempts(root))),
        "attempts_left": _budget(steps, cluster["id"], rk, int(_max_attempts(root)))["left"],
        "measure": doc["measure"],
        "procedure": PROCEDURE,
        "rule": "Edit only the write set as amended on the record (" + SCOPE_RULE + ") Do not edit tests. Do not touch pom.xml unless it is in the write set. Do not repeat a previous attempt (previous_attempts names the refused patch, before/after diagnostic loci, and the legal next action). A compile item with already_imported is not a missing import. Do not run extra mvn beside run-verify.sh. Then run run-verify.sh --mode acceptance and advance.py; the measure decides, not you.",
        "evidence_rule": EVIDENCE_RULE,
        "stop_rule": STOP_RULE,
        # the verify count for THIS card and the obligations each run left
        # reported (run-verify.sh records it): the stop rule is applied from
        # this, not from the worker's own counting
        "verify_runs": dict(verify_runs_for(root, _card_of(root, cluster, os.environ.get("HERMES_KANBAN_TASK") or "")),
                            rule=STOP_RULE),
    }
    slim_item_rejections(items)
    if cluster.get("not_open"):
        brief["issued_not_open"] = dict(cluster["not_open"])
        brief["procedure"] = cluster["not_open"]["next"]
    if pending:
        brief["verification_pending"] = {
            "card": pending.get("card"),
            "cause": pending.get("cause"),
            "reason": pending.get("reason"),
            "blocked": pending.get("blocked") or [],
            "changed": pending.get("changed") or pending.get("stored") or [],
            "restore": "python3 .hermes/skills/migration/fix-until-green/scripts/restore-pending.py --root . --cluster %s" % cluster["id"],
        }
    if repo:
        brief["repository"] = repo
    parity = parity_brief(items, cluster)
    if parity:
        brief["parity"] = parity
    # The SEALED SCOPE. The card is not finished while any inventoried member
    # still breaks the rule, so the worker is told the whole roster and the
    # current verdict on each one — including the members that are already
    # right and must be left alone.
    ref = cluster.get("batch_scope") or {}
    scope_p = root / str(ref.get("path") or "") if ref.get("path") else None
    if scope_p is not None and scope_p.is_file():
        scope = load_json(scope_p)
        family = str(scope.get("rule") or "") == CHECKED_FAMILY_RULE
        unit = str(scope.get("kind") or "") == UNIT_KIND
        issued_now = load_json(root / LOOP_ISSUED) if (root / LOOP_ISSUED).is_file() else {}
        # assess_unit dispatches on the sealed rule, so a repository inventory
        # and a checked-exception family are assessed exactly as before and a
        # unit is assessed by its own rule.
        verdicts = {r["member"]: r for r in assess_unit(root, scope)}
        def _member_name(m: dict) -> str:
            # how assess_unit names a row: the path, and the member when the
            # inventory records one. A repository or family inventory names its
            # members directly and keeps the name it always had.
            if "member" in m:
                return str(m["member"])
            mid = str(m.get("member_id") or "")
            return "%s%s" % (str(m.get("path") or ""), ("#" + mid) if mid else "")

        brief["batch_scope"] = {
            "rule": scope.get("rule"),
            "repository": scope.get("repository"),
            "digest": ref.get("digest"),
            "members": [dict(m, **{"verdict": verdicts.get(_member_name(m), {}).get("verdict", "inconclusive"),
                                   "detail": verdicts.get(_member_name(m), {}).get("detail", "")})
                        for m in scope.get("members") or []],
            "rule_note": ((str(scope.get("rule_note") or "") + " ") if family else "") + (
                          "Every member listed here is assessed against the rule when the candidate is judged, "
                          "and any that still violates it refuses the card. A member whose verdict is already ok "
                          "needs no edit and earns nothing if you change it. Written explanations do not count: "
                          "the assessment is made from the tree."),
            "introduced_by": scope.get("introduced_by") if family else None,
            "continuations": list((issued_now or {}).get("continuations") or []),
            "amend": (("Family members are already in the write set; amend-scope.py does not widen a family.")
                      if family else
                      ("A unit's scope is REVISED on evidence, never on a reason alone: amend-scope.py --root . "
                       "--cluster %s --card $HERMES_KANBAN_TASK --path <file> --reason <what this unit cannot finish "
                       "without it> --evidence javac:<a diagnostic identity the current work list carries> | "
                       "model:<a symbol this unit sealed> | runtime:<an rt: obligation the current work list carries>. "
                       "Bounded: four revisions, and never past %d file(s) in the write set." % (cluster["id"], UNIT_MAX_FILES))
                      if unit else
                      ("If a member cannot be finished without editing a file outside the write set, record the "
                       "amendment BEFORE touching it: amend-scope.py --root . --cluster %s --card $HERMES_KANBAN_TASK "
                       "--path <file> --reason <what this card cannot finish without it>. Bounded: two per card." % cluster["id"])),
            "amendments": list((issued_now or {}).get("amendments") or []),
        }
        if unit:
            # THE UNIT, as the worker has to see it: what one coherent repair
            # covers, what it is moving to and on whose authority, what decides
            # that it is finished, and the one rule that makes a coordinated
            # repair possible at all -- the checkpoint, not each edit, is judged.
            members: dict[str, list[dict]] = {}
            for m in scope.get("members") or []:
                name = _member_name(m)
                v = verdicts.get(name, {})
                members.setdefault(str(scope.get("rule") or ""), []).append({
                    "member": name, "path": str(m.get("path") or ""), "type": str(m.get("type") or ""),
                    "member_id": str(m.get("member_id") or ""), "state": str(m.get("state") or ""),
                    "signature": str(m.get("signature") or ""), "consumer": str(m.get("consumer") or ""),
                    "verdict": v.get("verdict", "inconclusive"), "detail": v.get("detail", ""),
                })
            brief["unit"] = {
                "unit_id": str(scope.get("unit_id") or ""),
                "rule": str(scope.get("rule") or ""),
                "family_key": str(scope.get("family_key") or ""),
                "members_by_rule": members,
                "symbols": list(scope.get("symbols") or []),
                # every documented target with the catalogue row that documents
                # it: a replacement with no row is not a target, and a
                # diagnostic about one is not explained by anything
                "target_symbols": [{"from": t.get("from"), "to": t.get("to"), "catalog_row": t.get("catalog_row")}
                                   for t in (scope.get("target_symbols") or [])],
                "completion": list(scope.get("completion") or []),
                "bounds": dict(scope.get("bounds") or {}),
                "evidence": list(scope.get("evidence") or []),
                "revisions": list((issued_now or {}).get("revisions") or []),
                "checkpoint": (
                    "This unit is judged ONCE, at its checkpoint, not per edit. Intermediate regressions INSIDE the "
                    "sealed symbols are allowed until then: the compile count may stand still or briefly rise, and the "
                    "step is still accepted, provided every diagnostic that remains is one the sealed symbols or the "
                    "documented targets above explain. Nothing else is relaxed -- a failing test, a new mandatory "
                    "obligation, a gate that was passing and is not any more, one of this unit's own sealed diagnostics "
                    "still reported, or a sealed member that violates its rule all refuse the card. So repair the whole "
                    "unit in one candidate; do not stop half way to make the count fall."),
            }
    write_canonical(root / LOOP_DIR / ("brief-%s.json" % cluster["id"].replace(":", "-")), brief)
    print(json.dumps(brief, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
