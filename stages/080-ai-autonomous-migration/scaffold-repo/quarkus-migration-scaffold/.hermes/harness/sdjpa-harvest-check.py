#!/usr/bin/env python3
"""O-SDJPAHARVEST / O-SDJPAHARVESTONLY — Spring Data JPA → Panache fidelity.

Migration-general (any Spring Boot → Quarkus specimen):

When a destination file pairs with a staged Spring Data repository
(``org.springframework.data.repository.*`` / ``@Query`` from spring-data),
the Panache convert must:

  0. O-SDJPAHARVESTONLY — not stop at harvest-from-staging: dest still
     carrying ``org.springframework.data`` with no PanacheRepository is
     incomplete (Shape=create|modify Panache consolidate).
  1. Preserve domain-repository ``extends`` contracts (do not drop
     domain repository ifaces when staging declared them).
  2. Not park orphan ``@NamedQuery`` on the repository interface (staging
     used method ``@Query`` — rewrite to Panache ``find``/``list`` / default
     methods or entity NamedQuery; bare iface NamedQuery is dishonest).
  3. Not leave hollow finder declarations (staging ``@Query`` methods must
     gain a body / Panache query, not ``ReturnType name(...);`` alone).
  4. Harvest Override ``*Impl`` classes when staging has them — empty
     Override interfaces without their Impl delete bodies ≠ consolidate.

Usage:
  sdjpa-harvest-check.py              # scan working tree
  sdjpa-harvest-check.py --sha HEAD   # scan files touched by that commit

Exit 0 = clean; exit 1 = violation(s) on stdout.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".").resolve()

SPRING_DATA = re.compile(
    r"org\.springframework\.data\.(?:jpa\.)?repository\b|"
    r"org\.springframework\.data\.repository\.query\b|"
    r"@Query\b"
)
PANACHE = re.compile(r"\bPanacheRepository(?:Base)?\b")
NAMED_QUERY = re.compile(r"@NamedQuery\b")
EXTENDS = re.compile(
    r"\b(?:public\s+)?interface\s+\w+\s+extends\s+([^{]+)", re.S
)
CLASS_IMPL = re.compile(
    r"\b(?:public\s+)?class\s+(\w+)\s+implements\s+([^{]+)", re.S
)
QUERY_METHOD = re.compile(
    r"@Query\b[\s\S]*?(?:public\s+)?([\w.<>,\[\]?]+)\s+(\w+)\s*\([^;{}]*\)\s*;",
    re.M,
)
HOLLOW_METHOD = re.compile(
    r"(?:^|\n)\s*(?:(?:default|static)\s+)?(?:[\w.<>,\[\]?]+\s+)+(\w+)\s*\([^;{}]*\)\s*;",
    re.M,
)
DEFAULT_OR_BODY = re.compile(
    r"(?:default\s+[\w.<>,\[\]?]+\s+(\w+)\s*\([^;{}]*\)\s*\{|"
    r"(?:public|protected)\s+[\w.<>,\[\]?]+\s+(\w+)\s*\([^;{}]*\)\s*\{)",
    re.M,
)
SKIP_EXTENDS = {
    "Repository",
    "CrudRepository",
    "JpaRepository",
    "PagingAndSortingRepository",
    "ListCrudRepository",
    "ListPagingAndSortingRepository",
    "PanacheRepository",
    "PanacheRepositoryBase",
}


def _strip_noise(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    return text


def _walk_java(root: Path) -> dict[str, tuple[Path, str]]:
    out: dict[str, tuple[Path, str]] = {}
    if not root.is_dir():
        return out
    for p in root.rglob("*.java"):
        try:
            out[p.name] = (p, p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return out


def _git_show(sha: str, path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{sha}:{path}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def _commit_java_names(sha: str) -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "show", "--name-only", "--format=", sha], text=True
        )
    except subprocess.CalledProcessError:
        return []
    return [
        ln.strip()
        for ln in out.splitlines()
        if ln.strip().endswith(".java") and ln.strip().startswith("src/")
    ]


def _split_types(blob: str) -> list[str]:
    """Split `A, B<C, D>, E` on commas outside angle brackets."""
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in blob:
        if ch == "<":
            depth += 1
            cur.append(ch)
        elif ch == ">":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return [p for p in parts if p]


def _domain_extends(text: str) -> list[str]:
    text = _strip_noise(text)
    m = EXTENDS.search(text)
    if not m:
        return []
    names: list[str] = []
    for p in _split_types(m.group(1)):
        # Strip generics: Repository<Owner, Integer> → Repository
        base = re.sub(r"<.*?>", "", p).strip()
        base = base.split(".")[-1]
        if not base or base in SKIP_EXTENDS:
            continue
        if base.endswith("Override"):
            continue
        names.append(base)
    return names


def _staging_query_methods(text: str) -> set[str]:
    return {m.group(2) for m in QUERY_METHOD.finditer(_strip_noise(text))}


def _dest_implemented_methods(text: str) -> set[str]:
    text = _strip_noise(text)
    names: set[str] = set()
    for m in DEFAULT_OR_BODY.finditer(text):
        names.add(m.group(1) or m.group(2))
    # Class methods with bodies already covered; also accept @Query retained
    # only when not using Panache (rare) — still count as non-hollow.
    if re.search(r"@Query\b", text) and not PANACHE.search(text):
        names |= _staging_query_methods(text)
    return names


def _hollow_finders(staged: str, dest: str) -> list[str]:
    """Staging @Query methods that remain bare declarations on dest."""
    want = _staging_query_methods(staged)
    if not want:
        return []
    have = _dest_implemented_methods(dest)
    # Bare declarations still present
    dest_noise = _strip_noise(dest)
    bare = {m.group(1) for m in HOLLOW_METHOD.finditer(dest_noise)}
    hollow = sorted((want & bare) - have)
    return hollow


def _is_spring_data_repo(text: str) -> bool:
    return bool(SPRING_DATA.search(text) and re.search(r"\binterface\s+\w+", text))


def _override_impls_missing(
    staged_files: dict[str, tuple[Path, str]],
    dest_files: dict[str, tuple[Path, str]],
    focus: set[str] | None,
) -> list[str]:
    """Flag staging Override Impls absent from dest once convert has started.

    Only fires when dest already has a related SpringData* / *Override file
    (or the Impl itself is in the commit focus) — never RED before the
    consolidate seat lands any springdatajpa Targets.
    """
    missing: list[str] = []
    dest_names = set(dest_files)

    def _related_dest_present(impl_fn: str) -> bool:
        stem = impl_fn[: -len(".java")]  # SpringDataPetRepositoryImpl
        base = stem.replace("Impl", "")  # SpringDataPetRepository
        # Pet from SpringDataPetRepositoryImpl
        entity = re.sub(r"^SpringData|RepositoryImpl$", "", stem)
        if base in dest_names or impl_fn in dest_names:
            return True
        if f"{entity}RepositoryOverride.java" in dest_names:
            return True
        if any(
            n.startswith("SpringData") and entity in n and n in dest_names
            for n in dest_names
        ):
            return True
        return False

    for fn, (_p, raw) in staged_files.items():
        if not fn.endswith("RepositoryImpl.java"):
            continue
        if "implements" not in raw and "Override" not in raw:
            continue
        if focus is not None:
            stem = fn[: -len(".java")]
            entity = re.sub(r"^SpringData|RepositoryImpl$", "", stem)
            related_focus = fn in focus or any(
                entity in f and ("SpringData" in f or "Override" in f or "Impl" in f)
                for f in focus
            )
            if not related_focus and not _related_dest_present(fn):
                continue
        elif not _related_dest_present(fn):
            continue
        if fn not in dest_names:
            missing.append(fn)
    return sorted(set(missing))


def check_tree(sha: str | None = None) -> list[str]:
    staging_root = ROOT / "migration" / "staging" / "src" / "main" / "java"
    dest_root = ROOT / "src" / "main" / "java"
    staged = _walk_java(staging_root)
    dests = _walk_java(dest_root)
    problems: list[str] = []

    focus: set[str] | None = None
    if sha:
        focus = {Path(n).name for n in _commit_java_names(sha)}
        # Load dest content from commit when available
        for rel in _commit_java_names(sha):
            body = _git_show(sha, rel)
            if body is not None:
                dests[Path(rel).name] = (Path(rel), body)

    for fn, (_sp, sraw) in staged.items():
        if not _is_spring_data_repo(sraw):
            continue
        if fn not in dests:
            continue
        if focus is not None and fn not in focus:
            continue
        _dp, draw = dests[fn]
        if not PANACHE.search(draw) and "Panache" not in draw:
            # O-SDJPAHARVESTONLY: harvest-from-staging left Spring Data
            # residue — convert before step_finish / tip-accept.
            if re.search(r"org\.springframework\.data\b", draw) or (
                _is_spring_data_repo(draw)
            ):
                problems.append(
                    f"O-SDJPAHARVESTONLY:{fn}: harvest-only Spring Data "
                    f"residue (no PanacheRepository) — after "
                    f"harvest-from-staging, convert to "
                    f"PanacheRepository/PanacheRepositoryBase, drop "
                    f"org.springframework.data, implement finder bodies + "
                    f"keep domain-repo contracts (O-SDJPAHARVEST) before "
                    f"step_finish; harvest ≠ consolidate"
                )
            # Non-Spring / non-Panache dest for a staged Spring Data repo
            # is a different failure class — do not soft-skip convert checks.
            continue

        # 1) domain extends
        need = _domain_extends(sraw)
        have = _domain_extends(draw)
        # class implements domain iface also OK
        cm = CLASS_IMPL.search(_strip_noise(draw))
        if cm:
            impls = [
                re.sub(r"<.*?>", "", p).strip().split(".")[-1]
                for p in _split_types(cm.group(2))
            ]
            have = sorted(
                set(have)
                | {
                    x
                    for x in impls
                    if x and x not in SKIP_EXTENDS and not x.endswith("Override")
                }
            )
        lost = [d for d in need if d not in have]
        if lost:
            problems.append(
                f"O-SDJPAHARVEST:{fn}: dropped domain repository contract "
                f"(staging extends {', '.join(need)}; dest missing "
                f"{', '.join(lost)}) — keep extends/implements <DomainRepository> "
                f"+ PanacheRepository(Base)"
            )

        # 2) orphan @NamedQuery on repository type
        if NAMED_QUERY.search(draw) and (
            re.search(r"\binterface\s+\w+", draw) or PANACHE.search(draw)
        ):
            problems.append(
                f"O-SDJPAHARVEST:{fn}: orphan @NamedQuery on repository "
                f"(staging used method @Query) — rewrite to Panache "
                f"find/list default methods or entity NamedQuery; do not park "
                f"NamedQuery on the repo interface"
            )

        # 3) hollow finders
        hollow = _hollow_finders(sraw, draw)
        if hollow:
            problems.append(
                f"O-SDJPAHARVEST:{fn}: hollow finder(s) without Panache query "
                f"body: {', '.join(hollow[:6])} — staging @Query must become "
                f"default/impl methods using find/list (empty Panache shells ≠ "
                f"consolidate)"
            )

    # 4) Override Impl harvest when SpringData* / Override touched
    impl_focus = focus
    if focus is not None:
        # Expand: if any SpringData* or *Override touched, check all staging Impls
        if any(
            "SpringData" in f or "Override" in f or f.endswith("RepositoryImpl.java")
            for f in focus
        ):
            impl_focus = None  # check all staging Override Impls vs dest
    for miss in _override_impls_missing(staged, dests, impl_focus):
        problems.append(
            f"O-SDJPAHARVEST:{miss}: staging Override Impl absent from dest — "
            f"harvest *RepositoryImpl delete bodies with Override interfaces; "
            f"iface-only empty Panache shells ≠ consolidate"
        )

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", default=None)
    args = ap.parse_args()
    problems = check_tree(args.sha)
    if problems:
        print("\n".join(problems))
        return 1
    print("sdjpa-harvest-check GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
