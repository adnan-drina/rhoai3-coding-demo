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
        re.finditer(r"^#{2,6}\s+(T[-A-Za-z0-9]*\d+)\s*:\s*(.+)$", text, re.M)
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


def _target_paths(body: str) -> list[str]:
    """Destination paths on Target/→ lines: java, props/yaml, k8s (O-AC-NONJAVA)."""
    paths: list[str] = []
    for line in body.splitlines():
        if not re.search(r"(?:Target|→|->)", line, re.I):
            continue
        paths.extend(
            re.findall(
                r"(?:src/(?:main|test)/(?:java/[A-Za-z0-9_./]+\.java|resources/[A-Za-z0-9_./-]+\.(?:properties|ya?ml|xml))|k8s/[A-Za-z0-9_./-]+)",
                line,
            )
        )
        # also bare migration.yaml when cited as Target
        paths.extend(re.findall(r"(?<![\w./])migration\.yaml\b", line))
    return [p for p in paths if "migration/staging" not in p and "/legacy/" not in p]


def missing_target_path(body: str) -> bool:
    """O-AC3/O-AC-NONJAVA: True when a Target destination path is still absent.

    Extends .java-only O-AC3 to application.properties, yaml, k8s/**, migration.yaml.
    """
    src_root = ROOT / "src"
    for path in _target_paths(body):
        if (ROOT / path).is_file():
            continue
        leaf = Path(path).name
        if path.endswith(".java") and src_root.is_dir() and list(src_root.rglob(leaf)):
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
    """
    return bool(
        re.search(
            r"^\s*(Convert|Port|Harvest|Migrate|Rewrite|Transform)\b",
            title,
            re.I,
        )
    )


def is_removal_task(title: str, body: str) -> bool:
    # O-ACCREATE / O-ACRESTABS: create/convert-shaped titles are never removal skips.
    if is_create_task(title) or is_convert_task(title):
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
    # Body-led removal of a named class/file — require remove/delete near a .java path.
    for m in re.finditer(
        r"\b(remove|delete|drop|eliminate)\b(.{0,80}?src/(?:main|test)/java/[A-Za-z0-9_./]+\.java)",
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
    """
    return bool(re.search(r"^\s*(Verify|Ensure|Confirm|Validate)\b", title, re.I))


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

    # O-AC3 / O-AC-NONJAVA / O-ACVERIFY: missing Target, non-java Target, or
    # verify-class titles block preserve fast-path.
    if (
        not missing_target_path(body)
        and not nonjava_target_blocks_preserve(body)
        and not is_verify_task(title)
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
        # O-ACCREATE: findings-oracle "absent" means finding cleared — never
        # means "create target missing, skip the create task".
        if (
            proc.returncode == 0
            and out.startswith("absent:")
            and not is_create_task(title)
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
    blob = f"{title}\n{body}"
    if re.search(r"(?i)jdbc\s+repository|/repository/jdbc/", blob):
        jpa = list((ROOT / "src/main/java").rglob("Jpa*RepositoryImpl.java"))
        jdbc = list((ROOT / "src/main/java").rglob("repository/jdbc/Jdbc*RepositoryImpl.java"))
        jpa_cdi = 0
        for p in jpa:
            try:
                if "@ApplicationScoped" in p.read_text(encoding="utf-8", errors="replace"):
                    jpa_cdi += 1
            except OSError:
                continue
        if jpa_cdi >= 3 and not jdbc:
            # kind must be present|absent|oracle-absent (supervisor try_already_complete)
            print(f"present:JpaRepositoryImpl-cdi({jpa_cdi})")
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
