#!/usr/bin/env python3
"""Build an OpenCode task packet from tasks.md (V7 model routing + K2 evidence).

Prints a single packet string on stdout for:
  opencode run "<packet>" -m <worker> ...

Used by supervisor.sh so mechanical rewrite/infer coding runs on the
worker (Qwen) without MiniMax applying file edits directly.

K2: when migration/mta-findings.json is available, inject a bounded
Analysis evidence section (rule message + file:line + code snip) so the
worker sees MTA remediation guidance, not bare Findings ids.

K10: when migration/hints/<rule-id>.md exists for a Findings id, inject a
bounded Solved-example hints section (caps in hint-inject.py).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# K2 — mandatory hard caps (64K worker context). Tune only with A/B evidence.
MAX_EVIDENCE_INCIDENTS = 6
MAX_EVIDENCE_CHARS = 400  # per message OR code field
# Combined message+code budget across the whole evidence section (K2-CAP):
# equals "≤6 incidents × ≤400 chars" as documented — not 6×(400+400).
MAX_EVIDENCE_CONTENT_CHARS = MAX_EVIDENCE_INCIDENTS * MAX_EVIDENCE_CHARS

# K10 — import sibling helper (same harness dir).
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from hint_inject import format_hints  # type: ignore
except ImportError:
    try:
        import importlib.util

        _hp = Path(__file__).resolve().parent / "hint-inject.py"
        _spec = importlib.util.spec_from_file_location("hint_inject", _hp)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore
        assert _spec and _spec.loader
        _spec.loader.exec_module(_mod)
        format_hints = _mod.format_hints  # type: ignore
    except Exception:  # pragma: no cover

        def format_hints(rule_ids, root=None):  # type: ignore
            return ""

# O-ORACLEDERIVE — filesystem Oracle (never default undeclared → present).
try:
    from oracle_derive import derive_oracle, inferabsent_blocks  # type: ignore
except ImportError:
    try:
        import importlib.util

        _odp = Path(__file__).resolve().parent / "oracle_derive.py"
        _ods = importlib.util.spec_from_file_location("oracle_derive", _odp)
        _odm = importlib.util.module_from_spec(_ods)  # type: ignore
        assert _ods and _ods.loader
        _ods.loader.exec_module(_odm)
        derive_oracle = _odm.derive_oracle  # type: ignore
        inferabsent_blocks = _odm.inferabsent_blocks  # type: ignore
    except Exception:  # pragma: no cover

        def derive_oracle(body, **_kw):  # type: ignore
            return "absent"

        def inferabsent_blocks(**_kw):  # type: ignore
            return False


def task_block(text: str, tid: str) -> tuple[str, str]:
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        return title, text[start:end].strip()
    return "", ""


def field(body: str, *names: str) -> str:
    for name in names:
        # O-PACKETFIELD: M3 often writes **Class: rewrite** (colon inside
        # bold). The older **Class**: rewrite form is still accepted.
        m = re.search(
            rf"^\*\*{re.escape(name)}\s*:\s*(.+?)\*\*\s*$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
        m = re.search(
            rf"^\*\*{re.escape(name)}\*\*\s*:?\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
        m = re.search(
            rf"^{re.escape(name)}\s*:\s*(.+)$",
            body,
            re.M | re.I,
        )
        if m:
            return m.group(1).strip()
    return ""


def parse_finding_ids(findings_field: str) -> list[str]:
    """Split a Findings: field into rule-id tokens (skip placeholders)."""
    if not findings_field:
        return []
    raw = findings_field.strip()
    if raw.startswith("(") or raw.lower() in {"n/a", "none", "-", "see tasks.md"}:
        return []
    parts = re.split(r"[,;\s]+", raw)
    out: list[str] = []
    for p in parts:
        p = p.strip().strip("`")
        if not p or p.startswith("("):
            continue
        # Drop prose glue words that sometimes appear in Findings lines
        if p.lower() in {"and", "or", "see", "tasks.md", "findings"}:
            continue
        out.append(p)
    return out


def resolve_findings_path(tasks_path: Path, explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    candidates = [
        Path("migration/mta-findings.json"),
        tasks_path.resolve().parent / "migration" / "mta-findings.json",
        tasks_path.resolve().parent.parent / "migration" / "mta-findings.json",
        tasks_path.resolve().parent.parent.parent / "migration" / "mta-findings.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _uri_display(uri: str) -> str:
    u = (uri or "?").replace("file:///", "/").replace("file://", "")
    # Prefer a repo-relative-looking tail when absolute
    for marker in ("/src/", "/projects/legacy/", "/projects/modernized/"):
        i = u.find(marker)
        if i >= 0:
            if marker == "/src/":
                return u[i + 1 :]  # src/...
            return u[i + len(marker) :]
    return u


def _trim(s: str, n: int = MAX_EVIDENCE_CHARS) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _rule_matches(rid: str, wanted: list[str]) -> bool:
    """Exact → prefix → guarded substring (K2-MATCH). No bare `w in rid`.

    Prefix/substring require a rule-id-shaped token (contains '-'): prose
    like `springboot` must not pull `springboot-web-to-quarkus-*`.
    """
    for w in wanted:
        if rid == w:
            return True
    for w in wanted:
        if "-" in w and len(w) >= 8 and rid.startswith(w):
            return True
    for w in wanted:
        if "-" in w and len(w) >= 12 and w in rid:
            return True
    return False


def _snip_norm(snip: str) -> str:
    return re.sub(r"\s+", " ", (snip or "").strip())


def _is_low_value_config_snip(uri: str, line: str, snip: str) -> bool:
    """K2-SNIP: skip head-of-file snips for pom/props/yaml (budget waste)."""
    u = (uri or "").lower()
    if not any(
        u.endswith(x) for x in ("pom.xml", ".properties", ".yaml", ".yml", ".xml")
    ):
        return False
    try:
        ln = int(line)
    except ValueError:
        ln = 999
    if ln <= 5:
        return True
    s = snip.lstrip()
    return bool(
        s.startswith("<?xml")
        or s.startswith("<project")
        or s.startswith("#")
        or s.startswith("<!--")
    )


def _inc_dict(rid: str, desc: str, inc: dict) -> dict:
    msg = (inc.get("message") or desc or "").strip()
    snip = (inc.get("codeSnip") or inc.get("code") or "").strip()
    uri = _uri_display(str(inc.get("uri") or "?"))
    line = str(inc.get("lineNumber") or "?")
    if snip and _is_low_value_config_snip(uri, line, snip):
        snip = ""
    return {
        "rule": rid,
        "uri": uri,
        "line": line,
        "message": msg,
        "code": snip,
    }


def collect_evidence(findings_path: Path, wanted: list[str]) -> list[dict]:
    """Return up to MAX_EVIDENCE_INCIDENTS incidents (K2-RR: round-robin)."""
    if not wanted:
        return []
    try:
        data = json.loads(findings_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    # Preserve Findings-field order: group incidents per matched rule.
    by_rule: dict[str, list[dict]] = {}
    order: list[str] = []
    for rs in data:
        if not isinstance(rs, dict):
            continue
        for rid, v in (rs.get("violations") or {}).items():
            if not _rule_matches(rid, wanted):
                continue
            desc = (v.get("description") or "").strip()
            bucket = by_rule.setdefault(rid, [])
            if rid not in order:
                order.append(rid)
            for inc in v.get("incidents") or []:
                if isinstance(inc, dict):
                    bucket.append(_inc_dict(rid, desc, inc))

    # Prefer order of tokens in the Findings field when possible.
    preferred: list[str] = []
    for w in wanted:
        for rid in order:
            if rid not in preferred and _rule_matches(rid, [w]):
                preferred.append(rid)
    for rid in order:
        if rid not in preferred:
            preferred.append(rid)

    cursors = {rid: 0 for rid in preferred}
    hits: list[dict] = []
    # Round 1+: one incident per rule per pass until cap (K2-RR).
    while len(hits) < MAX_EVIDENCE_INCIDENTS:
        progressed = False
        for rid in preferred:
            if len(hits) >= MAX_EVIDENCE_INCIDENTS:
                break
            bucket = by_rule.get(rid) or []
            i = cursors[rid]
            if i < len(bucket):
                hits.append(bucket[i])
                cursors[rid] = i + 1
                progressed = True
        if not progressed:
            break
    return hits


def format_evidence(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = [
        "Analysis evidence (from MTA — the authoritative description of the problem):"
    ]
    content_used = 0
    seen_snips: set[str] = set()
    for h in hits:
        lines.append(f"- {h['rule']} at {h['uri']}: line {h['line']}")
        msg = _trim(h["message"]) if h["message"] else ""
        code = _trim(h["code"]) if h["code"] else ""
        # K2-SNIP: drop identical codeSnips after the first (budget binds first).
        if code:
            key = _snip_norm(code)
            if key in seen_snips:
                code = ""
            else:
                seen_snips.add(key)
        # K2-CAP: combined message+code budget across the section.
        for label, chunk in (("message", msg), ("code", code)):
            if not chunk:
                continue
            room = MAX_EVIDENCE_CONTENT_CHARS - content_used
            if room <= 0:
                break
            if len(chunk) > room:
                chunk = chunk[: max(0, room - 1)].rstrip() + "…"
            lines.append(f"  {label}: {chunk}")
            content_used += len(chunk)
        if content_used >= MAX_EVIDENCE_CONTENT_CHARS:
            break
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: task-packet.py <tasks.md> <T-xxx> [worker-model] [mta-findings.json]",
            file=sys.stderr,
        )
        return 2
    path, tid = sys.argv[1], sys.argv[2]
    worker = sys.argv[3] if len(sys.argv) > 3 else "qwen27b/qwen3-6-27b"
    # Optional 4th arg is findings path; if argv[3] looks like a json path, treat as findings
    findings_arg: str | None = None
    if len(sys.argv) > 4:
        findings_arg = sys.argv[4]
    elif len(sys.argv) > 3 and sys.argv[3].endswith(".json"):
        worker = "qwen27b/qwen3-6-27b"
        findings_arg = sys.argv[3]

    tasks_path = Path(path)
    text = tasks_path.read_text(encoding="utf-8", errors="replace")
    title, body = task_block(text, tid)
    if not body:
        print(f"FATAL: task {tid} not found in {path}", file=sys.stderr)
        return 1
    cls = field(body, "Class", "Type") or "infer"
    cls_m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    cls = cls_m.group(1).lower() if cls_m else "infer"
    goal = field(body, "Goal") or title
    # O-ESCALORACLE / O-SHAPEDECL: carry deliverable shape + oracle so
    # MiniMax escalation cannot fabricate a deletion target (F-23).
    shape = (field(body, "Shape") or "").lower().strip()
    if shape not in {"create", "modify", "remove", "structure", "verify", "harvest"}:
        blob = f"{title}\n{body}".lower()
        if re.search(r"\b(remove|removal|delete|deletion|drop|erase)\b", blob):
            shape = "remove"
        elif re.search(r"\b(harvest|openrewrite|staging)\b", blob):
            shape = "harvest"
        elif re.search(r"\b(structure|gitkeep|scaffold)\b", blob):
            shape = "structure"
        elif re.search(r"\b(characterization|characterize|verify|assert)\b", blob):
            shape = "verify"
        elif re.search(r"\b(create|creating|add|adding|introduce|introducing)\b", blob):
            shape = "create"
        else:
            shape = "modify" if cls == "rewrite" else "modify"
    # O-ORACLEDERIVE (§2.1): derive from filesystem — legacy test for Target?
    # Target in destination? Never silently default undeclared → present.
    # Shape=remove still forces absent (deletion success = verified absence).
    oracle = derive_oracle(body, root=Path.cwd())
    if shape == "remove":
        oracle = "absent"
    # K2-LABEL: M3 sometimes writes **Finds**: / **Finding**: — accept aliases
    # so evidence injection is not silently skipped (Poll 13).
    findings = field(body, "Findings", "Finds", "Finding") or "(see tasks.md)"
    acceptance = field(body, "Acceptance") or "mvn -q clean test passes; commit ready"
    # Keep packet bounded — full body is attached via -f tasks.md
    design = ""
    for label in ("Target design", "Target Design", "Target", "Design"):
        chunk = field(body, label)
        if chunk:
            design = chunk
            break
    if not design:
        # First 1200 chars of body as design context
        design = re.sub(r"\s+", " ", body)[:1200]

    # O-TGTNAME: extract destination .java basenames from the task body so the
    # worker cannot invent CartResource when the plan says CartEndpoint.
    # O-STRUCTTGT: Shape=structure / Target .gitkeep must NOT scrape Absorbs
    # (or other later-story) .java paths as mandatory destinations — that made
    # Qwen harvest full entity packages on package-structure seats (v3 T-003).
    # O-STRUCTJAVA: Shape=structure + Target-design .java (non package-info)
    # is a plan defect (plan-lint RED at M3). Detect before dest_line so we do
    # not mandate .gitkeep while Goal lists Panache/harvest .java Targets.
    blob_for_paths = f"{title}\n{body}"
    gitkeep_paths = sorted(
        set(
            re.findall(
                r"src/(?:main|test)/[A-Za-z0-9_./-]*/\.gitkeep", blob_for_paths
            )
        )
    )
    design_ends_gitkeep = bool(
        re.search(r"(?:^|[\s`→>-])\.?/?[\w./-]*\.gitkeep\b", design or "", re.I)
        or re.search(r"\.gitkeep\b", design or "")
    )
    structjava_paths: list[str] = []
    if shape == "structure":
        seen_sj: set[str] = set()
        in_tgt = False
        for line in (body or "").splitlines():
            hm = re.match(r"^\s*\*?\*?([A-Za-z][A-Za-z0-9 ]*?)\*?\*?\s*:", line)
            if hm:
                fld = hm.group(1).strip().lower()
                if fld.startswith("target") or fld == "design":
                    in_tgt = True
                elif fld in (
                    "absorbs",
                    "owns",
                    "class",
                    "shape",
                    "goal",
                    "findings",
                    "acceptance",
                    "oracle",
                    "out of scope",
                ):
                    in_tgt = False
            if not in_tgt:
                continue
            for m in re.finditer(
                r"(?:src/(?:main|test)/[A-Za-z0-9_./-]+\.java)"
                r"|\b([A-Za-z_][A-Za-z0-9_]+\.java)\b",
                line,
            ):
                p = m.group(0) if m.group(0).startswith("src/") else m.group(1)
                if not p or Path(p).name == "package-info.java":
                    continue
                if p not in seen_sj:
                    seen_sj.add(p)
                    structjava_paths.append(p)
    struct_tgt = (
        (shape == "structure" or bool(gitkeep_paths) or design_ends_gitkeep)
        and not structjava_paths
    )
    if structjava_paths:
        sample = ", ".join(structjava_paths[:3])
        more = "…" if len(structjava_paths) > 3 else ""
        dest_names = []
        dest_line = (
            f"- O-STRUCTJAVA plan defect: Shape=structure lists .java Targets "
            f"({sample}{more}) — do NOT create .gitkeep as the deliverable; "
            f"write /tmp/escalation-noaction-<tid>.txt with O-STRUCTJAVA and "
            f"STOP (O-NULLACTION) for M3 reshape to create/modify"
        )
        struct_tip = (
            f"\n- O-STRUCTJAVA: Shape=structure contradicts Target .java "
            f"deliverables ({sample}{more}). This is a plan defect — write "
            f"/tmp/escalation-noaction-<tid>.txt with O-STRUCTJAVA and STOP "
            f"(O-NULLACTION) so M3 can reshape to create/modify. Do NOT tip "
            f".gitkeep-only as satisfying convert/harvest/Panache Goals; do "
            f"NOT READ_THRASH inventing both .gitkeep and .java under structure."
        )
    elif struct_tgt:
        dest_names = gitkeep_paths or (
            [".gitkeep"] if design_ends_gitkeep or shape == "structure" else []
        )
        dest_line = (
            f"- Target destination path(s) are MANDATORY: {', '.join(dest_names)} "
            f"— create ONLY those package-structure files (O-TGTNAME/O-STRUCTTGT); "
            f"do NOT harvest or create entity/DTO .java classes from Absorbs/staging"
            if dest_names
            else (
                "- Shape=structure / .gitkeep Target: create package directories + "
                ".gitkeep only (O-TGTNAME/O-STRUCTTGT); do NOT harvest entity classes"
            )
        )
        struct_tip = (
            "\n- O-STRUCTTGT: Shape=structure / Target .gitkeep — create package dirs + "
            ".gitkeep only; do NOT harvest entity classes. Absorbs .java cites are "
            "later-story ownership markers, not this task's deliverable."
        )
    else:
        dest_names = sorted(
            {
                Path(m).name
                for m in re.findall(
                    r"src/(?:main|test)/[A-Za-z0-9_./-]+\.java", blob_for_paths
                )
            }
        )
        dest_line = (
            f"- Target destination basename(s) are MANDATORY: {', '.join(dest_names)} "
            f"— create/edit exactly those file names (O-TGTNAME; never rename "
            f"Endpoint→Resource or invent alternate class names)"
            if dest_names
            else "- When Target design names a destination .java path, use that exact basename"
        )
        struct_tip = ""
    # O-INFERFIRSTWRITE: multi-file Class=infer seats thrash on reads after
    # harvest/preseed — name one leaf Target + concrete first import delta.
    inferfirst_tip = ""
    if cls == "infer" and not struct_tgt and len(dest_names) >= 2:
        leaf = next(
            (
                n
                for n in dest_names
                if re.search(
                    r"RowMapper|Extractor|ParameterSource|JdbcPet\.java$", n, re.I
                )
            ),
            dest_names[0],
        )
        inferfirst_tip = (
            f"\n- O-INFERFIRSTWRITE: multi-file Class=infer — FIRST mutate MUST "
            f"edit/write one leaf Target (`{leaf}`) with a concrete import/API "
            f"delta (e.g. drop `org.springframework.jdbc.*` / add "
            f"`javax.sql.DataSource` + `jakarta.inject.Inject`) BEFORE touring "
            f"the full sibling stack. After Targets already exist on disk, "
            f"harvest-from-staging alone is NOT a first-write "
            f"(pair O-FIRSTMUTBASH). Do not read all Targets first."
        )
    harvest_tip = (
        ""
        if struct_tgt
        else (
            "\n- For Class rewrite: FIRST action when a Target .java is missing — run "
            ".hermes/skills/migration-harness/scripts/harvest-from-staging.sh "
            "<package-relative-path> (works for src/main and src/test). "
            "O-HARVESTFULLPATH: pass package-relative only "
            "(e.g. repository/jdbc/JdbcPet.java) — NEVER "
            "src/main/java/<legacyPackage>/… from Target design (script also "
            "normalizes full paths, but prefer relative). Do not "
            "re-run OpenRewrite. Do not invent assertThat(true) stubs "
            "(G-PLACE / O-HARVESTSTALL)."
        )
    )
    # O-STAGEDPATH (W4-043b): staging mirrors LEGACY package layout, not target.
    # Workers that `ls migration/staging/.../<targetPackage>/...` get empty and
    # falsely claim already-complete (v3 S02 T-008 User). Emit explicit paths.
    staged_paths: list[str] = []
    if not struct_tgt:
        src_paths = re.findall(
            r"(?im)(?:\*\*)?(?:Source|Absorbs)(?:\*\*)?\s*:\s*`?(/?(?:projects/legacy/)?src/(?:main|test)/java/[A-Za-z0-9_./-]+\.java)`?",
            blob_for_paths,
        )
        for sp in src_paths:
            rel = sp
            # Strip /projects/legacy/ prefix if present
            rel = re.sub(r"^/?projects/legacy/", "", rel)
            rel = rel.lstrip("/")
            if not rel.startswith("src/"):
                # bare path under legacy root
                if "src/" in rel:
                    rel = rel[rel.index("src/") :]
                else:
                    continue
            staged = f"migration/staging/{rel}"
            if staged not in staged_paths:
                staged_paths.append(staged)
        # Also derive from Source basename + common legacy model path in Owns/Target
        if not staged_paths:
            for m in re.finditer(
                r"(?im)(?:\*\*)?Source(?:\*\*)?\s*:\s*`?([^`\n]+)`?",
                blob_for_paths,
            ):
                raw = m.group(1).strip()
                if raw.endswith(".java") and "src/" in raw:
                    rel = raw[raw.index("src/") :]
                    staged = f"migration/staging/{rel}"
                    if staged not in staged_paths:
                        staged_paths.append(staged)
    staged_block = ""
    if staged_paths:
        staged_block = "Staged-source (legacy package layout under migration/staging — NOT targetPackage):\n"
        for sp in staged_paths[:8]:
            staged_block += f"- {sp}\n"
    staged_tip = (
        "\n- O-STAGEDPATH: migration/staging mirrors the LEGACY package tree. "
        "Use the Staged-source path(s) above (or `find migration/staging -name "
        "'<Class>.java'`). NEVER construct staging paths with targetPackage "
        "(e.g. com/demo/model) — empty ls ≠ already harvested."
        if (not struct_tgt and (staged_paths or re.search(r"(?i)\bharvest\b|staging|Source\s*:", blob_for_paths)))
        else ""
    )
    # O-HTTPPORT-TIP: properties tasks must not transplant legacy server.port
    # (e.g. 9966) into quarkus.http.port when k8s deploy contract is 8080.
    props_blob = f"{goal}\n{design}\n{findings}".lower()
    httpport_tip = (
        "\n- O-HTTPPORT: when editing application*.properties, keep "
        "quarkus.http.port aligned with k8s containerPort / QUARKUS_HTTP_PORT "
        "(usually 8080). NEVER copy legacy Spring server.port (e.g. 9966) into "
        "quarkus.http.port — sensors RED O-HTTPPORT / http_port_deploy_contract."
        if (
            "application.properties" in props_blob
            or "server.port" in props_blob
            or "quarkus.http.port" in props_blob
            or re.search(r"\bproperties\b", props_blob)
        )
        else ""
    )
    # O-DSKIND tip: first @Entity / hibernate-orm harvest needs jdbc + db-kind
    # in the same commit family (or harness ensure-dskind will patch post-commit).
    dskind_tip = (
        "\n- O-DSKIND: when harvesting @Entity / adding quarkus-hibernate-orm, ALSO "
        "add quarkus-jdbc-h2 + quarkus-jdbc-postgresql and profiled "
        "quarkus.datasource.db-kind (%dev/%test=h2, default/prod=postgresql). "
        "Without jdbc/db-kind, Quarkus ConfigurationException fails milestone "
        "(Datasource must be defined). Prefer %dev/%test "
        "hibernate-orm.database.generation=drop-and-create until a seed story."
        if (
            re.search(r"\bentity\b|@entity|hibernate|persistence|jpa|jakarta\.persistence", props_blob)
            or "model/" in props_blob
        )
        else ""
    )
    # O-M3PRESERVEDAO / W4-085a: Spring DAO throws are not on the Quarkus
    # classpath — remap via exact-symbol table (never substring invent) or
    # drop throws; never preserve DataAccessException / add spring-tx.
    preservedao_tip = (
        "\n- O-M3PRESERVEDAO / O-DAOEXMAP (W4-085a): when harvesting Spring "
        "repository/DAO interfaces into a Quarkus pom (no spring-boot), "
        "remap per EXACT symbol (never substring replace "
        "`DataAccessException` inside longer names):"
        "\n  | legacy | target |"
        "\n  | `DataAccessException` | `jakarta.persistence.PersistenceException` |"
        "\n  | `EmptyResultDataAccessException` | `jakarta.persistence.NoResultException` "
        "(or documented null-return) |"
        "\n  | `DataRetrievalFailureException` | `jakarta.persistence.PersistenceException` |"
        "\n  | `ObjectRetrievalFailureException` | `jakarta.persistence.EntityNotFoundException` |"
        "\n  Or omit throws. NEVER invent `EmptyResultPersistenceException` / "
        "`*PersistenceException` under `org.springframework.*`; NEVER invent a "
        "local `DataAccessException` stub; NEVER add spring-tx/dao/jdbc/orm "
        "(O-JDBCREGRESS / O-HYGIENEWORKER / O-FIDELITYDAO / O-SPRINGRESIDUE)."
        if (
            re.search(
                r"dataaccessexception|dataretrievalfailure|"
                r"objectretrievalfailure|emptyresultdataaccess|"
                r"org\.springframework\.dao|spring\.dao|"
                r"\brepositor|\bdao\b|spring-(?:tx|dao|jdbc)",
                props_blob,
            )
            or re.search(r"repository/", blob_for_paths.lower())
        )
        else ""
    )
    # O-CDIPARTIAL / O-JDBCHARVESTAPI / O-SPRINGRESIDUE: harvest stamping
    # @ApplicationScoped is not done — must finish Autowired→Inject AND
    # drop ALL org.springframework under src/main/java.
    # O-MMSCOPEQUIT: MiniMax must not scope-quit mid-stack when a sibling
    # already proves Agroal/java.sql — finish residue=0 in-seat.
    cdipartial_tip = (
        "\n- O-CDIPARTIAL / O-JDBCHARVESTAPI / O-SPRINGRESIDUE: after "
        "harvest-from-staging.sh, CDI convert is INCOMPLETE while any Target "
        "@ApplicationScoped (or sibling scope) still has @Autowired or zero "
        "jakarta @Inject, OR any `org.springframework` remains under "
        "`src/main/java` (comments ignored). REQUIRED before exit: (1) "
        "@Autowired → @Inject (constructor preferred); (2) remove "
        "org.springframework.jdbc|dao|orm|beans|data|context imports — rewrite "
        "NamedParameterJdbcTemplate / SimpleJdbcInsert / JdbcTemplate to "
        "Agroal DataSource + java.sql (or EntityManager) — NEVER add "
        "spring-jdbc to green compile (O-JDBCREGRESS); (3) never invent "
        "`*PersistenceException` under `org.springframework.*` (W4-085a). "
        "Do NOT tip-accept / Already-satisfied / step_finish on residue; "
        "sensors RED O-CDIPARTIAL / O-JDBCHARVESTAPI / O-SPRINGRESIDUE."
        "\n- O-MMSCOPEQUIT: if ANY sibling Target already uses Agroal/"
        "DataSource + java.sql (or sensors RED O-JDBCHARVESTAPI / "
        "org.springframework residue on remaining Targets), do NOT exit with "
        "scope-quit / reclassification / task-splitting / human-approval "
        "narratives. Sensors refusing partial are not a scope defect — "
        "continue remaining Targets until residue=0 + GREEN, or honest "
        "sensor-RED / O-NULLACTION without asking to split the convert stack."
        "\n- O-TREEFIXSTUB: NEVER replace owned Targets with comment-only "
        "/* REMOVED */ husks or delete type bodies / interface methods to "
        "clear spring residue. Implement the full API with Agroal DataSource "
        "+ java.sql (or EntityManager). If same-package collaborators of "
        "Target files are not owned/deferred (O-COLLABOWN), prefer "
        "O-NULLACTION — tip-accept/sensors RED O-TREEFIXSTUB on stubs."
        "\n- O-COLLABOWN: every same-legacy-package type referenced by Target "
        "files must itself be an owned Target/Owns/Absorbs or explicitly "
        "Deferred/Out-of-scope — missing collaborators make convert "
        "compile-impossible; do not stub-nuke."
        "\n- O-AGROALHELPERSIG: when rewriting Spring JDBC → Agroal "
        "DataSource + java.sql, preserve staging *exact public* helper "
        "method names on the Impl class itself (`mapRow`, "
        "`create*ParameterSource`, `extractData`, …). Inline Spring "
        "RowMapper/ParameterSource as same-named *public* methods on the "
        "converted Impl — do NOT rename (mapRow→mapVetRow), privatize, "
        "or move-only onto a RowMapper collaborator. redesign-sig REDs "
        "missing names (O-REDESIGNSIG / O-IFACERENAME / O-AGROALHELPERSIG)."
        "\n- O-STEPFINISHRED: before step_finish / tip-accept / "
        "Already-satisfied / prose 'complete / ready for commit', run "
        "`.hermes/harness/sensors.sh task` (includes redesign-sig). If "
        "SENSOR RED (incl. O-AGROALHELPERSIG), do NOT exit 0 claiming "
        "done — keep editing until GREEN then "
        "`.hermes/harness/commit-gated.sh`, or stop with honest "
        "incomplete / sensor-RED (supervisor rewrites false rc=0→42)."
        "\n- O-ESCWSCOPEUTIL: NEVER create/harvest `src/main/**/util/*` or any "
        "path outside this task's Owns/Target (later-story util classes stay "
        "in migration/staging). Scope sensor removes untracked later-class "
        "dirt; tip REJECT if util collaborators land with a convert tip."
        if (
            re.search(
                r"@autowired|@inject|applicationscoped|cdi\b|"
                r"jdbc|namedparameterjdbctemplate|simplejdbcinsert|"
                r"spring\.jdbc|repository/jdbc|\brepositor|"
                r"org\.springframework|port\s*:?\s*reimplement",
                props_blob,
            )
            or re.search(r"repository/", blob_for_paths.lower())
        )
        else ""
    )
    # O-SDJPAHARVEST / O-SDJPAHARVESTONLY / O-T4SPRINGDATA / O-SDJPA-SKIP:
    # Spring Data → Panache must convert after harvest (not stop at Spring
    # Data dirt), or skip when Jpa* CDI already covers (Override-only).
    sdjpaharvest_tip = (
        "\n- O-T4SPRINGDATA / O-SDJPA-SKIP: when Quarkus pom has NO "
        "spring-data / quarkus-spring-data-* deps, do NOT burn seats "
        "harvesting SpringData* for compile-under-spring. Prefer "
        "**Port**: reimplement + Panache mapping, redesign/skip/defer, or "
        "Already-satisfied when ≥3 Jpa*RepositoryImpl @ApplicationScoped "
        "already cover domain repos and Override-only work is done/absent "
        "(O-SDJPA-SKIP / pair O-JDBCSKIP). If keeping Spring Data extends, "
        "pom MUST carry quarkus-spring-data-jpa."
        "\n- O-SDJPAHARVESTONLY: for Shape=create|modify Panache "
        "consolidate/convert, harvest-from-staging.sh is NOT task-complete. "
        "After harvest, BEFORE step_finish / tip-accept / Already-satisfied: "
        "(1) rewrite every Target Spring Data repo to "
        "PanacheRepository/PanacheRepositoryBase; (2) drop "
        "`org.springframework.data.*` / Spring `Repository` / method `@Query`; "
        "(3) implement Panache finder bodies + keep domain-repo contracts "
        "(O-SDJPAHARVEST). Do NOT exit 0 on Spring Data residue / Panache=0 "
        "dirt — sensors RED O-SDJPAHARVESTONLY; supervisor rewrites false "
        "rc=0→42 (O-STEPFINISHRED)."
        "\n- O-SDJPAHARVEST: Spring Data JPA → Panache consolidate/convert is "
        "NOT done when dest only `extends PanacheRepository<T>` with empty "
        "finder shells. REQUIRED: (1) keep staging domain-repo contract "
        "(`extends`/`implements` <DomainRepository> + "
        "PanacheRepository or PanacheRepositoryBase); (2) rewrite staging "
        "method `@Query` to Panache `find`/`list` default or class methods — "
        "NEVER park orphan `@NamedQuery` on the repository interface; "
        "(3) no hollow `ReturnType finder(...);` without a query body; "
        "(4) harvest staging `*RepositoryImpl` Override delete bodies with "
        "the Override interfaces (iface-only ≠ consolidate). Sensors + "
        "commit-hygiene RED O-SDJPAHARVEST. Prefer @ApplicationScoped class "
        "implementing domain iface + PanacheRepositoryBase when Override "
        "Impls need EntityManager."
        if (
            re.search(
                r"panache|spring\s*data|springdatajpa|jpa\.repository|"
                r"crudrepository|@query|namedquery|"
                r"consolidat.*repositor|repositor.*consolidat|"
                r"\boverride\b",
                props_blob,
            )
            or re.search(r"springdatajpa|SpringData\w+Repository", blob_for_paths)
        )
        else ""
    )
    # O-CHARORACLE: characterization Source→Target must exist under
    # migration/staging or /projects/legacy. Phantom oracle → READ_THRASH /
    # hollow MiniMax invent. Tip O-NULLACTION — do not fabricate G-PLACE.
    def _char_oracle_missing(blob: str) -> list[str]:
        is_char = bool(
            re.search(
                r"(?i)\bcharacterization\b|\bcharacterize\b|"
                r"\bport\s+legacy\s+.{0,40}\btest|\blegacy\s+test",
                blob,
            )
            or (
                re.search(r"(?i)\bsrc/test/", blob)
                and re.search(r"(?i)\b(test|assert|verify|pin)\b", blob)
            )
        )
        if not is_char:
            return []
        cited: list[str] = []
        seen: set[str] = set()
        for m in re.finditer(
            r"(?P<src>(?:/?projects/legacy/)?"
            r"src/test/java/[A-Za-z0-9_./-]+\.java)\s*(?:→|->)\s*"
            r"`?(?:src/test/java/[A-Za-z0-9_./-]+\.java)",
            blob,
        ):
            rel = re.sub(r"^/?projects/legacy/", "", m.group("src").lstrip("./"))
            if rel not in seen:
                seen.add(rel)
                cited.append(rel)
        for m in re.finditer(
            r"(?im)(?:\*\*)?(?:Source|Oracle\s*path|Legacy\s*test)(?:\*\*)?\s*:\s*`?"
            r"((?:/?projects/legacy/)?src/test/java/[A-Za-z0-9_./-]+\.java)",
            blob,
        ):
            rel = re.sub(r"^/?projects/legacy/", "", m.group(1).lstrip("./"))
            if rel not in seen:
                seen.add(rel)
                cited.append(rel)
        if not cited:
            return []
        roots = []
        for cand in (
            Path("migration/staging"),
            Path("/projects/legacy"),
            Path("legacy"),
            Path("../legacy"),
        ):
            try:
                if cand.is_dir():
                    roots.append(cand)
            except OSError:
                continue
        missing: list[str] = []
        for rel in cited:
            if any((base / rel).is_file() for base in roots):
                continue
            missing.append(rel)
        return missing

    _char_missing = _char_oracle_missing(blob_for_paths)
    charoracle_tip = (
        "\n- O-CHARORACLE: characterization oracle ABSENT from migration/staging "
        f"and legacy specimen ({', '.join(_char_missing[:3])}"
        f"{'…' if len(_char_missing) > 3 else ''}). Do NOT invent hollow / "
        "assertThat(true) / G-PLACE tests for a phantom Source→Target. "
        f"Write /tmp/escalation-noaction-{tid}.txt with one line "
        f"'O-CHARORACLE: oracle absent' and STOP (O-NULLACTION success). "
        "Re-plan M3 to drop the phantom char path or cite an existing "
        "staging/legacy test file."
        if _char_missing
        else ""
    )
    # O-PORTREIMPL: API-swap seats must treat work as re-implementation, not
    # transliteration. Pair plan-lint Port: declaration + mapping table.
    _port_m = re.search(
        r"(?im)^\*\*Port\*\*\s*:?\s*(rename|reimplement)\b"
        r"|^\*\*Port\s*:\s*(rename|reimplement)\*\*",
        blob_for_paths,
    )
    port = (
        next(g for g in _port_m.groups() if g).lower()
        if _port_m
        else ""
    )
    _port_signal = bool(
        re.search(
            r"(?i)panache|spring\s*data|springdatajpa|jdbctemplate|"
            r"namedparameterjdbctemplate|agroal",
            props_blob,
        )
        and shape in ("create", "modify")
    )
    portreimpl_tip = (
        "\n- O-PORTREIMPL: Port=reimplement — target API differs from staging "
        "(Spring Data→Panache / JDBC→Agroal). Do NOT stop at harvest-from-staging "
        "or empty Panache shells (O-SDJPAHARVESTONLY). Follow the task's API "
        "mapping table (per-type, never substring invent). Prefer convert-after-"
        "harvest in this seat, or honest O-NULLACTION if M3 omitted the mapping / "
        "split harvest vs convert. O-FIDELITYPORT: acceptance is redesign-sig / "
        "public signatures — NOT harvest-fidelity byte-match of Spring imports."
        if (port == "reimplement" or _port_signal)
        else ""
    )
    # O-REIMPLCREATE / O-RESTCREATE: Port=reimplement Shape=create ALWAYS gets
    # the create-procedure (harvest → mapping table → first-write anchor).
    # Charter §3.2 / C remainder — tip must fire even when Port was inferred
    # only from API-swap signals (no declared Port line yet).
    _reimpl_create = (port == "reimplement" or _port_signal) and shape == "create"
    _create_anchor = dest_names[0] if dest_names else "the Target .java basename"
    reimplcreate_tip = (
        f"\n- O-REIMPLCREATE / O-RESTCREATE: Port=reimplement Shape=create — "
        f"CREATE procedure (mandatory order): (1) FIRST write: run "
        f"`harvest-from-staging.sh` for Target `{_create_anchor}` (or write that "
        f"basename) — Convert when dest is missing is create-from-legacy / "
        f"harvest-then-convert, NOT noop or Already-satisfied; (2) cite and "
        f"apply the task's **API mapping** table (legacy→target rows; per-type, "
        f"never substring invent); (3) first-write anchor before sibling tour "
        f"(O-CREATEFIRSTMUT / O-INFERFIRSTWRITE). Acceptance regime is "
        f"redesign-sig / public signatures (O-FIDELITYPORT) — not byte-match."
        if _reimpl_create
        else ""
    )
    # O-INFERABSENT / O-ORACLEDERIVE: plan defect when infer + derived-absent
    # without Shape=create|verify or Proceed: O-NULLACTION.
    inferabsent_tip = (
        f"\n- O-INFERABSENT: Class=infer + derived Oracle=absent (no legacy test "
        f"for Target and Target missing from destination). This is a plan "
        f"defect — write /tmp/escalation-noaction-{tid}.txt with O-INFERABSENT "
        f"and STOP (O-NULLACTION). M3 must reshape to Shape=create "
        f"(create-procedure), Shape=verify (deferral), or Proceed: O-NULLACTION."
        if inferabsent_blocks(
            cls=cls, oracle=oracle, shape=shape, body=body
        )
        else ""
    )

    evidence_block = ""
    fpath = resolve_findings_path(tasks_path, findings_arg)
    wanted: list[str] = []
    if fpath is not None:
        wanted = parse_finding_ids(findings)
        evidence_block = format_evidence(collect_evidence(fpath, wanted))
        # K2-LABEL: never silently omit evidence when Findings ids were parsed.
        if wanted and not evidence_block.strip():
            print(
                f"WARN: {tid}: K2 no evidence resolved for {len(wanted)} Findings "
                f"id(s) — check label / mta-findings.json match (Poll 13)",
                file=sys.stderr,
            )

    evidence_section = f"\n{evidence_block}\n" if evidence_block else "\n"
    # K10: solved-example hints keyed by Findings rule id (bounded).
    hint_ids = wanted or parse_finding_ids(findings)
    hint_root = tasks_path.resolve().parent
    if (hint_root / "migration" / "hints").is_dir():
        root_for_hints = hint_root
    elif (hint_root.parent / "migration" / "hints").is_dir():
        root_for_hints = hint_root.parent
    else:
        root_for_hints = Path(".")
    hints_block = format_hints(hint_ids, root_for_hints) if hint_ids else ""
    hints_section = f"\n{hints_block}\n" if hints_block else ""

    port_line = f"Port: {port}\n" if port else ""
    packet = f"""Task ID: {tid}
