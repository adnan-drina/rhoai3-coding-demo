#!/usr/bin/env python3
"""V6 P2.4 already-complete probe (strict).

Exit 0 and print `REASON` when the supervisor may skip opencode.
Exit 1 when the task must still run.

V6 cart evidence: the previous bash heuristic treated the first Capitalized
word in the task body as a class name (`Convert`, `Port`) and, because those
.java files do not exist, auto-committed "ALREADY COMPLETE — Convert already
absent" for real CDI conversion work. That is forbidden.

Allowed skip paths (only):
1. preserve: token that is the *subject* of the task (title or Goal /
   Acceptance / Target design — O-AC2) is already present in the tree
   (and in k8s/ when STORY_DEPLOY=true for ENV_STYLE tokens). Waiver
   prose must not trigger this path. O-AC3: blocked when Target design
   names a destination path that is still missing (class/config conversion).
   O-AC-NONJAVA: non-.java Targets (properties/yaml/k8s) never preserve-skip.
2. Explicit removal task (title or body) naming a concrete src/.../*.java
   path whose basename is absent under src/main/java and src/test/java.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(os.environ.get("ALREADY_COMPLETE_ROOT", ".")).resolve()


def task_body(tasks_file: Path, tid: str) -> tuple[str, str]:
    text = tasks_file.read_text(encoding="utf-8", errors="replace")
    heads = list(
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+[A-Za-z]*)\s*:\s*(.+)$", text, re.M)
    )
    for i, m in enumerate(heads):
        if m.group(1) != tid:
            continue
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[start:end]
        # O-AC2: last-task bodies used to swallow story-level waiver appendices
        # (e.g. "<endpointEnv> … waived"), falsely triggering preserve skip.
        body = re.split(
            r"^##\s+(Story Scope Waivers|Waivers|Notes|Appendix)\b",
            body,
            maxsplit=1,
            flags=re.M | re.I,
        )[0]
        return title, body
    return "", ""


def preserve_is_task_subject(title: str, body: str, item: str) -> bool:
    """O-AC2: preserve fast-path only when the task is ABOUT that item.

    Mentions in waiver prose, or incidental body text outside Goal /
    Acceptance / Target design, must not skip real work.
    """
    if item in title:
        return True
    focus_parts = [title]
    for m in re.finditer(
        r"(?is)\*\*(?:Goal|Acceptance|Target design)\*\*.*?(?=\n\*\*|\n#{2,6}\s|\Z)",
        body,
    ):
        focus_parts.append(m.group(0))
    focus = "\n".join(focus_parts)
    if item not in focus:
        return False
    # Explicit waiver of this item is not a preserve task.
    if re.search(
        rf"(?is)\bwaiv\w*.{{0,120}}{re.escape(item)}|{re.escape(item)}.{{0,120}}\bwaiv\w*",
        focus,
    ):
        return False
    # O-ACPRESERVEUNTOUCHED: "Preserve untouched this story: TOKEN" is a
    # non-goal constraint (do-not-regress), not the subject of the task.
    if re.search(
        rf"(?is)preserve\s+untouched.{{0,160}}{re.escape(item)}",
        focus,
    ):
        return False
    return True


def preserve_items(myaml: str) -> list[str]:
    m = re.search(r"^preserve:(.*?)(^\S|\Z)", myaml, re.M | re.S)
    if not m:
        return []
    return re.findall(r"^\s*-\s*([A-Za-z0-9_./:-]+)", m.group(1), re.M)


def tree_has(token: str) -> bool:
    """True when token appears under application sources (not k8s docs).

    O-AC-K8S (V10 T-003): k8s/ comments and sample manifests must not satisfy
    preserve for ENV-style tokens when the working tree still lacks them in
    src/main (e.g. application.properties). Deploy stories add k8s_has() as
    an *extra* requirement below — never as a substitute for src presence.
    """
    for rel in ("src/main", "pom.xml"):
        p = ROOT / rel
        if p.is_file():
            try:
                if token in p.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                pass
        elif p.is_dir():
            for f in p.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    if token in f.read_text(encoding="utf-8", errors="replace"):
                        return True
                except OSError:
                    continue
    return False


def k8s_has(token: str) -> bool:
    k8s = ROOT / "k8s"
    if not k8s.is_dir():
        return False
    for f in k8s.rglob("*"):
        if not f.is_file():
            continue
        try:
            if token in f.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def _target_java_paths(body: str) -> list[str]:
    """Destination .java paths cited on Target/→ lines (not staging/legacy)."""
    return [p for p in _target_paths(body) if p.endswith(".java")]


def is_structure_task(title: str, body: str) -> bool:
    """O-ACSTRUCT: Shape=structure or package-structure /.gitkeep deliverable."""
    if re.search(r"(?im)^\*\*Shape\*\*\s*:?\s*structure\b", body):
        return True
    if re.search(r"(?im)^\*\*Shape\s*:\s*structure\*\*", body):
        return True
    if re.search(r"(?i)\.gitkeep|package structure|directory structure", body):
        return True
    if re.search(r"(?i)\b(prepare|create)\b.+\b(package|directory)\s+structure\b", title):
        return True
    return False


def _target_dir_paths(body: str) -> list[str]:
    """Package dirs on Target/→ lines (trailing / or bare java package path).

    O-ACSTRUCT: `→ src/main/java/com/demo/dto/` is a deliverable; finding-absent
    must not skip while the directory (and usually `.gitkeep`) is missing.
    """
    dirs: list[str] = []
    for line in body.splitlines():
        if not re.search(r"(?:Target|→|->)", line, re.I):
            continue
        for m in re.finditer(
            r"src/(?:main|test)/java/[A-Za-z0-9_./]+",
            line,
        ):
            p = m.group(0).rstrip("/")
            if p.endswith(".java") or p.endswith(".gitkeep"):
                continue
            # Prefer directory form; drop if a .java file was partially matched
            if "/java/" in p and not Path(p).suffix:
                dirs.append(p)
    return [p for p in dirs if "migration/staging" not in p and "/legacy/" not in p]


def structure_gitkeep_paths(body: str) -> list[str]:
    """Declared or synthesized .gitkeep paths for structure Targets (O-ACSTRUCT)."""
    paths = sorted(
        set(
            re.findall(
                r"src/(?:main|test)/[A-Za-z0-9_./-]+/\.gitkeep",
                body,
            )
        )
    )
    if paths:
        return [p for p in paths if "migration/staging" not in p]
    out: list[str] = []
    for d in _target_dir_paths(body):
        out.append(f"{d}/.gitkeep")
    return out


def missing_structure_deliverable(title: str, body: str) -> bool:
    """True when Shape=structure Target dir/.gitkeep is still absent (O-ACSTRUCT)."""
    if not is_structure_task(title, body):
        return False
    keeps = structure_gitkeep_paths(body)
    if keeps:
        for path in keeps:
            if not (ROOT / path).is_file():
                return True
        return False
    # Structure task with only a Target dir (no .gitkeep cite) — dir must exist.
    dirs = _target_dir_paths(body)
    if not dirs:
        return True  # structure claim with no Target path → refuse skip
    for d in dirs:
        if not (ROOT / d).is_dir():
            return True
    return False


def _target_paths(body: str) -> list[str]:
    """Destination paths on Target/→ lines: java, props/yaml, k8s (O-AC-NONJAVA).

    O-ACSTRUCT: also .gitkeep and package directories under src/*/java/.
    """
    paths: list[str] = []
    for line in body.splitlines():
        if not re.search(r"(?:Target|→|->)", line, re.I):
            continue
        paths.extend(
            re.findall(
                r"(?:src/(?:main|test)/(?:java/[A-Za-z0-9_./]+\.java|java/[A-Za-z0-9_./]+/\.gitkeep|resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml))|k8s/[A-Za-z0-9_./-]+)",
                line,
            )
        )
        # also bare migration.yaml when cited as Target
        paths.extend(re.findall(r"(?<![\w./])migration\.yaml\b", line))
        # package dirs (trailing slash or bare) — checked as dir-or-.gitkeep below
        for d in re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./]+/?", line):
            d = d.rstrip("/")
            if not d.endswith(".java") and not Path(d).suffix:
                paths.append(f"{d}/.gitkeep")
    return [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]


def missing_target_path(body: str) -> bool:
    """O-AC3/O-AC-NONJAVA: True when a Target destination path is still absent.

    Extends .java-only O-AC3 to application.properties, yaml, k8s/**, migration.yaml,
    and structure `.gitkeep` / package dirs (O-ACSTRUCT).
    """
    src_root = ROOT / "src"
    for path in _target_paths(body):
        p = ROOT / path
        if p.is_file():
            continue
        # Structure package deliverable: require the .gitkeep file itself
        if path.endswith("/.gitkeep"):
            return True
        leaf = Path(path).name
        if path.endswith(".java") and src_root.is_dir():
            # ADR-24: when model.json exists, require the exact target_path —
            # basename rglob falsely AC-closes co-harvested siblings (Pet/Owner).
            model_path = ROOT / "migration" / "model.json"
            if model_path.is_file():
                if p.is_file():
                    continue
                return True
            if list(src_root.rglob(leaf)):
                continue
        return True
    return False


def missing_target_java(body: str) -> bool:
    """Back-compat alias for instruments — same as missing_target_path for .java."""
    return missing_target_path(body)


def nonjava_target_blocks_preserve(body: str) -> bool:
    """O-AC-NONJAVA: Target design naming non-.java deliverables must not
    preserve-skip — token presence ≠ config/test deliverable complete.
    """
    for path in _target_paths(body):
        if not path.endswith(".java"):
            return True
    return False


def java_basenames_absent(body: str) -> Optional[str]:
    """Return basename if an explicit java path is named and absent in tree."""
    # Prefer TARGET-side paths (after → / -> / Target).
    targetish = _target_java_paths(body)
    paths = targetish or re.findall(
        r"src/(?:main|test)/java/[A-Za-z0-9_./]+\.java", body
    )
    # Ignore staging/legacy sources — absence there is meaningless.
    paths = [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]
    if not paths:
        return None
    for path in paths:
        leaf = Path(path).name
        if list((ROOT / "src").rglob(leaf) if (ROOT / "src").is_dir() else []):
            return None  # still present somewhere under src/
    return Path(paths[0]).stem


def is_create_task(title: str) -> bool:
    """O-ACCREATE: Create/Add/… tasks must never already-complete via absent.

    Wave2 T-009: 'Create EntityUtils migration integration tests' body mentions
    'EntityUtils removal' (context for what to test). Bare \\bremoval\\b made
    is_removal_task true → absent Test.java → false ALREADY COMPLETE skip.
    """
    return bool(
        re.search(
            r"^\s*(Create|Add|Implement|Write|Author|Introduce|Build)\b",
            title,
            re.I,
        )
    )


def is_convert_task(title: str) -> bool:
    """O-ACRESTABS: Convert/Port/Harvest/Migrate must not absent-skip.

    Wave2 T-013: 'Convert remaining REST controllers' body mentions
    'Remove RootRestController' / 'removed' → is_removal_task true →
    absent PetRestController → false ALREADY COMPLETE while controllers
    still need harvest/JAX-RS.

    O-ALREADYCONS: Consolidate/Implement Panache (or similar) titles are
    convert-shaped — Target absence means not done, never removal-skip.
    """
    return bool(
        re.search(
            r"^\s*(Convert|Port|Harvest|Migrate|Rewrite|Transform|"
            r"Consolidate|Implement)\b",
            title,
            re.I,
        )
    )


def _shape_of(body: str) -> str:
    m = re.search(
        r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify|remove|structure|verify)\b"
        r"|^\*\*Shape\s*:\s*(create|modify|remove|structure|verify)\*\*",
        body or "",
    )
    if not m:
        return ""
    return next(g for g in m.groups() if g).lower()


def is_removal_task(title: str, body: str) -> bool:
    # O-ACCREATE / O-ACRESTABS / O-ALREADYCONS: create/convert-shaped titles
    # are never removal skips.
    if is_create_task(title) or is_convert_task(title):
        return False
    # O-ALREADYCONS: Shape=create|modify with missing Target .java is never
    # an absence-success (Wave4 S03 T-004: "delete bodies" near Target paths
    # false-fired body-led removal after reset).
    shape = _shape_of(body)
    if shape in {"create", "modify"} and missing_target_path(body):
        return False
    # O-T6DREMOVAL / R-104: titles like "Handle … removal" / "(removed/refactored)"
    if re.search(
        r"^\s*(Remove|Delete|Drop|Eliminate)\b", title, re.I
    ) or re.search(
        r"\b(removal|removed|already absent|must not exist)\b",
        f"{title}\n{body}",
        re.I,
    ):
        return True
    # Body-led removal of a named class/file — require remove/delete near a
    # .java path. Do NOT match "delete bodies" / "delete body" (Override Impl
    # harvest prose) — that false-skipped Consolidate→Panache (O-ALREADYCONS).
    for m in re.finditer(
        r"\b(remove|delete|drop|eliminate)\b(?!\s+bod(?:y|ies)\b)"
        r"(.{0,80}?src/(?:main|test)/java/[A-Za-z0-9_./]+\.java)",
        body,
        re.I | re.S,
    ):
        return True
    return False


def is_verify_task(title: str) -> bool:
    """O-ACVERIFY: Verify/Ensure/Confirm/Validate tasks must not preserve-skip.

    S05 T-003: 'Verify existing catalog-backed acceptance' skipped because
    an endpointEnv token appeared in Acceptance/preserve prose while the real
    work was proving acceptance.path + collection body (G-CAT / O-ACCEPTGEN).
    Env token presence ≠ verification complete.

    O-ACVERIFY2: also titles whose work is characterization / package verify
    (v2 S04 T-006: 'Repository characterization tests and package verify'
    preserve-skipped on petclinic.security.enable from Target-design prose).
    """
    return bool(
        re.search(
            r"(?i)^\s*(Verify|Ensure|Confirm|Validate)\b"
            r"|\bcharacterization\b|\bpackage verify\b|\bverify\b",
            title,
        )
    )


def _owns_and_target_java(body: str) -> list[str]:
    """Target → paths plus Owns: listed .java paths (O-ALREADYFINDING)."""
    paths = list(_target_java_paths(body))
    for m in re.finditer(r"(?im)^\*\*Owns\*\*:?\s*(.+)$", body):
        paths.extend(
            re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./]+\.java", m.group(1))
        )
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        if p in seen or "migration/staging" in p or "/legacy/" in p:
            continue
        seen.add(p)
        out.append(p)
    return out


def target_java_blocks_preserve(body: str) -> bool:
    """O-ALREADYPROP: Target/Owns .java means class work — preserve token ≠ done.

    S07 T-002/T-009: `petclinic.security.enable` present while
    BasicAuthenticationConfig missing or VetRestController lacked @RolesAllowed.
    Property-only preserve tasks (no Target .java) still skip via present:TOKEN.
    """
    return bool(_owns_and_target_java(body))


def _focus_blob(title: str, body: str) -> str:
    parts = [title]
    for m in re.finditer(
        r"(?is)\*\*(?:Goal|Acceptance|Target design)\*\*.*?(?=\n\*\*|\n#{2,6}\s|\Z)",
        body,
    ):
        parts.append(m.group(0))
    return "\n".join(parts)


def replacement_constructs_missing(title: str, body: str) -> Optional[str]:
    """O-ALREADYREPL (W3-140): skip only when declared replacements exist.

    Wave 3 S07: oracle-absent / preserve-token skips accepted T-005/T-009 while
    Target work was incomplete. Require quarkus-* deps named in Goal/Acceptance/
    Target design to be present in pom.xml before any already-complete skip.
    Annotation gaps are handled by annotation_work_incomplete.
    """
    focus = _focus_blob(title, body)
    arts = sorted(
        set(
            re.findall(
                r"\b(quarkus-[a-z0-9][a-z0-9-]{2,})\b",
                focus,
                re.I,
            )
        )
    )
    # Drop finding-id lookalikes (quarkus-00000) and overly generic tokens.
    arts = [a for a in arts if not re.search(r"-\d{3,}$", a)]
    if not arts:
        return None
    pom = ROOT / "pom.xml"
    if not pom.is_file():
        return "need-pom:" + ",".join(arts[:6])
    try:
        ptxt = pom.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "need-pom:" + ",".join(arts[:6])
    missing = [a for a in arts if a not in ptxt]
    if missing:
        return "need-deps:" + ",".join(missing[:6])
    return None


def annotation_work_incomplete(title: str, body: str) -> Optional[str]:
    """O-ALREADYFINDING: RolesAllowed / PreAuthorize work not done on Targets.

    Finding-absent must not skip Shape=modify annotation harvest when Owns/
    Target REST classes still lack @RolesAllowed.
    """
    blob = f"{title}\n{body}"
    if not re.search(
        r"(?i)@?RolesAllowed|@?PreAuthorize|role.?based|security annotation",
        blob,
    ):
        return None
    paths = _owns_and_target_java(body)
    if not paths:
        # Title asks for RolesAllowed but no paths — do not oracle-skip.
        return "rolesallowed-no-paths"
    missing: list[str] = []
    for want in paths:
        p = ROOT / want
        if not p.is_file():
            # basename search under src/
            leaf = Path(want).name
            hits = list((ROOT / "src").rglob(leaf)) if (ROOT / "src").is_dir() else []
            if not hits:
                missing.append(want)
                continue
            p = hits[0]
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            missing.append(want)
            continue
        if "@RolesAllowed" not in text and "RolesAllowed" not in text:
            try:
                missing.append(str(p.relative_to(ROOT)))
            except ValueError:
                missing.append(want)
    if missing:
        return "need-RolesAllowed:" + ",".join(missing[:6])
    return None


def verify_absence_already_ok(title: str, body: str) -> Optional[str]:
    """O-ACVERIFYABS / O-ESCWVERIFYABS: Shape=verify Oracle=absent deferral.

    Wave4 S03 T-000: characterization deferred — success is verified ABSENCE of
    phantom repository tests, not inventing them. Fast-path before worker so
    MiniMax is not burned on run-log-only tips.
    """
    if _shape_of(body) != "verify":
        return None
    if not re.search(
        r"(?im)^\*\*Oracle\*\*\s*:?\s*absent\b|^\*\*Oracle\s*:\s*absent\*\*",
        body,
    ):
        return None
    blob = f"{title}\n{body}"
    if not re.search(
        r"(?i)verify absence|characterization\s+deferred|do NOT invent|hollow|"
        r"must not invent|no hollow",
        blob,
    ):
        return None
    phantoms = re.findall(
        r"([A-Za-z0-9_]+)\*Test\.java|\`([^*`]+\*[^*`]*Test\.java)\`",
        blob,
    )
    test_root = ROOT / "src/test"
    if test_root.is_dir():
        for a, b in phantoms:
            raw = a or b
            key = raw.replace("*", "").replace(".java", "").replace("Test", "")
            if not key:
                continue
            for p in test_root.rglob("*Test.java"):
                if key in p.name:
                    return None  # phantom present — must-run
    return "verify-absent"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: already-complete.py <tasks.md> <T-xxx>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    deploy = os.environ.get("STORY_DEPLOY", "false").lower() == "true"
    title, body = task_body(tasks, tid)
    if not body:
        return 1

    myaml = ""
    myp = ROOT / "migration.yaml"
    if myp.is_file():
        myaml = myp.read_text(encoding="utf-8", errors="replace")

    # O-ACVERIFYABS: Shape=verify + Oracle=absent + absence/defer Goal.
    vabs = verify_absence_already_ok(title, body)
    if vabs:
        print(f"absent:{vabs}")
        return 0

    # O-AC3 / O-AC-NONJAVA / O-ACVERIFY / O-ALREADYPROP / O-ALREADYREPL /
    # O-ACSTRUCT: missing Target, non-java Target, Target/Owns .java class work,
    # verify titles, structure package/.gitkeep, or missing named quarkus-*
    # replacements block preserve skip.
    repl_gap = replacement_constructs_missing(title, body)
    if missing_structure_deliverable(title, body):
        return 1
    if (
        not missing_target_path(body)
        and not nonjava_target_blocks_preserve(body)
        and not target_java_blocks_preserve(body)
        and not is_verify_task(title)
        and annotation_work_incomplete(title, body) is None
        and repl_gap is None
    ):
        for item in preserve_items(myaml):
            if not preserve_is_task_subject(title, body, item):
                continue
            # Application tree must carry the token. ENV-style + deploy also
            # requires k8s/ (real env wiring), never k8s-alone (O-AC-K8S).
            if not tree_has(item):
                continue
            if re.fullmatch(r"[A-Z][A-Z0-9_]+", item) and deploy and not k8s_has(item):
                continue
            print(f"present:{item}")
            return 0

    if is_removal_task(title, body):
        leaf = java_basenames_absent(body)
        if leaf:
            # Refuse verb-looking "leaves" even if somehow extracted.
            if leaf.lower() in {
                "convert",
                "port",
                "ensure",
                "preserve",
                "create",
                "update",
                "implement",
                "migrate",
                "replace",
                "verify",
            }:
                return 1
            print(f"absent:{leaf}")
            return 0

    # K6 / O-DESTBASE: findings oracle — all Findings ids absent (after-scan,
    # tree heuristic, or scaffold-presatisfied) → genuine already-complete.
    oracle = ROOT / ".hermes/harness/findings-oracle.py"
    if not oracle.is_file():
        oracle = Path(__file__).resolve().parent / "findings-oracle.py"
    if oracle.is_file():
        import subprocess

        env = os.environ.copy()
        env["ORACLE_ROOT"] = str(ROOT)
        env["ALREADY_COMPLETE_ROOT"] = str(ROOT)
        proc = subprocess.run(
            [sys.executable, str(oracle), str(tasks), tid],
            capture_output=True,
            text=True,
            env=env,
        )
        out = (proc.stdout or "").strip()
        # O-ACCREATE / O-ACHARVEST: findings-oracle "absent" means finding
        # cleared in the *current* tree — never means skip Create/Harvest when
        # the Target destination is still missing. Live S02 T-002/T-003: Harvest
        # BaseEntity skipped via oracle-absent while Target .java absent.
        # O-DESTBASE: Convert titles MAY oracle-skip when findings are
        # scaffold-presatisfied and no Target path is missing — the blanket
        # is_convert_task block broke parent-pom already-complete (instrument).
        # O-ACRESTABS still holds via missing_target_path for Convert REST.
        # O-ALREADYFINDING: finding absent ≠ @RolesAllowed / Target work done.
        ann_gap = annotation_work_incomplete(title, body)
        if repl_gap is None:
            repl_gap = replacement_constructs_missing(title, body)
        if (
            proc.returncode == 0
            and out.startswith("absent:")
            and not is_create_task(title)
            and not is_verify_task(title)  # O-ACVERIFY2: verify ≠ finding-absent
            and not missing_target_path(body)
            # O-ACSTRUCT: finding-absent ≠ package structure until .gitkeep exists
            and not missing_structure_deliverable(title, body)
            and ann_gap is None
            and repl_gap is None
        ):
            print(f"oracle-{out}")
            return 0
        # returncode 3 = no-findings → fall through; 1 = present → do not skip
    else:
        # Fallback when oracle script not deployed: static scaffold-presatisfied.
        findings = re.findall(r"(?im)^\s*-?\s*\*\*Findings\*\*:\s*(.+)$", body)
        ids: list[str] = []
        for block in findings:
            ids.extend(re.findall(r"[a-z][a-z0-9_-]*-\d+", block, re.I))
        if ids:
            presat: set[str] = set()
            for base in (
                ROOT / "migration/scaffold-presatisfied.generated.txt",
                ROOT / ".hermes/harness/scaffold-presatisfied.txt",
                Path(__file__).resolve().parent / "scaffold-presatisfied.txt",
            ):
                try:
                    for ln in base.read_text(encoding="utf-8").splitlines():
                        ln = ln.strip()
                        if ln and not ln.startswith("#"):
                            presat.add(ln)
                except OSError:
                    continue
            if ids and all(i in presat for i in ids):
                pom = ROOT / "pom.xml"
                if pom.is_file():
                    ptxt = pom.read_text(encoding="utf-8", errors="replace")
                    if "quarkus-maven-plugin" in ptxt and "spring-boot" not in ptxt.lower():
                        print("scaffold-presatisfied:" + ",".join(ids[:6]))
                        return 0

    # O-JDBCSKIP / O-JDBCREGRESS: JDBC repository CDI when Quarkus JPA
    # @ApplicationScoped impls already cover the repository interfaces —
    # skip rather than re-adding spring-jdbc (Wave2 T-009).
    # O-JDBCSKIPSTAGING: do NOT skip when staging/legacy still has
    # Jdbc*RepositoryImpl to harvest (petclinic S04 T-004) — "JPA present +
    # live jdbc empty" is incomplete work, not already-complete.
    blob = f"{title}\n{body}"
    if re.search(r"(?i)jdbc\s+repository|/repository/jdbc/", blob):
        jpa = list((ROOT / "src/main/java").rglob("Jpa*RepositoryImpl.java"))
        jdbc = list((ROOT / "src/main/java").rglob("repository/jdbc/Jdbc*RepositoryImpl.java"))
        staging_root = ROOT / "migration/staging"
        staging_jdbc: list[Path] = []
        if staging_root.is_dir():
            staging_jdbc = list(staging_root.rglob("repository/jdbc/Jdbc*RepositoryImpl.java"))
        jpa_cdi = 0
        for p in jpa:
            try:
                if "@ApplicationScoped" in p.read_text(encoding="utf-8", errors="replace"):
                    jpa_cdi += 1
            except OSError:
                continue
        if jpa_cdi >= 3 and not jdbc and not staging_jdbc:
            # kind must be present|absent|oracle-absent (supervisor try_already_complete)
            print(f"present:JpaRepositoryImpl-cdi({jpa_cdi})")
            return 0

    # O-SDJPA-SKIP / O-T4SPRINGDATA: Spring Data Override-only (or redesign
    # skip) when Quarkus Jpa* @ApplicationScoped already cover domain repos
    # and pom has no spring-data — skip rather than Qwen READ_THRASH→MiniMax
    # (Wave2 T-011 / v2 S04 T-005). Do NOT skip Port=reimplement Panache
    # consolidate seats or when staging Override Impls still need harvest.
    if re.search(
        r"(?i)spring\s*data|springdatajpa|SpringData\w+Repository", blob
    ):
        pom_path = ROOT / "pom.xml"
        pom_txt = ""
        if pom_path.is_file():
            try:
                pom_txt = pom_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pom_txt = ""
        has_sd_dep = bool(
            re.search(r"(?i)spring-data|quarkus-spring-data", pom_txt)
        )
        # Panache consolidate / Port=reimplement must still run
        if re.search(
            r"(?i)panache|consolidat|\*\*Port\*\*\s*:?\s*reimplement|"
            r"Port\s*:\s*reimplement",
            blob,
        ):
            pass
        elif not has_sd_dep:
            jpa = list((ROOT / "src/main/java").rglob("Jpa*RepositoryImpl.java"))
            jpa_cdi = 0
            for p in jpa:
                try:
                    if "@ApplicationScoped" in p.read_text(
                        encoding="utf-8", errors="replace"
                    ):
                        jpa_cdi += 1
                except OSError:
                    continue
            staging_root = ROOT / "migration/staging"
            staging_ov: list[Path] = []
            if staging_root.is_dir():
                staging_ov = [
                    p
                    for p in staging_root.rglob("*RepositoryImpl.java")
                    if "springdatajpa" in str(p).replace("\\", "/")
                    or "Override" in p.name
                ]
            live_ov_names = {
                p.name
                for p in (ROOT / "src/main/java").rglob("*RepositoryImpl.java")
            }
            pending_ov = [p for p in staging_ov if p.name not in live_ov_names]
            override_focus = bool(
                re.search(
                    r"(?i)\boverride\b|delete\s+(?:helper|bod)|"
                    r"O-SDJPA-SKIP|redesign|defer|already.?complete",
                    blob,
                )
            )
            # Override-only / redesign-skip with JPA cover and no pending Impl
            if jpa_cdi >= 3 and override_focus and not pending_ov:
                print(f"present:JpaRepositoryImpl-cdi-sdjpa-skip({jpa_cdi})")
                return 0

    # O-ACPRECLAIM (W4R7 S02 T-003): HARVEST/rewrite Target already on disk with
    # Jakarta imports, but Findings are prose (javax.persistence.*) so
    # findings-oracle returns no-findings (rc=3) and preserve-skip is blocked by
    # target_java_blocks_preserve → false must-run → Qwen/MiniMax seat burn.
    # When every Owns/Target .java exists and no longer carries javax.persistence
    # (Acceptance/Goal cite Jakarta), treat as already-complete.
    if (
        not missing_target_path(body)
        and not missing_structure_deliverable(title, body)
        and _shape_of(body) in {"", "modify", "create", "structure"}
        and not is_removal_task(title, body)
        and not is_verify_task(title)
    ):
        java_paths = _owns_and_target_java(body)
        focus = _focus_blob(title, body)
        wants_jakarta = bool(re.search(r"(?i)jakarta", focus))
        harvestish = bool(
            re.search(r"(?i)\bharvest\b|\brewrite\b|\bmoderniz", f"{title}\n{body}")
        )
        if java_paths and (harvestish or wants_jakarta):
            ok = True
            for rel in java_paths:
                fp = ROOT / rel
                if not fp.is_file():
                    ok = False
                    break
                try:
                    txt = fp.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    ok = False
                    break
                if re.search(r"\bjavax\.persistence\b", txt):
                    ok = False
                    break
                if wants_jakarta and not re.search(r"\bjakarta\.persistence\b", txt):
                    # Entity harvest Acceptance usually requires jakarta imports.
                    if re.search(r"(?i)@Entity|persistence", focus):
                        ok = False
                        break
                # O-ACPRECLAIMVAL: jakarta.validation.* needs hibernate-validator
                # on the Quarkus BOM path — presence alone is not compile-green
                # (W4R7 S02 T-004 NamedEntity NotEmpty → sfix after false AC).
                if re.search(r"\bjakarta\.validation\b", txt):
                    pom = ROOT / "pom.xml"
                    ptxt = pom.read_text(encoding="utf-8", errors="replace") if pom.is_file() else ""
                    if not re.search(
                        r"(?i)hibernate-validator|quarkus-hibernate-validator|"
                        r"jakarta\.validation",
                        ptxt,
                    ):
                        ok = False
                        break
            if ok:
                print(f"present:target-jakarta:{java_paths[0]}")
                return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
