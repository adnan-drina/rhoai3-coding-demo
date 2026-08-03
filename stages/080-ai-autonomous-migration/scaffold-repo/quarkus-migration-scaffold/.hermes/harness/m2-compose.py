#!/usr/bin/env python3
"""O-M2COMPOSE skeleton-first / bookkeeping compose — deterministic M2 pass.

Symmetric with m3-all-compose.py: bookkeeping the lint already knows how to
derive must not be re-asked of the model.

Modes:
  skeleton — if roadmap missing (or marked skeleton), cut a unique-owner
             partition from findings-inventory (+ optional dependency-order
             path hints), emit brief stubs, non-mandatory decision rows,
             deploy on last story.
  fill     — repair an existing roadmap/briefs: unique-owner partition,
             strip recipe-owned claims, brief stubs for missing stories,
             non-mandatory table completeness, last-story deploy, and
             **computed seat-budget** from seat-budget.py whenever kind is set.

Leave judgment to the model: story titles/rationale refinement, kind,
fabrication quotes, O-PORTDERIVE target contracts, adopt/defer reasons.

Usage:
  python3 .hermes/harness/m2-compose.py [--root DIR] [--mode skeleton|fill]
  Exit 0 on success; 2 on usage / missing inventory.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path

SKELETON_MARK = "<!-- O-M2COMPOSE-SKELETON -->"
FINDING_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+")
BRIEF_SECTIONS = [
    "Goal & position",
    "In scope",
    "Out of scope",
    "Decided target shapes",
    "Contracts",
    "Done-criteria",
]

# Path → layer (general Spring Boot → Quarkus migration shapes; not specimen).
LAYER_ORDER = (
    "platform",
    "model",
    "repository",
    "service",
    "surface",
    "other",
)
LAYER_TITLE = {
    "platform": "Platform and BOM conversion",
    "model": "Domain model foundation",
    "repository": "Repository layer",
    "service": "Service layer modernization",
    "surface": "REST surface and configuration",
    "other": "Remaining modernization",
}

_HARNESS = Path(__file__).resolve().parent
_SB_PATH = _HARNESS / "seat-budget.py"
_sb_spec = importlib.util.spec_from_file_location("seat_budget", _SB_PATH)
seat_budget = importlib.util.module_from_spec(_sb_spec)
assert _sb_spec.loader is not None
_sb_spec.loader.exec_module(seat_budget)


def layer_for_path(path: str) -> str:
    p = path.replace("\\", "/").lower()
    if p.endswith("pom.xml") or "/pom.xml" in p or p == "pom.xml":
        return "platform"
    if re.search(r"/model/|/dto/|/domain/", p):
        return "model"
    if re.search(r"/repository/|/repo/|/persistence/", p):
        return "repository"
    if re.search(r"/service/|/services/", p):
        return "service"
    if re.search(
        r"/rest/|/web/|/api/|/controller/|/resource/|/security/|/config/", p
    ):
        return "surface"
    if p.endswith(".properties") or p.endswith(".yaml") or p.endswith(".yml"):
        return "platform"
    return "other"


def parse_inventory(inv: str) -> dict:
    """Extract must / recipe / non-mandatory sets, open-design, per-rule sites."""
    must: set[str] = set()
    recipe: set[str] = set()
    non_mandatory: set[str] = set()
    open_design: set[str] = set()
    sites: dict[str, list[str]] = defaultdict(list)
    current = None
    current_bucket = None

    for line in inv.splitlines():
        hm = re.match(
            r"^##\s+([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)\s*\[([^\]]+)\]",
            line,
        )
        if hm:
            current = hm.group(1)
            current_bucket = hm.group(2).strip()
            if current_bucket.upper().startswith("OPEN"):
                open_design.add(current)
            continue
        sm = re.match(r"^-\s+(\S+):\s*line\s+", line)
        if sm and current:
            uri = sm.group(1)
            # inventory often uses absolute /projects/legacy/... — keep tail
            if "/projects/legacy/" in uri:
                uri = uri.split("/projects/legacy/", 1)[1]
            elif uri.startswith("file://"):
                uri = re.sub(r"^file:/*", "/", uri)
            sites[current].append(uri)

    for m in re.finditer(
        r"^-\s*(recipe|rewrite|infer|OPEN DESIGN|non-mandatory):\s*\d+\s*—\s*(.*)$",
        inv,
        re.M,
    ):
        bucket = m.group(1)
        ids = {x for x in re.split(r"[,\s]+", m.group(2)) if FINDING_RE.fullmatch(x)}
        if bucket == "recipe":
            recipe |= ids
        elif bucket == "non-mandatory":
            non_mandatory |= ids
        elif bucket == "OPEN DESIGN":
            open_design |= ids
            must |= ids
        else:
            must |= ids

    # Headings not listed in summary still count as mandatory unless recipe/nm
    for rid in list(sites) + list(open_design):
        if rid not in recipe and rid not in non_mandatory:
            must.add(rid)

    must -= recipe
    must -= non_mandatory
    return {
        "must": must,
        "recipe": recipe,
        "non_mandatory": non_mandatory,
        "open_design": open_design,
        "sites": dict(sites),
    }


def parse_roadmap(text: str) -> list[dict]:
    heads = re.findall(r"^##\s+(S\d{2,})\s*:\s*(.+)$", text, re.M)
    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    stories = []
    for sid, title in heads:
        body = bodies.get(sid, "")
        # Trim trailing non-story section (e.g. Non-mandatory) from last body
        body = re.split(r"(?m)^##\s+(?!S\d)", body, maxsplit=1)[0]

        def field(name: str, b: str = body) -> str | None:
            m = re.search(rf"^-\s*{name}:[ \t]*(.*)$", b, re.M)
            return m.group(1).strip() if m else None

        findings_raw = (field("findings") or "").strip()
        findings = [
            f
            for f in re.split(r"[,\s]+", findings_raw)
            if f and f != "-" and FINDING_RE.fullmatch(f)
        ]
        stories.append(
            {
                "sid": sid,
                "title": title.strip(),
                "scope": field("scope") or "",
                "findings": findings,
                "findings_raw": findings_raw,
                "depends": field("depends") or "-",
                "deploy": (field("deploy") or "false").lower() == "true",
                "done": field("done") or "<!-- JUDGMENT: checkable done-criterion -->",
                "rationale": field("rationale")
                or "<!-- JUDGMENT: why this story, why now -->",
                "kind": field("kind"),
                "seat_budget": field("seat-budget"),
                "body": body,
            }
        )
    return stories


def is_roadmap_skeleton(text: str) -> bool:
    return SKELETON_MARK in text


def slugify(title: str) -> str:
    safe = re.sub(r"[^a-z0-9-]+", "-", title.lower()).strip("-")
    return safe or "story"


def best_story_for_finding(
    fid: str, sites: dict[str, list[str]], stories: list[dict]
) -> str:
    """Pick unique owner by path/layer overlap with story scope."""
    paths = sites.get(fid) or []
    if not stories:
        return "S01"
    if not paths:
        # Prefer a story that already owns something; else first
        for st in stories:
            if st["findings"]:
                return st["sid"]
        return stories[0]["sid"]

    layers = {layer_for_path(p) for p in paths}
    scores: list[tuple[int, str]] = []
    for st in stories:
        scope = st["scope"] or ""
        score = 0
        for p in paths:
            leaf = p.rsplit("/", 1)[-1]
            if leaf and leaf in scope:
                score += 3
            lay = layer_for_path(p)
            if lay == "platform" and "pom.xml" in scope:
                score += 2
            if lay != "other" and lay in scope.lower():
                score += 1
            # layer name vs typical scope dirs
            for token in (
                "model",
                "repository",
                "service",
                "rest",
                "security",
                "config",
            ):
                if token in p and token in scope.lower():
                    score += 1
        # soft prefer layer-aligned empty-ish stories
        if score == 0 and layers:
            for lay in layers:
                if lay == "platform" and "pom.xml" in scope:
                    score = 1
        scores.append((score, st["sid"]))
    scores.sort(key=lambda x: (-x[0], x[1]))
    if scores[0][0] > 0:
        return scores[0][1]
    # fallback: first story with non-harvest findings field capacity
    for st in stories:
        if st["findings_raw"] != "-":
            return st["sid"]
    return stories[0]["sid"]


def unique_partition(
    stories: list[dict], inv: dict
) -> list[dict]:
    """Each mandatory finding owned exactly once; strip recipe claims."""
    must = inv["must"]
    recipe = inv["recipe"]
    sites = inv["sites"]

    # First pass: drop recipe + keep first owner on duals
    claimed: dict[str, str] = {}
    for st in stories:
        kept: list[str] = []
        for fid in st["findings"]:
            if fid in recipe:
                continue
            if fid not in must and fid not in inv["open_design"]:
                # unknown / already non-mandatory — drop from ownership
                if fid in inv["non_mandatory"]:
                    continue
            if fid in claimed:
                continue
            claimed[fid] = st["sid"]
            kept.append(fid)
        st["findings"] = kept
        if kept:
            st["findings_raw"] = ", ".join(kept)
        elif st["findings_raw"] == "-" or not st["findings_raw"]:
            st["findings_raw"] = "-"
        else:
            st["findings_raw"] = ", ".join(kept) if kept else "-"

    # Assign orphans
    for fid in sorted(must - set(claimed)):
        sid = best_story_for_finding(fid, sites, stories)
        for st in stories:
            if st["sid"] == sid:
                st["findings"].append(fid)
                if st["findings_raw"] in ("", "-"):
                    st["findings_raw"] = fid
                else:
                    st["findings_raw"] = ", ".join(st["findings"])
                claimed[fid] = sid
                break
    return stories


def ensure_deploy_last(stories: list[dict]) -> None:
    if not stories:
        return
    for st in stories[:-1]:
        # leave earlier deploy flags; only enforce last
        pass
    stories[-1]["deploy"] = True


def render_roadmap(stories: list[dict], non_mandatory: set[str], prior_nm: str) -> str:
    lines = [
        "# Modernization roadmap",
        "",
        SKELETON_MARK,
        "# O-M2COMPOSE — mechanical partition / deploy / seat-budget / K3 rows.",
        "# Model fills JUDGMENT (kind, rationale, quotes, adopt/defer reasons, §7 contracts).",
        "",
    ]
    for i, st in enumerate(stories):
        dep = st["depends"]
        if dep == "-" and i > 0:
            dep = stories[i - 1]["sid"]
        lines.append(f"## {st['sid']}: {st['title']}")
        lines.append(f"- scope: {st['scope'] or '<!-- JUDGMENT: target paths -->'}")
        lines.append(f"- findings: {st['findings_raw'] or '-'}")
        lines.append(f"- depends: {dep}")
        lines.append(f"- deploy: {'true' if st['deploy'] else 'false'}")
        lines.append(f"- done: {st['done']}")
        lines.append(f"- rationale: {st['rationale']}")
        if st.get("kind"):
            lines.append(f"- kind: {st['kind']}")
        if st.get("seat_budget") is not None and str(st.get("seat_budget")).strip() != "":
            lines.append(f"- seat-budget: {st['seat_budget']}")
        lines.append("")

    # Preserve existing adopt/defer decisions when present
    existing: dict[str, str] = {}
    for m in re.finditer(
        r"(?m)^\|\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)\s*\|\s*(adopt|defer)\s*\|\s*(.*?)\s*\|",
        prior_nm,
    ):
        existing[m.group(1)] = f"{m.group(2)}|{m.group(3).strip()}"
    for m in re.finditer(
        r"(?m)^-\s*([a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+)\s*:\s*(adopt|defer(?:\s*\([^)]*\))?)\s*$",
        prior_nm,
    ):
        existing[m.group(1)] = m.group(2).strip()

    lines.append("## Non-mandatory decisions")
    lines.append("")
    if non_mandatory:
        lines.append("| rule-id | decision | reason |")
        lines.append("|---|---|---|")
        for rid in sorted(non_mandatory):
            if rid in existing:
                val = existing[rid]
                if "|" in val:
                    dec, reason = val.split("|", 1)
                    lines.append(f"| {rid} | {dec} | {reason} |")
                elif val.startswith("defer"):
                    reason = ""
                    dm = re.match(r"defer(?:\s*\(([^)]*)\))?", val)
                    if dm and dm.group(1):
                        reason = dm.group(1)
                    lines.append(f"| {rid} | defer | {reason} |")
                elif val == "adopt":
                    lines.append(f"| {rid} | adopt | |")
                else:
                    lines.append(f"| {rid} |  |  |")
            else:
                lines.append(f"| {rid} |  |  |")
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def apply_seat_budgets(stories: list[dict], inv_text: str) -> int:
    """Write computed seat-budget when kind is set. Returns count updated."""
    n_upd = 0
    for st in stories:
        kind = seat_budget.parse_kind(st.get("kind"))
        if not kind:
            continue
        fids = set(st["findings"])
        inc = seat_budget.story_incident_total(inv_text, fids)
        expected = seat_budget.expected_budget(kind, inc)
        cur = seat_budget.parse_seat_budget_field(st.get("seat_budget"))
        if cur != expected:
            st["seat_budget"] = str(expected)
            n_upd += 1
        elif st.get("seat_budget") is None:
            st["seat_budget"] = str(expected)
            n_upd += 1
    return n_upd


def brief_path(root: Path, sid: str, title: str) -> Path:
    briefs = sorted((root / "migration" / "briefs").glob(f"{sid}-*.md"))
    if briefs:
        return briefs[0]
    return root / "migration" / "briefs" / f"{sid}-{slugify(title)}.md"


def brief_is_skeleton(text: str) -> bool:
    return SKELETON_MARK in text


def render_brief_stub(st: dict) -> str:
    budget_line = ""
    if st.get("seat_budget"):
        budget_line = f"\n- **seat-budget**: `{st['seat_budget']}`\n"
    elif st.get("kind") and seat_budget.parse_kind(st.get("kind")):
        budget_line = "\n- **seat-budget**: `<!-- filled by m2-compose when kind set -->`\n"
    findings = st["findings_raw"] or "-"
    return "\n".join(
        [
            f"# {st['sid']}: {st['title']}",
            "",
            SKELETON_MARK,
            "# O-M2COMPOSE brief stub — model fills JUDGMENT quotes / §7 contracts.",
            "",
            "## Goal & position",
            "",
            "<!-- JUDGMENT: what this story achieves and why it is next -->",
            "",
            "## In scope",
            "",
            "<!-- JUDGMENT: quote REAL legacy lines per class (fabrication gate) -->",
            "",
            f"- scope seeds: `{st['scope']}`" if st["scope"] else "- <!-- paths -->",
            "",
            "## Out of scope",
            "",
            "<!-- JUDGMENT: neighboring code this story must not touch -->",
            "",
            "## Decided target shapes",
            "",
            "<!-- JUDGMENT: MAPPINGS decided targets; REDESIGN §7 contracts -->",
            "",
            "## Contracts",
            "",
            f"- **Findings**: {findings}",
            budget_line.rstrip("\n"),
            "- **Preserve**: <!-- from migration.yaml -->",
            "- **Behavioral pins**: <!-- JUDGMENT -->",
            "- **Forbidden**: <!-- fabrication tripwires -->",
            "",
            "## Done-criteria",
            "",
            f"- {st['done']}",
            "",
        ]
    )


def ensure_brief_seat_budget(path: Path, n: int) -> bool:
    """Publish seat-budget: N in brief; return True if changed."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if seat_budget.brief_has_seat_budget(text, n):
        return False
    # Replace existing seat-budget publish or inject under Contracts
    new, count = re.subn(
        r"(?im)((?:seat-budget|\*\*seat budget\*\*|seat budget)\s*[:=]\s*)\d+",
        rf"\g<1>{n}",
        text,
        count=1,
    )
    if count:
        path.write_text(new, encoding="utf-8")
        return True
    if re.search(r"(?im)^##\s+Contracts", text):
        new = re.sub(
            r"(?im)(^##\s+Contracts[^\n]*\n)",
            rf"\1\n- **seat-budget**: `{n}`\n",
            text,
            count=1,
        )
        path.write_text(new, encoding="utf-8")
        return True
    path.write_text(text.rstrip() + f"\n\n- **seat-budget**: `{n}`\n", encoding="utf-8")
    return True