Class: {cls}
Shape: {shape}
{port_line}Oracle: {oracle}
Goal: {goal}
Findings: {findings}{evidence_section}{hints_section}Target Design: {design}
{staged_block}Constraints:
- Follow AGENTS.md and the repo skills; no scope creep
- Package rename is full legacyPackage → targetPackage prefix replace (never invent targetPackage.coolstore)
{dest_line}{struct_tip}{inferfirst_tip}
- O-IFACERENAME / O-REDESIGNSIG: preserve legacy *public method names* verbatim from migration/staging (even if misspelled or semantically odd, e.g. getAllSpecialtys, addOwner on UserRestController). Never rename methods for grammar/clarity — redesign-sig will RED and block commit.
- O-ESCALORACLE: Shape={shape} Oracle={oracle}. If Oracle=absent / Shape=remove: success is verified ABSENCE of named targets — do NOT create a file just to delete it, and do NOT invent deletion targets not listed in Owns/Target.
- Never git add or commit .hermes/ or migration/staging/ (harness/runtime only; O-HERMNEST){harvest_tip}{httpport_tip}{dskind_tip}{preservedao_tip}{cdipartial_tip}{sdjpaharvest_tip}{portreimpl_tip}{reimplcreate_tip}{inferabsent_tip}{charoracle_tip}{staged_tip}
- Before adding a Maven dependency: run python3 .hermes/harness/verify-dep.py <groupId> <artifactId> [version] (K8 advisory WARN only — factory resolve is authority).
- Out-of-scope needs discovered mid-task: append via `python3 .hermes/harness/append-discovered.py {tid} <file-or-area> <one-line-need>` (K9) — do NOT act on them (scope sensor reverts). Never confuse with migration/debt.md.
- Worker model for this run is {worker}
Inputs: tasks.md (attached), AGENTS.md (attached), migration/staging when harvesting
Acceptance: {acceptance}
Out of scope: do not push; do not start other tasks; finish with changes ready for a commit whose message STARTS with '{tid}:'
"""
    print(packet.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
