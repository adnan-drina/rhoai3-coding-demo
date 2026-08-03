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
import subprocess
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

    # O-ESCWVERIFYABS: Shape=verify + Oracle=absent + absence/defer Goal is
    # success when named phantom *Test paths are gone — never require inventing
    # characterization tests (Wave4 S03 T-000: "Characterization deferred" title
    # matched wants_tests → need-src-test → MiniMax for a verify-absent tip).
    shape_verify = bool(
        re.search(r"(?im)^\*\*Shape\*\*\s*:?\s*verify\b|^\*\*Shape\s*:\s*verify\*\*", body)
    )
    oracle_absent = bool(
        re.search(r"(?im)^\*\*Oracle\*\*\s*:?\s*absent\b|^\*\*Oracle\s*:\s*absent\*\*", body)
    )
    verify_abs_lang = bool(
        re.search(
            r"(?i)verify absence|characterization\s+deferred|deferred\s+[—-]|do NOT invent|"
            r"hollow\s+(G-PLACE\s+)?[Rr]epository|must not invent|no hollow",
            blob,
        )
    )
    if shape_verify and oracle_absent and verify_abs_lang:
        # Patterns like PetTypeRepository*Test.java / `*Foo*Test.java`
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
                        print(f"phantom-present:{p.name}")
                        return 1
        print("verify-absent-ok")
        return 0

    # Real characterization / unit-test delivery — not verify-absent deferrals.
    wants_tests = bool(
        re.search(
            r"(?i)\bcharacterization\b|src/test/|DomainModelTest|\bunit tests?\b",
            blob,
        )
    ) and not (
        shape_verify
        and oracle_absent
        and re.search(r"(?i)deferred|verify absence|do NOT invent|hollow", blob)
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
            r"constructor injection|Quarkus session|@Autowired|cdi\b|"
            r"jdbc\s+repository|@ApplicationScoped",
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
            if re.search(r"(?i)constructor injection|@Autowired|@Inject|cdi\b|jdbc", blob):
                if "@Inject" not in text and "jakarta.inject.Inject" not in text:
                    print(f"need-inject:{want}")
                    return 1
                # O-CDIPARTIAL: ApplicationScoped + leftover @Autowired ≠ done
                if re.search(r"@Autowired\b", text):
                    print(f"partial-cdi-autowired:{want}")
                    return 1

    # O-CDIPARTIAL / O-JDBCHARVESTAPI: tree-wide refuse Already-satisfied when
    # any CDI bean still carries @Autowired or spring.jdbc APIs under quarkus.
    # Skip finding-scope / structure claim tasks (O-ESCW3SCOPE) — those are not
    # CDI-convert seats.
    checker = Path(__file__).resolve().parent / "cdi-partial-check.py"
    if (
        checker.is_file()
        and not finding_scope
        and re.search(
            r"(?i)\bconvert\b|cdi\b|@Autowired|jdbc\s+repository|"
            r"NamedParameterJdbc|SimpleJdbcInsert|@Inject|ApplicationScoped",
            blob,
        )
    ):
        try:
            out = subprocess.check_output(
                [sys.executable, str(checker)],
                text=True,
                stderr=subprocess.STDOUT,
                cwd=str(ROOT),
            )
            _ = out
        except subprocess.CalledProcessError as exc:
            first = (exc.output or "").strip().splitlines()
            print(first[0] if first else "cdi-partial")
            return 1

    # O-ESCWSTRUCTTGT: Target .gitkeep (or Shape=structure) must exist on disk
    # before allow-empty — never claim Already satisfied with an empty tree tip.
    gitkeep_tgts = re.findall(
        r"(?:Target|→|->|Owns)[^\n]*?(src/(?:main|test)/[A-Za-z0-9_./-]*/\.gitkeep)",
        blob,
    )
    if gitkeep_tgts or re.search(
        r"(?i)\*\*Shape\*\*\s*:\s*structure|\bShape\s*:\s*structure\b", blob
    ):
        for gk in gitkeep_tgts:
            if not (ROOT / gk).is_file():
                print(f"missing-gitkeep:{gk}")
                return 1
        if not gitkeep_tgts and re.search(
            r"(?i)package structure|package-info|\.gitkeep", blob
        ):
            # Structure task without an explicit .gitkeep path still needs a
            # Target package dir under targetPackage with at least one file.
            tgt_dirs = re.findall(
                r"(?:Target|→|->)[^\n]*?(src/(?:main|test)/java/[A-Za-z0-9_./-]+/)",
                blob,
            )
            for d in tgt_dirs:
                p = ROOT / d.rstrip("/")
                if not p.is_dir() or not any(p.iterdir()):
                    print(f"missing-struct:{d}")
                    return 1

    # Package-structure: need .gitkeep or any file in the named directory.
    # O-ESCW3PKGDIR: only require Target/→ package dirs under targetPackage —
    # never refuse allow-empty citing legacyPackage path (Absorbs/Source).
    if re.search(r"(?i)package structure|empty package", blob):
        dirs = re.findall(r"src/(?:main|test)/java/[A-Za-z0-9_./-]+/", blob)
        tgt_dirs = re.findall(
            r"(?:Target|→|->)[^\n]*?(src/(?:main|test)/java/[A-Za-z0-9_./-]+/)",
            blob,
        )
        check_dirs = tgt_dirs if tgt_dirs else dirs
        legacy_seg = ""
        tgt_seg = ""
        myaml = ROOT / "migration.yaml"
        if myaml.is_file():
            ytxt = myaml.read_text(encoding="utf-8", errors="replace")
            m_leg = re.search(
                r"(?m)^\s*legacyPackage:\s*['\"]?([A-Za-z0-9_.]+)['\"]?", ytxt
            )
            m_tgt = re.search(
                r"(?m)^\s*targetPackage:\s*['\"]?([A-Za-z0-9_.]+)['\"]?", ytxt
            )
            if m_leg:
                legacy_seg = m_leg.group(1).replace(".", "/")
            if m_tgt:
                tgt_seg = m_tgt.group(1).replace(".", "/")
        filtered: list[str] = []
        for d in check_dirs:
            dn = d.replace("\\", "/")
            if legacy_seg and f"/{legacy_seg}/" in f"/{dn}":
                continue
            if tgt_seg and f"/{tgt_seg}/" not in f"/{dn}" and tgt_dirs:
                # Target-line dirs must sit under targetPackage when configured
                continue
            filtered.append(d)
        if not filtered and tgt_dirs:
            filtered = list(tgt_dirs)
        for d in filtered:
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
