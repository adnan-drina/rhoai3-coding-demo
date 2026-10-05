#!/usr/bin/env python3
"""decided-repairs selftest (ADR-019 §2, §3), on a synthetic Maven project that
is not the pilot specimen: every transformation kind applies, a second run
changes nothing and records already-applied, and every refusal is typed and
writes nothing.

Exits proven here:
  - a reviewed new file is added only where absent or byte-identical
    (REPAIR_FILE_CONFLICT otherwise, file untouched)
  - an annotation expression is rewritten structurally: only the literal token
    changes, the original expression is kept verbatim, unrelated members, an
    unrelated annotation of the same simple name and the destination's own
    repairs survive; fully qualified and on-demand-imported uses are found;
    a destination site that is neither original nor rewritten is
    REPAIR_SITE_MISMATCH and no file changes; a non-literal value is
    REPAIR_ANNOTATION_VALUE_NOT_LITERAL
  - a member annotation lands with its imports; a different existing one is
    REPAIR_ANNOTATION_CONFLICT; a clashing import is REPAIR_IMPORT_CONFLICT
  - dependency and property rows: added once; an incompatible existing value
    (unprefixed or under a profile) is refused and never overwritten
  - a plugin execution retirement removes ONLY the decided execution, keeps the
    preserved goals and plugin configuration, records the thresholds as
    retired-not-achieved, and refuses unexpected configuration with
    REPAIR_EXECUTION_MISMATCH (different thresholds, the goal bound elsewhere)
    and a different source with REPAIR_NOT_APPLICABLE; the effective model is
    checked (stub mvn), a still-bound goal is REPAIR_EFFECTIVE_MISMATCH and no
    mvn is REPAIR_EFFECTIVE_UNVERIFIED
  - independent review reuse: reviewer == author, a review of other bytes,
    other source applicability, or no record at all are refused by type
  - idempotency: identical product tree, all rows already-applied, the
    inventory keeps the run that first applied each row
  - admission / baseline: receipt_gaps and summary see missing, stale and
    refused receipts, and a run bootstrapped before the capability is not
    stalled once its baseline exists
  - the bootstrap producer applies the manifest before the baseline and binds
    the receipt in evidence/producers/bootstrap.json; a second bootstrap
    leaves the product tree identical
  - the engine source names no specimen identifier
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
sys.path.insert(0, str(GOLDEN / ".hermes" / "lib"))
sys.path.insert(0, str(HERE))
import _decided_repairs as dr  # noqa: E402
from planner import decided_repairs as lib  # noqa: E402
from planner.canonical import load_json, sha256_file, write_canonical  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.acme</groupId>
  <artifactId>shop</artifactId>
  <version>1</version>
  <dependencies>
    <dependency><groupId>org.acme.lib</groupId><artifactId>audit</artifactId><version>2.0</version></dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>com.acme.tools</groupId>
        <artifactId>gate-maven-plugin</artifactId>
        <version>1.0</version>
        <configuration><skipList><skip>gen/**</skip></skipList></configuration>
        <executions>
          <execution><goals><goal>arm</goal></goals></execution>
          <execution>
            <id>gate</id>
            <goals><goal>enforce</goal></goals>
            <configuration>
              <rules><rule><scope>ALL</scope><limits>
                <limit><metric>LINES</metric><minimum>0.90</minimum></limit>
                <limit><metric>PATHS</metric><minimum>0.60</minimum></limit>
              </limits></rule></rules>
            </configuration>
          </execution>
          <execution><id>summary</id><phase>prepare-package</phase><goals><goal>summarize</goal></goals></execution>
        </executions>
      </plugin>
    </plugins>
  </build>
  <profiles>
    <profile><id>extra</id></profile>
  </profiles>
</project>
"""

ORDER_API = """package org.acme.shop.api;

import java.util.List;
import org.acme.guard.Guard;
import org.other.Marker;

@Guard("isStaff()")
public class OrderApi {
    private final List<String> names = List.of();

    @Guard("hasGrant('orders:read')")
    @Marker("keep")
    public List<String> list() { return names; }

    @Guard(value = "hasGrant(\\"orders:write\\") and isOwner(#id)")
    public void update(int id, String body) { }

    public int unrelated() { return 42; }
}
"""

ITEM_API = """package org.acme.shop.api;

import org.acme.guard.*;

public class ItemApi {
    // a comment with an astral character \U0001F600 before the sites
    @Guard("hasGrant('items')")
    public void a() {}

    @org.acme.guard.Guard("isStaff()")
    public void b() {}
}
"""

OTHER_API = """package org.acme.shop.api;

import org.elsewhere.Guard;

public class OtherApi {
    @Guard("not-ours")
    public void c() {}
}
"""

ACCOUNT = """package org.acme.shop.model;

import org.acme.persist.Column;

@Table("accounts")
public class Account {

    @Column("login")
    private String login;

    private String secret;

    public String getLogin() { return login; }
}
"""

RULES_TEST = """package org.acme.shop;

class RulesTest {
    void legacy() { }
}
"""

RULES_TEST_REVIEWED = """package org.acme.shop;

class RulesTest {
    void ported() { }
}
"""

GUARD_MODE = """package org.acme.shop.guard;

public class GuardMode {
    public boolean off() { return true; }
}
"""

PROPS = "shop.guard.enabled=false\nserver.port=8080\n"

SOURCES = {
    "pom.xml": POM,
    "src/main/java/org/acme/shop/api/OrderApi.java": ORDER_API,
    "src/main/java/org/acme/shop/api/ItemApi.java": ITEM_API,
    "src/main/java/org/acme/shop/api/OtherApi.java": OTHER_API,
    "src/main/java/org/acme/shop/model/Account.java": ACCOUNT,
    "src/test/java/org/acme/shop/RulesTest.java": RULES_TEST,
    "src/main/resources/application.properties": PROPS,
}

