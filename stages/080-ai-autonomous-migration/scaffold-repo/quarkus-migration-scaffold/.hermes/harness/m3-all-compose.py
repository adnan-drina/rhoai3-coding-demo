#!/usr/bin/env python3
"""O-M3ALL skeleton-first compose — deterministic pass after M2.

One pass generates tasks.md skeletons for every roadmap story before any
model seat fills judgment:

  - task IDs from roadmap scope partition (one T-NNN per scope path)
  - Owns filled from scope (K1 / file-partition seeds)
  - Class / Shape / Port / Oracle / Assumes field lines always present
  - Oracle derived from the filesystem when a Target .java is known (fact)
  - Port field present for repository-layer paths (models may revise)
  - Assumes seeded from prior stories' Owns (projection closure)

Does **not** overwrite a non-skeleton authored plan. Skeletons carry
`<!-- O-M3ALL-SKELETON -->` so re-compose can refresh them safely.

O-M3ALLORDER / O-PLANORDER: scope paths are sorted by
`migration/dependency-order.md` convert rank before T-NNN assignment so the
skeleton cannot emit an unsatisfiable precedes storm (W4-320: 97× O-PLANORDER
from alpha/scope order vs dep-order).

Usage:
  python3 .hermes/harness/m3-all-compose.py [--root DIR] [--force-skeleton]
  Exit 0 on success; 2 on usage / missing roadmap.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKELETON_MARK = "<!-- O-M3ALL-SKELETON -->"
FINDING_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+")
REPO_SIGNAL = re.compile(
    r"(?i)\b(repository|spring\s*data|springdatajpa|panache|"
    r"jdbctemplate|namedparameterjdbc|agroal|crudrepository|"
    r"jpa\.repository|entitymanager)\b"
)

_HARNESS = Path(__file__).resolve().parent
if str(_HARNESS) not in sys.path:
    sys.path.insert(0, str(_HARNESS))
try:
    from oracle_derive import derive_oracle  # type: ignore
except Exception:  # pragma: no cover

    def derive_oracle(body: str, *, root=None, legacy_pkg="", target_pkg=""):  # type: ignore
        return "absent"


def parse_roadmap(text: str) -> list[dict]:
    heads = re.findall(r"^##\s+(S\d{2,})\s*:", text, re.M)
    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    stories = []
    for sid in heads:
        body = bodies.get(sid, "")

        def field(name: str, b: str = body) -> str:
            m = re.search(rf"^-\s*{name}:\s*(.+)$", b, re.M)
            return m.group(1).strip() if m else ""

        findings = [
            f
            for f in re.split(r"[,\s]+", field("findings"))
            if f and f != "-" and FINDING_RE.fullmatch(f)
        ]
        scope = [
            s.strip().rstrip(",") for s in field("scope").split(",") if s.strip()
        ]
        title_m = re.search(rf"^##\s+{re.escape(sid)}\s*:\s*(.+)$", text, re.M)
        title = title_m.group(1).strip() if title_m else sid
        stories.append(
            {
                "sid": sid,
                "title": title,
                "findings": findings,
                "scope": scope,
                "deploy": field("deploy").lower() == "true",
            }
        )
    return stories


def brief_slug(root: Path, sid: str, title: str) -> str:
    briefs = sorted((root / "migration" / "briefs").glob(f"{sid}-*.md"))
    if briefs:
        return briefs[0].stem
    safe = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-")
    return f"{sid}-{safe or 'plan'}"


def is_skeleton(path: Path) -> bool:
    """True only for real skeletons — not authored plans that left the mark.

    O-M3ALLMARKERSTALE: MiniMax/green tips sometimes keep
    `<!-- O-M3ALL-SKELETON -->` after fill; treating the mark alone as
    skeleton caused compose to wipe S01 on every M3-ALL restart.
    """
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if "O-M3QWENSTALL preseed" in text:
        return True
    if SKELETON_MARK not in text:
        return False
    # Marker present: only refresh if body still looks like a stub.
    return bool(
        re.search(r"skeleton \(fill from brief\)", text, re.I)
        or re.search(r"TODO — replace from brief", text)
        or re.search(r"O-M3ALL-SKELETON preseed", text, re.I)
    )


def class_simple(path: str) -> str:
    base = path.rstrip("/").split("/")[-1]
    return re.sub(r"\.java$", "", base)


def path_is_repo(path: str) -> bool:
    return bool(REPO_SIGNAL.search(path))


def path_to_fqn(rel: str) -> str:
    rel = (rel or "").lstrip("./")
    for kind in ("main", "test"):
        pref = f"src/{kind}/java/"
        if rel.startswith(pref) and rel.endswith(".java"):
            return rel[len(pref) : -5].replace("/", ".")
    return ""


def load_fqn_rank(root: Path) -> dict[str, int]:
    """ADR-24: prefer model.json condensation order; md view is fallback only."""
    ranks: dict[str, int] = {}
    model_path = root / "migration" / "model.json"
    if model_path.is_file():
        try:
            from model import load as _mload

            model = _mload(root)
            for i, item in enumerate(model.get("order") or [], start=1):
                if item.startswith("SCC-"):
                    scc = next(
                        (s for s in model.get("sccs") or [] if s["id"] == item),
                        None,
                    )
                    if scc:
                        for m in scc.get("members") or []:
                            ranks[m] = i
                else:
                    ranks[item] = i
            if ranks:
                return ranks
        except Exception:
            pass
    dep = root / "migration" / "dependency-order.md"
    if not dep.is_file():
        return ranks
    for line in dep.read_text(encoding="utf-8", errors="replace").splitlines():
        dm = re.match(r"^\s*(\d+)\.\s+([\w.]+)\s+\(", line)
        if dm:
            ranks[dm.group(2)] = int(dm.group(1))
    return ranks


def order_scope_by_dep(scope: list[str], fqn_rank: dict[str, int]) -> list[str]:
    """Stable sort: known dep-order ranks first (ascending), unknowns last."""
    if not fqn_rank:
        return list(scope)

    def key(item: tuple[int, str]) -> tuple[int, int, str]:
        idx, path = item
        fqn = path_to_fqn(path)
        rank = fqn_rank.get(fqn, 10**9)
        return (rank, idx, path)

    indexed = list(enumerate(scope))
    indexed.sort(key=key)
    return [p for _, p in indexed]


def dest_exists(root: Path, rel: str) -> bool:
    rel = rel.lstrip("./")
    try:
        return (root / rel).is_file()
    except OSError:
        return False


def mechanical_class_shape(root: Path, owns: str) -> tuple[str, str]:
    """Cheap scaffold defaults — models revise judgment in the author seat."""
    if owns.endswith(".java") and not dest_exists(root, owns):
        return "infer", "create"
    if owns.endswith(".java") and dest_exists(root, owns):
        return "rewrite", "modify"
    return "rewrite", "modify"


def oracle_for(root: Path, owns: str) -> str:
    if not owns.endswith(".java"):
        return "absent"
    body = (
        f"**Target design**:\n"
        f"- legacy → `{owns}`\n"
        f"**Owns**: `{owns}`\n"
    )
    return derive_oracle(body, root=root)


def render_task(
    *,
    tid: str,
    title: str,
    owns: str,
    findings: list[str],
    cls: str,
    shape: str,
    oracle: str,
    port: str | None,
    assumes: str | None,
) -> str:
    lines = [
        f"#### {tid}: {title}",
        f"**Class**: {cls}",
        f"**Shape**: {shape}",
        f"**Port**: {port}" if port else "**Port**:",
        f"**Owns**: `{owns}`" if owns else "**Owns**:",
        f"**Oracle**: {oracle}",
        f"**Assumes**: {assumes}" if assumes else "**Assumes**:",
        f"**Findings**: {', '.join(findings) if findings else '(none — fill from brief)'}",
        "**Goal**: <!-- JUDGMENT: one sentence from brief — replace this marker -->",
        "**Target design**:",
    ]
    if owns:
        lines.append(f"- → `{owns}`")
    else:
        lines.append("- <!-- JUDGMENT: legacy → dest mapping -->")
    lines.append("**Acceptance**: plan-lint green; sensors green")
    lines.append("")
    return "\n".join(lines)


def extract_owns(path: Path, sid: str) -> list[tuple[str, str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    owns_list: list[tuple[str, str, str]] = []
    for m in re.finditer(r"(?m)^####\s+(T-\d+):", text):
        tid = m.group(1)
        start = m.end()
        nxt = re.search(r"(?m)^####\s+T-\d+:", text[start:])
        block = text[start : start + nxt.start()] if nxt else text[start:]
        om = re.search(r"(?im)^\*\*Owns\*\*\s*:?\s*`?([^`\n]+)", block)
        if om:
            owns_list.append((sid, tid, om.group(1).strip("` ").strip()))
    return owns_list


def compose_story(
    root: Path,
    story: dict,
    prior_first: list[tuple[str, str, str]],
    *,
    force: bool,
) -> tuple[Path, str, list[tuple[str, str, str]]]:
    """Return (path, status, owns) where status is wrote|skipped|refreshed."""
    sid = story["sid"]
    slug = brief_slug(root, sid, story["title"])
    out_dir = root / "specs" / slug
    out_path = out_dir / "tasks.md"

    if out_path.is_file() and not is_skeleton(out_path) and not force:
        return out_path, "skipped", extract_owns(out_path, sid)

    # ADR-24: when model.json is bound, emit one skeleton task per condensation
    # unit (SCC batch required; singletons seat-authored). Else legacy scope path.
    tasks: list[str] = []
    story_owns: list[tuple[str, str, str]] = []
    model_units: list[dict] = []
    model_path = root / "migration" / "model.json"
    if model_path.is_file():
        try:
            from model import load as _mload, skeleton_condensation_units

            model_units = skeleton_condensation_units(_mload(root), sid)
        except Exception:
            model_units = []

    if model_units:
        for i, cu in enumerate(model_units, start=1):
            tid = f"T-{i:03d}"
            owns_list = cu.get("owns") or []
            # render_task wraps Owns in backticks once — pass bare joined paths
            owns_field = " ".join(owns_list)
            title = cu.get("title") or "skeleton (fill from brief)"
            if cu.get("kind") == "scc":
                shape = f"batch:{cu['id']}"
                cls = "infer"
                oracle = "absent"
                port = None
            else:
                one = owns_list[0] if owns_list else ""
                cls, shape = (
                    mechanical_class_shape(root, one) if one else ("rewrite", "modify")
                )
                oracle = oracle_for(root, one) if one else "absent"
                port = "reimplement" if one and path_is_repo(one) else None
            assumes = None
            if prior_first and i == 1:
                psid, ptid, ppath = prior_first[0]
                pcls = class_simple(ppath) if ppath.endswith(".java") else ppath
                assumes = f"{pcls} exists ({psid} {ptid})"
            findings = story["findings"] if i == 1 else []
            tasks.append(
                render_task(
                    tid=tid,
                    title=title,
                    owns=owns_field,
                    findings=findings,
                    cls=cls,
                    shape=shape,
                    oracle=oracle,
                    port=port,
                    assumes=assumes,
                )
            )
            if owns_list:
                story_owns.append((sid, tid, owns_list[0]))
    else:
        scope = list(story["scope"]) or [""]
        # O-M3ALLORDER: T-NNN order must respect convert ranks
        # (otherwise O-PLANORDER fires O(n²) precedes on the skeleton itself).
        scope = order_scope_by_dep(scope, load_fqn_rank(root))
        for i, owns in enumerate(scope, start=1):
            tid = f"T-{i:03d}"
            leaf = class_simple(owns) if owns else "plan-stub"
            title = f"{leaf} — skeleton (fill from brief)"
            cls, shape = (
                mechanical_class_shape(root, owns) if owns else ("rewrite", "modify")
            )
            oracle = oracle_for(root, owns) if owns else "absent"
            port = "reimplement" if owns and path_is_repo(owns) else None
            assumes = None
            if prior_first and i == 1:
                psid, ptid, ppath = prior_first[0]
                pcls = class_simple(ppath) if ppath.endswith(".java") else ppath
                assumes = f"{pcls} exists ({psid} {ptid})"
            findings = story["findings"] if i == 1 else []
            tasks.append(
                render_task(
                    tid=tid,
                    title=title,
                    owns=owns,
                    findings=findings,
                    cls=cls,
                    shape=shape,
                    oracle=oracle,
                    port=port,
                    assumes=assumes,
                )
            )
            if owns:
                story_owns.append((sid, tid, owns))

    body = "\n".join(
        [
            f"# {slug} Tasks",
            "",
            SKELETON_MARK,
            "# O-M3ALL skeleton-first compose — mechanical fields only.",
            "# Model fills JUDGMENT markers (Goal / Target design / Class·Shape revise).",
            "# Do not delete Oracle / Port / Owns / Assumes field lines.",
            "",
            "UI surface: waived (API-only).  <!-- revise if brief requires UI -->",
            "",
            *tasks,
        ]
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    existed = out_path.is_file()
    out_path.write_text(body + "\n", encoding="utf-8")
    return out_path, ("refreshed" if existed else "wrote"), story_owns


def main() -> int:
    ap = argparse.ArgumentParser(description="O-M3ALL skeleton-first compose")
    ap.add_argument("--root", default=".", help="migration workspace root")
    ap.add_argument(
        "--force-skeleton",
        action="store_true",
        help="overwrite even non-skeleton tasks.md (tests only)",
    )
    ap.add_argument(
        "--roadmap",
        default="",
        help="override roadmap path (default: <root>/migration/roadmap.md)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    roadmap = Path(args.roadmap) if args.roadmap else root / "migration" / "roadmap.md"
    if not roadmap.is_file():
        print(f"O-M3ALL compose RED: missing roadmap {roadmap}", file=sys.stderr)
        return 2

    stories = parse_roadmap(roadmap.read_text(encoding="utf-8", errors="replace"))
    if not stories:
        print("O-M3ALL compose RED: no stories in roadmap", file=sys.stderr)
        return 2

    chrono_prior: list[tuple[str, str, str]] = []
    wrote = refreshed = skipped = 0
    for story in stories:
        seed: list[tuple[str, str, str]] = []
        if chrono_prior:
            last_sid = chrono_prior[-1][0]
            # first Owns of the immediately previous story
            for sid, tid, p in chrono_prior:
                if sid == last_sid:
                    seed = [(sid, tid, p)]
                    break
        path, status, owns_list = compose_story(
            root, story, seed, force=args.force_skeleton
        )
        if status == "wrote":
            wrote += 1
            print(f"O-M3ALL compose: wrote {path}")
        elif status == "refreshed":
            refreshed += 1
            print(f"O-M3ALL compose: refreshed skeleton {path}")
        else:
            skipped += 1
            print(f"O-M3ALL compose: skipped authored plan {path}")
        chrono_prior.extend(owns_list)

    print(
        f"O-M3ALL compose: done stories={len(stories)} "
        f"wrote={wrote} refreshed={refreshed} skipped={skipped}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
