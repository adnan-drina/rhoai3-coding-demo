#!/usr/bin/env python3
"""O-ESCW3 — may the supervisor allow-empty "Already satisfied" for this task?

Exit 0 = eligible (noop commit OK when tree has no app dirt + task sensor GREEN).
Exit 1 = not eligible — worker/escalation must still produce deliverables.

V9 S03 T-008: O-ESCW allow-empty'd characterization after worker wrote nothing;
task sensor stays GREEN without tests. Characterization / missing Target .java
must never ESCW.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

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
        # O-T6dCHARSEC: same as mechan-match — strip ## section titles between
        # T-NNN blocks so "Characterization Tests" headings do not mark the
        # prior harvest task as wants_tests.
        body = re.split(r"^##\s+", body, maxsplit=1, flags=re.M)[0]
        body = re.split(
            r"^##\s+(Story Scope Waivers|Waivers|Notes|Appendix)\b",
            body,
            maxsplit=1,
            flags=re.M | re.I,
        )[0]
        return title, body
    return "", ""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: escw-eligible.py <tasks.md> <T-xxx>", file=sys.stderr)
        return 2
    tasks = Path(sys.argv[1])
    tid = sys.argv[2]
    title, body = task_body(tasks, tid)
    if not title and not body:
        print("no-task")
        return 1

    blob = f"{title}\n{body}"
    wants_tests = bool(
        re.search(
            r"(?i)\bcharacterization\b|src/test/|DomainModelTest|\bunit tests?\b",
            blob,
        )
    )
    if wants_tests:
        tests = (
            list((ROOT / "src/test").rglob("*.java"))
            if (ROOT / "src/test").is_dir()
            else []
        )
        named = re.findall(r"src/test/[A-Za-z0-9_./-]+\.java", blob)
        if named:
            if all((ROOT / p).is_file() for p in named):
                print("tests-present")
                return 0
            print("need-src-test")
            return 1
        # Service-layer characterization must not ESCW on model-only tests (S02).
        if re.search(r"(?i)service layer|/service/|com\.demo\.service", blob):
            svc = [t for t in tests if "/service/" in str(t).replace("\\", "/")]
            if not svc:
                print("need-service-tests")
                return 1
            print("tests-present")
            return 0
        if not tests:
            print("need-src-test")
            return 1
        print("tests-present")
        return 0

    # Target destination .java files must exist for ESCW (conversion tasks).
    targets = re.findall(
        r"(?:Target|→|->)[^\n]*?(src/main/java/[A-Za-z0-9_./-]+\.java)", blob
    )

    # O-ESCW3SCOPE (v2 S05 T-006): finding-scope / Absorbs tasks list later-story
    # Target arrows (REST/security/util) that must stay ABSENT. Requiring those
    # as missing-target forced MiniMax escalation. For these tasks, require
    # **Absorbs** paths (already-delivered prior work) instead of all Target dests.
    finding_scope = bool(
        re.search(
            r"(?i)finding-scope|findings-scope|"
            r"no new\b.{0,80}\bfrom this task|"
            r"reserved for later",
            blob,
        )
    )
    if finding_scope:
        # Absorbs often mixes prior-story deliveries with later-story claim paths
        # (REST/security/util) that Acceptance says must stay absent — only prior
        # deliveries are required to exist.
        later_pkg = re.compile(r"/(?:rest|security|util|openapi)/")
        absorbs: list[str] = []
        for m in re.finditer(r"(?im)^\*\*Absorbs\*\*:?\s*(.+)$", body):
            absorbs.extend(
                re.findall(r"src/main/java/[A-Za-z0-9_./-]+\.java", m.group(1))
            )
        for want in absorbs:
            if later_pkg.search(want):
                if (ROOT / want).is_file():
                    print(f"unexpected-later:{want}")
                    return 1
                continue
            if not (ROOT / want).is_file():
                print(f"missing-absorb:{want}")
                return 1
        # Do not require later-story Target destinations.
    else:
        for want in targets:
            if not (ROOT / want).is_file():
                print(f"missing-target:{want}")
                return 1

    # O-ESCWCONVERT (S04 T-005): existence of a harvested JAX-RS stub is not
    # "Convert … session management / constructor injection" complete. Require
    # the contract the task text asks for before allow-empty.
    convertish = bool(
        re.search(
            r"(?i)\bconvert\b|session management|@SessionScoped|"
            r"constructor injection|Quarkus session",
            blob,
        )
    )
    if convertish and targets and not finding_scope:
        for want in targets:
            text = (ROOT / want).read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?i)session management|@SessionScoped|Quarkus session", blob):
                if not re.search(r"@SessionScoped|SessionScoped", text):
                    print(f"need-session-scope:{want}")
                    return 1
            if re.search(r"(?i)constructor injection|@Autowired|@Inject", blob):
                if "@Inject" not in text and "jakarta.inject.Inject" not in text:
                    print(f"need-inject:{want}")
                    return 1

    # Package-structure: need .gitkeep or any file in the named directory.
    if re.search(r"(?i)package structure|empty package", blob):
        dirs = re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./-]+/", blob)
        for d in dirs:
            p = ROOT / d.rstrip("/")
            if not p.is_dir():
                print(f"missing-pkgdir:{d}")
                return 1
            if not any(p.iterdir()):
                print(f"empty-pkgdir:{d}")
                return 1

    # O-T6EEMPTYESC: POM/dep tips — named quarkus artifactIds already in pom
    # means worker-verified satisfied even when findings-oracle still "present"
    # (MTA may still emit springboot-security-* until after-scan; dep tip is done).
    pom = ROOT / "pom.xml"
    if pom.is_file() and re.search(
        r"(?i)pom\.xml|quarkus-security|quarkus-smallrye|elytron-security|"
        r"Add Quarkus .+ dependenc",
        blob,
    ):
        # Only Goal/Acceptance — Findings ids like springboot-…-quarkus-00000
        # must not be mistaken for artifactIds (O-T6EEMPTYESC).
        focus_parts = [title]
        for m in re.finditer(
            r"(?is)\*\*(?:Goal|Acceptance)\*\*.*?(?=\n\*\*|\n#{2,6}\s|\Z)",
            body,
        ):
            focus_parts.append(m.group(0))
        focus = "\n".join(focus_parts)
        arts = re.findall(
            r"\b(quarkus-[a-z][a-z0-9-]{2,})\b", focus, re.I
        )
        arts = [
            a
            for a in arts
            if a.lower()
            not in {
                "quarkus-maven-plugin",
                "quarkus-bom",
            }
            and not re.search(r"-\d{3,}$", a)  # not rule-id suffixes
        ]
        # de-dupe
        seen: set[str] = set()
        uniq: list[str] = []
        for a in arts:
            k = a.lower()
            if k in seen:
                continue
            seen.add(k)
            uniq.append(a)
        arts = uniq
        if arts:
            ptxt = pom.read_text(encoding="utf-8", errors="replace")
            if all(
                re.search(
                    rf"<artifactId>\s*{re.escape(a)}\s*<", ptxt, re.I
                )
                for a in arts[:8]
            ):
                print("pom-deps-present:" + ",".join(arts[:6]))
                return 0

    # K6: Findings still present in oracle → never allow-empty ESCW.
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
        if proc.returncode == 1 and out.startswith("present:"):
            print(f"findings-present:{out.split(':', 1)[1][:80]}")
            return 1

    print("eligible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