TEST_PATH = "src/test/java/org/acme/shop/RulesTest.java"
NEW_PATH = "src/main/java/org/acme/shop/guard/GuardMode.java"
MANIFEST = "repairs/shop/manifest.json"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        # the product tree only: harness state and caches are not product
        if not p.is_file() or rel.startswith(("evidence/", "frozen/", "verification/", ".hermes/", ".derived/")):
            continue
        h.update(rel.encode()); h.update(b"\0"); h.update(p.read_bytes()); h.update(b"\0")
    return h.hexdigest()


def base_manifest() -> dict:
    return {
        "schema": "rhoai3.decided-repairs-manifest/v1", "specimen": "acme-shop", "manifest_version": "0.1.0",
        "standing_obligations": ["fresh execution of the retained test"],
        "review_records": [
            {"id": "RR-1", "adr": "ADR-201", "kind": "operator-step", "source": "fixture", "operator": "op", "author": "seat-a", "reviewer": "seat-b",
             "reviewed_artifacts": [{"path": TEST_PATH, "sha256": sha(RULES_TEST_REVIEWED), "applicability": {"source_path": TEST_PATH, "source_sha256": sha(RULES_TEST)}}]},
            {"id": "RR-2", "adr": "ADR-202", "kind": "operator-step", "source": "fixture", "operator": "op", "author": "seat-a", "reviewer": "seat-c",
             "reviewed_artifacts": [{"path": NEW_PATH, "sha256": sha(GUARD_MODE)}]},
        ],
        "transformations": [
            {"id": "t-test", "adr": "ADR-201", "kind": "replace_reviewed_file", "path": TEST_PATH, "content": "reviewed/RulesTest.java",
             "content_sha256": sha(RULES_TEST_REVIEWED), "applicability": {"source_sha256": sha(RULES_TEST)}, "review_record": "RR-1",
             "obligations": ["fresh execution"]},
            {"id": "t-new", "adr": "ADR-202", "kind": "add_file", "path": NEW_PATH, "content": "reviewed/GuardMode.java",
             "content_sha256": sha(GUARD_MODE), "review_record": "RR-2"},
            {"id": "t-guard", "adr": "ADR-202", "kind": "java_annotation_expression", "roots": ["src/main/java"],
             "annotation": "org.acme.guard.Guard", "attribute": "value", "template": "@mode.off() or {expression}",
             "applicability": {}},
            {"id": "t-type", "adr": "ADR-202", "kind": "java_member_annotation", "type": "org.acme.shop.model.Account",
             "annotation": "org.acme.id.Principal", "text": "@Principal", "imports": ["org.acme.id.Principal"], "applicability": {}},
            {"id": "t-login", "adr": "ADR-202", "kind": "java_member_annotation", "type": "org.acme.shop.model.Account", "member": "login",
             "member_kind": "field", "annotation": "org.acme.id.LoginName", "text": "@LoginName", "imports": ["org.acme.id.LoginName"], "applicability": {}},
            {"id": "t-secret", "adr": "ADR-202", "kind": "java_member_annotation", "type": "org.acme.shop.model.Account", "member": "secret",
             "member_kind": "field", "annotation": "org.acme.id.Secret", "text": "@Secret(kind = Kind.PLAIN, reader = org.acme.shop.guard.GuardMode.class)",
             "imports": ["org.acme.id.Secret", "org.acme.id.Kind"], "applicability": {}},
            {"id": "t-dep", "adr": "ADR-202", "kind": "pom_dependency", "groupId": "org.acme.id", "artifactId": "id-store"},
            {"id": "t-prop-switch", "adr": "ADR-202", "kind": "property", "key": "shop.guard.enabled", "value": "false",
             "applicability": {"source_value": "false"}},
            {"id": "t-prop-new", "adr": "ADR-202", "kind": "property", "key": "shop.auth.eager", "value": "false"},
            {"id": "t-retire", "adr": "ADR-203", "kind": "pom_retire_execution",
             "plugin": {"groupId": "com.acme.tools", "artifactId": "gate-maven-plugin"},
             "execution": {"id": "gate", "goals": ["enforce"], "phase": None},
             "configuration": {"rules": [{"scope": "ALL", "limits": [{"metric": "LINES", "minimum": "0.90"}, {"metric": "PATHS", "minimum": "0.60"}]}]},
             "preserve_goals": ["arm", "summarize"], "applicability": {}},
        ],
    }


def decisions(manifest_sha: str, applies: list[str] | None = None) -> dict:
    return {"adrs": [{"id": a, "status": "accepted", "title": a} for a in ("ADR-200", "ADR-201", "ADR-202", "ADR-203")],
            "build_profiles": {"adr": "ADR-200", "active": ["prod"]},
            "decided_repairs": {"adr": "ADR-200", "manifest": MANIFEST, "manifest_sha256": manifest_sha,
                                "applies": applies if applies is not None else ["ADR-201", "ADR-202", "ADR-203"]}}


def author_manifest(root: Path, copy: Path, manifest: dict) -> dict:
    """What a manifest author does: read the applicability the frozen source
    yields and write it into the manifest."""
    described = {r["id"]: r for r in dr.describe_source(root, copy, manifest)}
    for t in manifest["transformations"]:
        d = described[t["id"]]
        if t["kind"] == "java_annotation_expression":
            t["applicability"] = {"sites": d["sites"], "structure_sha256": d["structure_sha256"]}
        elif t["kind"] in ("java_member_annotation", "pom_retire_execution"):
            t["applicability"] = {"structure_sha256": d["structure_sha256"]}
    return manifest


def write_manifest(root: Path, manifest: dict) -> dict:
    p = root / MANIFEST
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return decisions(sha256_file(p))