def write_briefs(root: Path, stories: list[dict], *, force_skeleton: bool) -> tuple[int, int]:
    wrote = refreshed = 0
    bdir = root / "migration" / "briefs"
    bdir.mkdir(parents=True, exist_ok=True)
    for st in stories:
        path = brief_path(root, st["sid"], st["title"])
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            if not brief_is_skeleton(text) and not force_skeleton:
                # authored — only ensure seat-budget publish
                if st.get("seat_budget"):
                    try:
                        n = int(str(st["seat_budget"]).split()[0])
                    except ValueError:
                        n = None
                    if n is not None and ensure_brief_seat_budget(path, n):
                        refreshed += 1
                continue
            path.write_text(render_brief_stub(st), encoding="utf-8")
            refreshed += 1
        else:
            path.write_text(render_brief_stub(st), encoding="utf-8")
            wrote += 1
    return wrote, refreshed


def skeleton_from_inventory(inv: dict, dep_text: str = "") -> list[dict]:
    """Mechanical story cut: one story per non-empty path layer."""
    layer_findings: dict[str, list[str]] = defaultdict(list)
    layer_scopes: dict[str, set[str]] = defaultdict(set)

    for fid in sorted(inv["must"]):
        paths = inv["sites"].get(fid) or []
        if not paths:
            layer_findings["other"].append(fid)
            continue
        # majority layer
        counts: dict[str, int] = defaultdict(int)
        for p in paths:
            counts[layer_for_path(p)] += 1
            layer_scopes[layer_for_path(p)].add(p)
        lay = sorted(counts.items(), key=lambda x: (-x[1], LAYER_ORDER.index(x[0])))[0][0]
        layer_findings[lay].append(fid)

    # Also pull scope hints from dependency-order paths when present
    for m in re.finditer(r"\(([^)]+\.java)\)", dep_text):
        p = m.group(1)
        layer_scopes[layer_for_path(p)].add(p)

    stories: list[dict] = []
    idx = 1
    for lay in LAYER_ORDER:
        fids = layer_findings.get(lay) or []
        scopes = sorted(layer_scopes.get(lay) or [])
        if not fids and not scopes:
            continue
        if lay == "platform" and not scopes:
            scopes = ["pom.xml"]
        # Cap scope list for readability; model may refine
        scope_s = ", ".join(scopes[:40]) if scopes else "<!-- JUDGMENT: paths -->"
        sid = f"S{idx:02d}"
        stories.append(
            {
                "sid": sid,
                "title": LAYER_TITLE[lay],
                "scope": scope_s,
                "findings": list(fids),
                "findings_raw": ", ".join(fids) if fids else "-",
                "depends": "-" if idx == 1 else f"S{idx-1:02d}",
                "deploy": False,
                "done": "<!-- JUDGMENT: checkable done-criterion -->",
                "rationale": f"O-M2COMPOSE layer={lay} unique-owner partition from findings-inventory",
                "kind": None,
                "seat_budget": None,
                "body": "",
            }
        )
        idx += 1

    if not stories:
        stories.append(
            {
                "sid": "S01",
                "title": "Modernization increment",
                "scope": "pom.xml",
                "findings": sorted(inv["must"]),
                "findings_raw": ", ".join(sorted(inv["must"])) or "-",
                "depends": "-",
                "deploy": True,
                "done": "<!-- JUDGMENT: checkable done-criterion -->",
                "rationale": "O-M2COMPOSE fallback single-story partition",
                "kind": None,
                "seat_budget": None,
                "body": "",
            }
        )
    ensure_deploy_last(stories)
    return stories