def make(td: Path, *, mutate_dest=None, mutate_copy=None, manifest_edit=None) -> tuple[Path, Path, dict]:
    root = td / "dest"
    copy = td / "frozen"
    for base in (root, copy):
        for rel, text in SOURCES.items():
            p = base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    if mutate_copy:
        mutate_copy(copy)
    # the destination as the loop would have it: a worker repair and an extra member
    order = root / "src/main/java/org/acme/shop/api/OrderApi.java"
    order.write_text(order.read_text(encoding="utf-8")
                     .replace("public void update(int id, String body) { }", "public void update(int id, String body, String etag) { /* repaired */ }")
                     .replace("    public int unrelated()", "    public void patch() { }\n\n    public int unrelated()"), encoding="utf-8")
    (root / "reviewed").mkdir(parents=True, exist_ok=True)
    (root / "reviewed/RulesTest.java").write_text(RULES_TEST_REVIEWED, encoding="utf-8")
    (root / "reviewed/GuardMode.java").write_text(GUARD_MODE, encoding="utf-8")
    write_canonical(root / "evidence/build/bom-managed.json", {"managed": ["org.acme.id:id-store"], "bom": {}})
    manifest = author_manifest(root, copy, base_manifest())
    if manifest_edit:
        manifest_edit(manifest)
    doc = write_manifest(root, manifest)
    if mutate_dest:
        mutate_dest(root)
    return root, copy, doc


def rows(receipt: dict) -> dict[str, dict]:
    return {r["id"]: r for r in receipt["rows"]}


def refused(receipt: dict, tid: str) -> str:
    r = rows(receipt)[tid]
    return (r.get("refusal") or {}).get("class", "") if r["status"] == "refused" else ""


def stub_mvn(bindir: Path, effective: str = "") -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    stub = bindir / "mvn"
    stub.write_text("#!%s\nimport shutil, sys\nout = [a.split('=', 1)[1] for a in sys.argv if a.startswith('-Doutput=')][0]\n"
                    "shutil.copy(%r or 'pom.xml', out)\n" % (sys.executable, effective), encoding="utf-8")
    stub.chmod(0o755)


def with_path(bindir: Path | None):
    class _Ctx:
        def __enter__(self):
            self.old = os.environ.get("PATH", "")
            if bindir is None:
                keep = [d for d in self.old.split(os.pathsep) if not (Path(d) / "mvn").exists()]
                os.environ["PATH"] = os.pathsep.join(keep)
            else:
                os.environ["PATH"] = str(bindir) + os.pathsep + self.old
            return self

        def __exit__(self, *a):
            os.environ["PATH"] = self.old
    return _Ctx()


# ---------------------------------------------------------------------------
def case_clean_apply_and_idempotent(td: Path) -> None:
    root, copy, doc = make(td)
    before_order = (root / "src/main/java/org/acme/shop/api/OrderApi.java").read_text(encoding="utf-8")
    rec, blocks = dr.apply_decided_repairs(root, copy, doc)
    check(not blocks, "clean apply must not block: %s" % blocks)
    st = {k: v["status"] for k, v in rows(rec).items()}
    check(st == {"t-test": "applied", "t-new": "applied", "t-guard": "applied", "t-type": "applied", "t-login": "applied",
                 "t-secret": "applied", "t-dep": "applied", "t-prop-switch": "already-applied", "t-prop-new": "applied",
                 "t-retire": "applied"}, "statuses: %s" % st)
    for r in rec["rows"]:
        check(r["implementation"] == {"name": "decided-repairs", "version": dr.ENGINE_VERSION}, "row implementation")
        check(r["files"] and r["symbols"] and r["inputs"] and r["outputs"], "row %s must carry files, symbols, input and output digests" % r["id"])
        if r["kind"] in ("java_annotation_expression", "java_member_annotation", "pom_retire_execution"):
            a = r["applicability"]
            check(a.get("expected") == a.get("observed") and a.get("observed"), "row %s must bind the source structure: %s" % (r["id"], a))
    check(rec["implementation"]["engine_sha256"] == sha256_file(Path(dr.__file__)) and rec["implementation"]["java_tool_sha256"], "receipt binds the engine and tool digests")
    check(rec["classification"] == "autonomous_execution_with_predecided_repairs", "classification")
    from planner.schema_lite import load_schema, validate

    schema_errors = validate(rec, load_schema(GOLDEN / ".hermes/planning/schemas/decided-repairs-receipt.schema.json"))
    check(not schema_errors, "the receipt must satisfy its schema: %s" % schema_errors)
    # the structural rewrite: only literal tokens changed, originals kept verbatim
    order = (root / "src/main/java/org/acme/shop/api/OrderApi.java").read_text(encoding="utf-8")
    check('@Guard("@mode.off() or isStaff()")' in order and '@Guard("@mode.off() or hasGrant(\'orders:read\')")' in order, "rewritten sites: %s" % order)
    check('@Guard(value = "@mode.off() or hasGrant(\\"orders:write\\") and isOwner(#id)")' in order, "escaped expression kept verbatim, explicit name kept")
    restored = order.replace("@mode.off() or ", "")
    check(restored == before_order, "nothing but the literal tokens may change (repairs, extra members, other annotations kept)")
    check("String etag) { /* repaired */ }" in order and "public void patch() { }" in order and '@Marker("keep")' in order, "worker repairs preserved")
    item = (root / "src/main/java/org/acme/shop/api/ItemApi.java").read_text(encoding="utf-8")
    check('@Guard("@mode.off() or hasGrant(\'items\')")' in item and '@org.acme.guard.Guard("@mode.off() or isStaff()")' in item and "\U0001F600" in item,
          "on-demand import and fully qualified uses are rewritten, UTF-16 offsets honoured: %s" % item)
    check((root / "src/main/java/org/acme/shop/api/OtherApi.java").read_text(encoding="utf-8") == OTHER_API, "a Guard of another package is never touched")
    check(rows(rec)["t-guard"]["details"]["rewritten"] == 5, "five sites rewritten: %s" % rows(rec)["t-guard"]["details"])
    acct = (root / "src/main/java/org/acme/shop/model/Account.java").read_text(encoding="utf-8")
    check('@Table("accounts")\n@Principal\npublic class Account' in acct, "type annotation after the existing ones: %s" % acct)
    check('    @Column("login")\n    @LoginName\n    private String login;' in acct, "field annotation after the last annotation, same indent")
    check("    @Secret(kind = Kind.PLAIN, reader = org.acme.shop.guard.GuardMode.class)\n    private String secret;" in acct, "field without annotations gets it before its modifiers")
    for imp in ("org.acme.id.Principal", "org.acme.id.LoginName", "org.acme.id.Secret", "org.acme.id.Kind"):
        check(acct.count("import %s;" % imp) == 1, "import %s added once" % imp)
    check((root / TEST_PATH).read_text(encoding="utf-8") == RULES_TEST_REVIEWED and (root / NEW_PATH).read_text(encoding="utf-8") == GUARD_MODE, "reviewed files installed")
    rr = {r["id"]: r for r in rec["review_records"]}
    check(set(rr) == {"RR-1", "RR-2"} and rr["RR-1"]["artifacts"][0]["reviewed_sha256"] == sha(RULES_TEST_REVIEWED), "review reuse recorded: %s" % rr)
    pom = (root / "pom.xml").read_text(encoding="utf-8")
    check("<id>gate</id>" not in pom and "<goal>enforce</goal>" not in pom, "the decided execution is gone")
    check("<goal>arm</goal>" in pom and "<id>summary</id>" in pom and "<skip>gen/**</skip>" in pom and "<artifactId>audit</artifactId>" in pom, "everything else in the pom stays")
    check(pom.count("<artifactId>id-store</artifactId>") == 1, "dependency row added once")
    ret = rec["coverage_account"]["retired_thresholds"]
    check(len(ret) == 1 and ret[0]["status"] == "retired-not-achieved" and ret[0]["retired_thresholds"]["rules"][0]["limits"][0]["minimum"] == "0.90",
          "thresholds preserved in the coverage account: %s" % ret)
    props = (root / "src/main/resources/application.properties").read_text(encoding="utf-8")
    check(props.startswith(PROPS) and props.count("shop.auth.eager=false") == 1 and props.count("shop.guard.enabled") == 1, "property rows: %s" % props)
    check(any("fresh execution" in o for o in rec["obligations"]), "obligations recorded")
    # idempotency
    h = tree_hash(root)
    rec2, blocks2 = dr.apply_decided_repairs(root, copy, doc)
    check(not blocks2 and tree_hash(root) == h, "second run must leave the product tree identical")
    check({r["status"] for r in rec2["rows"]} == {"already-applied"}, "second run records already-applied: %s" % [(r["id"], r["status"], r.get("refusal")) for r in rec2["rows"]])
    inv = {i["id"]: i for i in rec2["inventory"]}
    check(inv["t-guard"]["first_applied_run"] == 1 and inv["t-prop-switch"]["first_applied_run"] is None and len(rec2["runs"]) == 2,
          "inventory keeps the run that first applied a row: %s" % inv["t-guard"])
    # effective model: stub mvn over the edited pom passes; a pom still binding the goal refuses
    with with_path(td / "bin"):
        stub_mvn(td / "bin")
        eb = dr.finalize_effective(root, rec2, doc)
        check(not eb and rec2["effective_configuration"]["checked"] and len(rec2["effective_configuration"]["runs"]) == 2,
              "effective model checked under the default and every declared profile: %s %s" % (eb, rec2["effective_configuration"]))
        check(rec2["effective_configuration"]["decided_build_profiles"] == ["prod"], "decided profiles recorded")
        stale = td / "stale-effective.xml"
        stale.write_text(POM, encoding="utf-8")
        stub_mvn(td / "bin", str(stale))
        rec3 = load_json(root / "evidence/producers/decided-repairs.json")
        eb = dr.finalize_effective(root, rec3, doc)
        check([b["class"] for b in eb] == ["REPAIR_EFFECTIVE_MISMATCH", "REPAIR_EFFECTIVE_MISMATCH"] and rec3["status"] == "refused",
              "a goal still bound in the effective model refuses: %s" % eb)
    with with_path(None):
        rec4 = load_json(root / "evidence/producers/decided-repairs.json")
        eb = dr.finalize_effective(root, rec4, doc)
        check([b["class"] for b in eb] == ["REPAIR_EFFECTIVE_UNVERIFIED"], "no mvn is unverified, never a pass: %s" % eb)