def extract_nm_section(text: str) -> str:
    m = re.search(r"(?im)^##\s+Non-mandatory decisions\b.*", text, re.S)
    return m.group(0) if m else ""


def compose(root: Path, mode: str, *, force_skeleton: bool = False) -> int:
    inv_path = root / "migration" / "findings-inventory.md"
    if not inv_path.is_file():
        print(f"O-M2COMPOSE RED: missing {inv_path}", file=sys.stderr)
        return 2
    inv_text = inv_path.read_text(encoding="utf-8", errors="replace")
    inv = parse_inventory(inv_text)
    roadmap_path = root / "migration" / "roadmap.md"
    dep_path = root / "migration" / "dependency-order.md"
    dep_text = (
        dep_path.read_text(encoding="utf-8", errors="replace")
        if dep_path.is_file()
        else ""
    )

    prior_nm = ""
    wrote_roadmap = False
    if mode == "skeleton":
        if roadmap_path.is_file() and not force_skeleton:
            text = roadmap_path.read_text(encoding="utf-8", errors="replace")
            if not is_roadmap_skeleton(text):
                print(
                    "O-M2COMPOSE: skeleton skipped — authored roadmap present "
                    "(use --mode fill or --force-skeleton)"
                )
                # Still run fill bookkeeping on authored roadmap
                mode = "fill"
            else:
                prior_nm = extract_nm_section(text)
                stories = skeleton_from_inventory(inv, dep_text)
                # Preserve kind/seat-budget if re-skeletonizing
                old = parse_roadmap(text)
                by_sid = {s["sid"]: s for s in old}
                for st in stories:
                    if st["sid"] in by_sid and by_sid[st["sid"]].get("kind"):
                        st["kind"] = by_sid[st["sid"]]["kind"]
                stories = unique_partition(stories, inv)
                apply_seat_budgets(stories, inv_text)
                ensure_deploy_last(stories)
                roadmap_path.write_text(
                    render_roadmap(stories, inv["non_mandatory"], prior_nm),
                    encoding="utf-8",
                )
                wrote_roadmap = True
                print(f"O-M2COMPOSE: wrote skeleton roadmap stories={len(stories)}")
        if not roadmap_path.is_file() or force_skeleton:
            stories = skeleton_from_inventory(inv, dep_text)
            stories = unique_partition(stories, inv)
            apply_seat_budgets(stories, inv_text)
            ensure_deploy_last(stories)
            roadmap_path.parent.mkdir(parents=True, exist_ok=True)
            roadmap_path.write_text(
                render_roadmap(stories, inv["non_mandatory"], ""),
                encoding="utf-8",
            )
            wrote_roadmap = True
            print(f"O-M2COMPOSE: wrote skeleton roadmap stories={len(stories)}")

    if mode == "fill":
        if not roadmap_path.is_file():
            print(
                "O-M2COMPOSE: no roadmap — falling through to skeleton",
                file=sys.stderr,
            )
            return compose(root, "skeleton", force_skeleton=True)
        text = roadmap_path.read_text(encoding="utf-8", errors="replace")
        prior_nm = extract_nm_section(text)
        stories = parse_roadmap(text)
        if not stories:
            print("O-M2COMPOSE RED: roadmap has no stories", file=sys.stderr)
            return 2
        stories = unique_partition(stories, inv)
        n_budget = apply_seat_budgets(stories, inv_text)
        ensure_deploy_last(stories)
        # Keep authored marker status: if it was skeleton, stay skeleton;
        # if authored, rewrite without forcing skeleton mark only when
        # bookkeeping fields change — still emit mark only if prior had it.
        body = render_roadmap(stories, inv["non_mandatory"], prior_nm)
        if not is_roadmap_skeleton(text):
            body = body.replace(SKELETON_MARK + "\n", "")
            body = re.sub(
                r"# O-M2COMPOSE — mechanical[^\n]*\n"
                r"# Model fills JUDGMENT[^\n]*\n\n?",
                "",
                body,
                count=1,
            )
        roadmap_path.write_text(body, encoding="utf-8")
        wrote_roadmap = True
        print(
            f"O-M2COMPOSE: fill stories={len(stories)} "
            f"seat-budget-updates={n_budget} must={len(inv['must'])}"
        )

    # Reload stories for brief sync
    stories = parse_roadmap(
        roadmap_path.read_text(encoding="utf-8", errors="replace")
    )
    # Re-apply budgets onto parsed stories for brief publish
    apply_seat_budgets(stories, inv_text)
    # Persist budget fields again if fill stripped them somehow
    if any(st.get("kind") and st.get("seat_budget") for st in stories):
        prior_nm = extract_nm_section(
            roadmap_path.read_text(encoding="utf-8", errors="replace")
        )
        body = render_roadmap(stories, inv["non_mandatory"], prior_nm)
        cur = roadmap_path.read_text(encoding="utf-8", errors="replace")
        if not is_roadmap_skeleton(cur):
            body = body.replace(SKELETON_MARK + "\n", "")
            body = re.sub(
                r"# O-M2COMPOSE — mechanical[^\n]*\n"
                r"# Model fills JUDGMENT[^\n]*\n\n?",
                "",
                body,
                count=1,
            )
        if body != cur:
            roadmap_path.write_text(body, encoding="utf-8")
            wrote_roadmap = True

    bw, br = write_briefs(root, stories, force_skeleton=force_skeleton)
    print(
        f"O-M2COMPOSE: done mode={mode} roadmap_written={wrote_roadmap} "
        f"briefs_wrote={bw} briefs_refreshed={br}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="O-M2COMPOSE skeleton-first M2 compose")
    ap.add_argument("--root", default=".", help="migration workspace root")
    ap.add_argument(
        "--mode",
        choices=("skeleton", "fill"),
        default="fill",
        help="skeleton=create/refresh partition; fill=repair bookkeeping (default)",
    )
    ap.add_argument(
        "--force-skeleton",
        action="store_true",
        help="overwrite authored roadmap/briefs with skeleton (tests only)",
    )
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    return compose(root, args.mode, force_skeleton=args.force_skeleton)


if __name__ == "__main__":
    sys.exit(main())