def case_conflicts(td: Path) -> None:
    def dest(root: Path) -> None:
        (root / NEW_PATH).parent.mkdir(parents=True, exist_ok=True)
        (root / NEW_PATH).write_text(GUARD_MODE.replace("true", "false"), encoding="utf-8")
        p = root / "src/main/resources/application.properties"
        p.write_text(p.read_text(encoding="utf-8") + "%prod.shop.auth.eager = true\n", encoding="utf-8")
        pom = root / "pom.xml"
        pom.write_text(pom.read_text(encoding="utf-8").replace("<artifactId>audit</artifactId><version>2.0</version></dependency>",
                                                               "<artifactId>audit</artifactId><version>2.0</version></dependency>\n"
                                                               "    <dependency><groupId>org.acme.id</groupId><artifactId>id-store</artifactId><version>9</version></dependency>")
                       .replace("<minimum>0.60</minimum>", "<minimum>0.50</minimum>"), encoding="utf-8")
        acct = root / "src/main/java/org/acme/shop/model/Account.java"
        acct.write_text(acct.read_text(encoding="utf-8").replace('    @Column("login")', '    @Column("login")\n    @org.acme.id.LoginName(strict = true)')
                        .replace("import org.acme.persist.Column;", "import org.acme.persist.Column;\nimport org.other.Kind;"), encoding="utf-8")
    root, copy, doc = make(td, mutate_dest=dest)
    snap = {p: (root / p).read_bytes() for p in (NEW_PATH, "src/main/resources/application.properties", "pom.xml")}
    rec, blocks = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-new") == "REPAIR_FILE_CONFLICT", "conflicting new file: %s" % rows(rec)["t-new"])
    check(refused(rec, "t-prop-new") == "REPAIR_PROPERTY_CONFLICT", "a profiled incompatible value refuses: %s" % rows(rec)["t-prop-new"])
    check(refused(rec, "t-dep") == "REPAIR_DEPENDENCY_CONFLICT", "a dependency with another version refuses: %s" % rows(rec)["t-dep"])
    check(refused(rec, "t-retire") == "REPAIR_EXECUTION_MISMATCH", "different thresholds are a typed mismatch: %s" % rows(rec)["t-retire"])
    check(refused(rec, "t-login") == "REPAIR_ANNOTATION_CONFLICT", "a different existing annotation refuses: %s" % rows(rec)["t-login"])
    check(refused(rec, "t-secret") == "REPAIR_IMPORT_CONFLICT", "a clashing import refuses: %s" % rows(rec)["t-secret"])
    check(rows(rec)["t-guard"]["status"] == "applied" and rows(rec)["t-test"]["status"] == "applied", "unrelated rows still apply")
    check((root / NEW_PATH).read_bytes() == snap[NEW_PATH] and (root / "src/main/resources/application.properties").read_bytes() == snap["src/main/resources/application.properties"],
          "a refused row writes nothing")
    pom = (root / "pom.xml").read_text(encoding="utf-8")
    check("<id>gate</id>" in pom and "<version>9</version>" in pom, "the pom keeps the refused rows' state")
    check(rec["status"] == "refused" and {b["subject"] for b in blocks} >= {"t-new", "t-prop-new", "t-dep", "t-retire", "t-login", "t-secret"}, "blocks name the rows")
    # a goal bound elsewhere is not retired either
    def elsewhere(root: Path) -> None:
        pom = root / "pom.xml"
        pom.write_text(pom.read_text(encoding="utf-8").replace(
            "<profile><id>extra</id></profile>",
            "<profile><id>extra</id><build><plugins><plugin><groupId>com.acme.tools</groupId><artifactId>gate-maven-plugin</artifactId>"
            "<executions><execution><id>again</id><goals><goal>enforce</goal></goals></execution></executions></plugin></plugins></build></profile>"), encoding="utf-8")
    root, copy, doc = make(td / "elsewhere", mutate_dest=elsewhere)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-retire") == "REPAIR_EXECUTION_MISMATCH" and "<id>gate</id>" in (root / "pom.xml").read_text(encoding="utf-8"),
          "the goal bound in a profile is a mismatch, nothing is retired: %s" % rows(rec)["t-retire"])
    # a destination whose preserved goal is gone is a mismatch too
    root, copy, doc = make(td / "nopreserve", mutate_dest=lambda r: (r / "pom.xml").write_text(
        (r / "pom.xml").read_text(encoding="utf-8").replace("<execution><goals><goal>arm</goal></goals></execution>", ""), encoding="utf-8"))
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-retire") == "REPAIR_EXECUTION_MISMATCH" and "<id>gate</id>" in (root / "pom.xml").read_text(encoding="utf-8"),
          "a retirement that would drop a preserved goal refuses: %s" % rows(rec)["t-retire"])


def case_sites(td: Path) -> None:
    def odd(root: Path) -> None:
        p = root / "src/main/java/org/acme/shop/api/ItemApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace("hasGrant('items')", "permitAll()"), encoding="utf-8")
    root, copy, doc = make(td / "odd", mutate_dest=odd)
    h = tree_hash(root)
    before = (root / "src/main/java/org/acme/shop/api/OrderApi.java").read_text(encoding="utf-8")
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-guard") == "REPAIR_SITE_MISMATCH", "a site that is neither original nor rewritten refuses: %s" % rows(rec)["t-guard"])
    check((root / "src/main/java/org/acme/shop/api/OrderApi.java").read_text(encoding="utf-8") == before, "the refused rewrite changed no file (atomic)")

    def missing(root: Path) -> None:
        p = root / "src/main/java/org/acme/shop/api/ItemApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace('    @Guard("hasGrant(\'items\')")\n', ""), encoding="utf-8")
    root, copy, doc = make(td / "missing", mutate_dest=missing)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-guard") == "REPAIR_SITE_MISMATCH", "a deleted authorization site refuses: %s" % rows(rec)["t-guard"])

    def constant(base: Path) -> None:
        p = base / "src/main/java/org/acme/shop/api/ItemApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace('@Guard("hasGrant(\'items\')")', "@Guard(Rules.ITEMS)"), encoding="utf-8")
    root, copy, doc = make(td / "const", mutate_dest=constant)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-guard") == "REPAIR_ANNOTATION_VALUE_NOT_LITERAL", "a non-literal value is never guessed at: %s" % rows(rec)["t-guard"])

    def unresolved(root: Path) -> None:
        p = root / "src/main/java/org/acme/shop/api/OtherApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace("import org.elsewhere.Guard;", "import org.elsewhere.*;"), encoding="utf-8")
    root, copy, doc = make(td / "unres", mutate_dest=unresolved)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-guard") == "REPAIR_ANNOTATION_UNRESOLVED", "a simple name the imports cannot resolve refuses: %s" % rows(rec)["t-guard"])

    def broken(root: Path) -> None:
        p = root / "src/main/java/org/acme/shop/api/OrderApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace("public int unrelated()", "public int unrelated("), encoding="utf-8")
    root, copy, doc = make(td / "broken", mutate_dest=broken)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-guard") == "REPAIR_JAVA_UNPARSEABLE", "an unparseable file is never edited: %s" % rows(rec)["t-guard"])


def case_applicability_and_review(td: Path) -> None:
    def other_source(copy: Path) -> None:
        p = copy / "src/main/java/org/acme/shop/api/ItemApi.java"
        p.write_text(p.read_text(encoding="utf-8").replace("hasGrant('items')", "hasGrant('stock')"), encoding="utf-8")
        (copy / TEST_PATH).write_text(RULES_TEST + "// changed\n", encoding="utf-8")
        pom = copy / "pom.xml"
        pom.write_text(pom.read_text(encoding="utf-8").replace("<minimum>0.90</minimum>", "<minimum>0.95</minimum>"), encoding="utf-8")
        acct = copy / "src/main/java/org/acme/shop/model/Account.java"
        acct.write_text(acct.read_text(encoding="utf-8").replace("private String login;", "private char[] login;"), encoding="utf-8")
        props = copy / "src/main/resources/application.properties"
        props.write_text("shop.guard.enabled=true\n", encoding="utf-8")
        (copy / NEW_PATH).parent.mkdir(parents=True, exist_ok=True)
        (copy / NEW_PATH).write_text("package x;\n", encoding="utf-8")

    # the manifest is authored against the ORIGINAL source, then applied to another one
    root, copy, doc = make(td / "appl")
    other_source(copy)
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    for tid in ("t-guard", "t-test", "t-retire", "t-login", "t-prop-switch", "t-new"):
        check(refused(rec, tid) == "REPAIR_NOT_APPLICABLE", "%s must not apply to another source structure: %s" % (tid, rows(rec)[tid]))
    check("<id>gate</id>" in (root / "pom.xml").read_text(encoding="utf-8"), "a retirement decided for one configuration is never applied to another")

    def review_edit(fn):
        def edit(m: dict) -> None:
            fn(m)
        return edit

    cases = {
        "REPAIR_REVIEW_NOT_INDEPENDENT": lambda m: m["review_records"][0].update(reviewer="seat-a"),
        "REPAIR_REVIEW_ARTIFACT_MISMATCH": lambda m: m["review_records"][0]["reviewed_artifacts"][0].update(sha256="0" * 64),
        "REPAIR_REVIEW_APPLICABILITY": lambda m: m["review_records"][0]["reviewed_artifacts"][0]["applicability"].update(source_sha256="1" * 64),
        "REPAIR_REVIEW_MISSING": lambda m: m["transformations"][0].pop("review_record"),
    }
    for cls, fn in cases.items():
        root, copy, doc = make(td / cls, manifest_edit=review_edit(fn))
        rec, _ = dr.apply_decided_repairs(root, copy, doc)
        check(refused(rec, "t-test") == cls and (root / TEST_PATH).read_text(encoding="utf-8") == RULES_TEST, "%s: %s" % (cls, rows(rec)["t-test"]))
    # an ADR identifier alone is not a review record
    root, copy, doc = make(td / "adr-only", manifest_edit=lambda m: m["transformations"][0].update(review_record="ADR-201"))
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-test") == "REPAIR_REVIEW_MISSING", "an ADR id is not a review record: %s" % rows(rec)["t-test"])
    # reviewed bytes that changed after the review
    root, copy, doc = make(td / "content")
    (root / "reviewed/RulesTest.java").write_text(RULES_TEST_REVIEWED + "// edited\n", encoding="utf-8")
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-test") == "REPAIR_CONTENT_DIGEST", "changed reviewed content refuses: %s" % rows(rec)["t-test"])
    # the destination test is neither the source bytes nor the reviewed ones (someone else's port)
    root, copy, doc = make(td / "foreign", mutate_dest=lambda r: (r / TEST_PATH).write_text("class RulesTest { void mine() {} }\n", encoding="utf-8"))
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-test") == "REPAIR_FILE_CONFLICT", "a foreign port is a conflict: %s" % rows(rec)["t-test"])
    # manifest pinning and ADR checks
    root, copy, doc = make(td / "pin")
    doc["decided_repairs"]["manifest_sha256"] = "2" * 64
    rec, blocks = dr.apply_decided_repairs(root, copy, doc)
    check([b["class"] for b in blocks] == ["REPAIR_MANIFEST_DIGEST"] and not rec["rows"] and tree_hash(root) == tree_hash(root),
          "an unpinned manifest applies nothing: %s" % blocks)
    root, copy, doc = make(td / "invalid", manifest_edit=lambda m: m["transformations"][0].update(kind="copy_whole_tree"))
    rec, blocks = dr.apply_decided_repairs(root, copy, doc)
    check([b["class"] for b in blocks] == ["REPAIR_MANIFEST_INVALID"] and not rec["rows"], "an unknown kind fails the manifest schema: %s" % blocks)
    root, copy, doc = make(td / "applies")
    doc["decided_repairs"]["applies"] = ["ADR-201", "ADR-202"]
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-retire") == "REPAIR_ADR_NOT_ACCEPTED", "a row whose ADR the decision does not apply refuses: %s" % rows(rec)["t-retire"])
    root, copy, doc = make(td / "unmanaged")
    write_canonical(root / "evidence/build/bom-managed.json", {"managed": [], "bom": {}})
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    check(refused(rec, "t-dep") == "REPAIR_DEPENDENCY_UNMANAGED", "a version-less row the platform does not manage refuses: %s" % rows(rec)["t-dep"])


def case_admission(td: Path) -> None:
    root, copy, doc = make(td / "adm")
    # bootstrap receipt without the capability key and no baseline: missing
    write_canonical(root / "evidence/producers/bootstrap.json", {"status": "ok"})
    gaps = lib.receipt_gaps(root, doc)
    check([g["class"] for g in gaps] == ["DECIDED_REPAIRS_MISSING"], "no bootstrap application and no baseline: %s" % gaps)
    # predates the capability, baseline already recorded: admission lets the run go on, the baseline question does not
    write_canonical(root / "verification/loop/steps.json", {"steps": [{"verdict": "baseline"}]})
    check(lib.receipt_gaps(root, doc) == [], "a run bootstrapped before the capability is not stalled")
    check([g["class"] for g in lib.receipt_gaps(root, doc, for_baseline=True)] == ["DECIDED_REPAIRS_MISSING"], "a NEW baseline always needs the repairs")
    check(lib.summary(root, doc).get("applied_at_bootstrap") is False, "the summary says the repairs did not enter at bootstrap")
    (root / "verification/loop/steps.json").unlink()
    rec, _ = dr.apply_decided_repairs(root, copy, doc)
    write_canonical(root / "evidence/producers/bootstrap.json", {"status": "ok", "decided_repairs": dr.bootstrap_record(root, rec)})
    check(lib.receipt_gaps(root, doc, for_baseline=True) == [], "applied and bound: no gap: %s" % lib.receipt_gaps(root, doc, for_baseline=True))
    s = lib.summary(root, doc)
    check(s["classification"] == "autonomous_execution_with_predecided_repairs" and s["counts"]["applied"] == 9 and s["inventory"] == 10, "summary: %s" % s)
    check(lib.summary(root, {"adrs": []}) == {"declared": False, "classification": None}, "no decision, no classification")
    # the manifest moved on after the bootstrap
    m = load_json(root / MANIFEST)
    m["manifest_version"] = "0.2.0"
    doc2 = write_manifest(root, m)
    classes = sorted(g["class"] for g in lib.receipt_gaps(root, doc2))
    check(classes == ["DECIDED_REPAIRS_STALE"], "a manifest newer than the receipt is stale: %s" % classes)
    check([g["class"] for g in lib.receipt_gaps(root, doc)] == ["DECIDED_REPAIRS_MANIFEST"], "a manifest that no longer matches its pin: %s" % lib.receipt_gaps(root, doc))
    doc2_rec = load_json(root / "evidence/producers/decided-repairs.json")
    doc2_rec["rows"][0]["status"] = "refused"
    doc2_rec["rows"][0]["refusal"] = {"class": "REPAIR_FILE_CONFLICT", "detail": "x"}
    write_canonical(root / "evidence/producers/decided-repairs.json", doc2_rec)
    classes = sorted(g["class"] for g in lib.receipt_gaps(root, doc2))
    check("DECIDED_REPAIR_REFUSED" in classes and "DECIDED_REPAIRS_STALE" in classes, "a refused row and an unbound receipt are both reported: %s" % classes)
    shape = lib.section_gaps({"decided_repairs": {"adr": "ADR-999", "manifest": ""}}, {"ADR-200"})
    check(sorted(g["class"] for g in shape) == ["ADR_NOT_ACCEPTED", "MISSING_DECISION", "MISSING_DECISION"], "decision shape: %s" % shape)


def case_bootstrap_integration(td: Path) -> None:
    from planner import pipeline, specimens

    root = td / "boot"
    adrs = list(specimens.ACCEPTED_ADRS) + [{"id": a, "status": "accepted", "title": a} for a in ("ADR-200", "ADR-202", "ADR-203")]
    specimens.build_dest(root, specimens.specimen("http"), decisions=specimens.admitted_decisions(adrs=adrs))
    pipeline.assemble_bundle(root)
    copy = root / ".derived" / "frozen-input"
    # the frozen legacy gains a coverage gate plugin and one authorised endpoint
    pom = copy / "pom.xml"
    gate = POM[POM.index("      <plugin>\n        <groupId>com.acme.tools"):POM.index("    </plugins>")]
    pom.write_text(pom.read_text(encoding="utf-8").replace("    </plugins>", gate + "    </plugins>"), encoding="utf-8")
    api = copy / "src/main/java/org/acme/clinic/guarded/GuardedApi.java"
    api.parent.mkdir(parents=True, exist_ok=True)
    api.write_text('package org.acme.clinic.guarded;\n\nimport org.acme.guard.Guard;\n\npublic class GuardedApi {\n    @Guard("isStaff()")\n    public void a() {}\n}\n', encoding="utf-8")
    (root / "reviewed").mkdir(parents=True, exist_ok=True)
    (root / "reviewed/GuardMode.java").write_text(GUARD_MODE, encoding="utf-8")
    manifest = base_manifest()
    manifest["review_records"] = manifest["review_records"][1:]
    manifest["transformations"] = [t for t in manifest["transformations"] if t["id"] in ("t-new", "t-guard", "t-prop-new", "t-retire")]
    manifest = author_manifest(root, copy, manifest)
    doc_extra = write_manifest(root, manifest)["decided_repairs"]
    doc_extra["applies"] = ["ADR-202", "ADR-203"]
    text = (root / "decisions.yaml").read_text(encoding="utf-8")
    text += specimens.decisions_yaml({"decided_repairs": doc_extra})
    (root / "decisions.yaml").write_text(text, encoding="utf-8")
    script = HERE / "bootstrap-destination.py"
    env = dict(os.environ)
    stub_mvn(td / "bin")
    env["PATH"] = str(td / "bin") + os.pathsep + env.get("PATH", "")
    p = subprocess.run([sys.executable, str(script), "--root", str(root)], text=True, capture_output=True, env=env)
    check(p.returncode == 0, "bootstrap with decided repairs must pass: %s %s" % (p.stdout[-300:], p.stderr[-600:]))
    b = load_json(root / "evidence/producers/bootstrap.json")
    rec = load_json(root / "evidence/producers/decided-repairs.json") if (root / "evidence/producers/decided-repairs.json").is_file() else {}
    check(b.get("decided_repairs", {}).get("declared") is True and b["decided_repairs"]["receipt_sha256"] == sha256_file(root / "evidence/producers/decided-repairs.json"),
          "bootstrap binds the receipt: %s" % b.get("decided_repairs"))
    check(rec.get("counts") == {"applied": 4, "already-applied": 0, "refused": 0}, "all four rows applied at bootstrap: %s" % rec.get("counts"))
    check(rec.get("effective_configuration", {}).get("checked") is True, "the bootstrap verifies the effective model after its last pom pass")
    check('@Guard("@mode.off() or isStaff()")' in (root / "src/main/java/org/acme/clinic/guarded/GuardedApi.java").read_text(encoding="utf-8"), "the imported source was rewritten")
    check("<id>gate</id>" not in (root / "pom.xml").read_text(encoding="utf-8") and "rhoai3:generated-tests:begin" in (root / "pom.xml").read_text(encoding="utf-8"),
          "the retirement survives the parity block rewrite and the block keeps its markers")
    check(any(c.get("op") == "decided-repair" for c in b["changes"]), "applied repairs appear in the bootstrap changes")
    check(lib.receipt_gaps(root, __import__("planner.decisions", fromlist=["load_decisions"]).load_decisions(root), for_baseline=True) == [], "the baseline may be recorded")
    h = tree_hash(root)
    p = subprocess.run([sys.executable, str(script), "--root", str(root)], text=True, capture_output=True, env=env)
    rec = load_json(root / "evidence/producers/decided-repairs.json")
    check(p.returncode == 0 and tree_hash(root) == h, "a second bootstrap leaves the product tree identical: %s" % p.stderr[-300:])
    check(rec["counts"] == {"applied": 0, "already-applied": 4, "refused": 0} and len(rec["runs"]) == 2, "second bootstrap records already-applied: %s" % rec["counts"])
    # admission sees the repairs: the receipt carries the classification and seals the receipt ...
    from planner import admission
    from planner.canonical import digest
    from planner.decisions import load_decisions
    from planner.pins import load_pins

    write_canonical(root / "evidence/planning/worklist.json", {})
    composed = admission.compose_receipt(root)
    check((composed.get("decided_repairs") or {}).get("classification") == "autonomous_execution_with_predecided_repairs"
          and composed["seals"].get("decided_repairs") == sha256_file(root / "evidence/producers/decided-repairs.json"),
          "admission records the classification and seals the receipt: %s" % composed.get("decided_repairs"))
    # ... and a refused row keeps it INCONCLUSIVE
    bundle = load_json(root / "evidence/planning/evidence-bundle.json")
    wl = {"measure": {"known": True, "tuple": [0, 0, 0]}, "evidence_bundle_sha256": digest(bundle)}
    names = lambda: {b["class"] for b in admission.blocks_for(root, bundle, wl, load_decisions(root), load_pins(root), digest(bundle))}  # noqa: E731
    check(not any(n.startswith("DECIDED") for n in names()), "an applied set opens no admission block: %s" % names())
    bad = load_json(root / "evidence/producers/decided-repairs.json")
    bad["rows"][0]["status"] = "refused"
    bad["rows"][0]["refusal"] = {"class": "REPAIR_FILE_CONFLICT", "detail": "x"}
    write_canonical(root / "evidence/producers/decided-repairs.json", bad)
    check({"DECIDED_REPAIR_REFUSED", "DECIDED_REPAIRS_STALE"} <= names(), "a refused (and rebound) receipt blocks admission: %s" % names())


def case_engine_is_specimen_agnostic() -> None:
    for path in (Path(dr.__file__), GOLDEN / ".hermes/lib/planner/decided_repairs.py", dr.TOOL):
        low = path.read_text(encoding="utf-8").lower()
        for word in ("petclinic", "preauthorize", "jacoco", "securitymode", "owner", "userdefinition", "spring"):
            check(word not in low, "%s names the specimen identifier %r" % (path.name, word))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="decided-repairs-") as td:
        t = Path(td)
        for name, fn in (("clean", case_clean_apply_and_idempotent), ("conflicts", case_conflicts), ("sites", case_sites),
                         ("review", case_applicability_and_review), ("admission", case_admission), ("boot", case_bootstrap_integration)):
            (t / name).mkdir()
            try:
                fn(t / name)
            except Exception as exc:  # a crash is a failure with its cause
                import traceback

                FAILS.append("%s crashed: %s\n%s" % (name, exc, traceback.format_exc()))
    case_engine_is_specimen_agnostic()
    if FAILS:
        for f in FAILS:
            print("FAIL: " + f, file=sys.stderr)
        return 1
    print("OK: decided-repairs (every kind applies on a synthetic project; a second run is byte-identical and already-applied; "
          "new-file, property, dependency, annotation, import and execution conflicts are typed refusals that write nothing; "
          "only literal tokens change and repairs survive; a retirement removes only the decided execution, keeps the thresholds "
          "as retired-not-achieved and is checked on the effective model; review reuse needs the exact reviewed bytes, "
          "applicability and two seats; admission and the baseline see missing, stale and refused receipts; the bootstrap applies "
          "and binds it; the engine names no specimen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
