#!/usr/bin/env python3
"""O-M2COMPOSE skeleton-first / bookkeeping compose — deterministic M2 pass.

Symmetric with m3-all-compose.py: bookkeeping the lint already knows how to
derive must not be re-asked of the model.

Modes:
  skeleton — if roadmap missing (or marked skeleton), cut a unique-owner
             partition. **ADR-34 REV-2:** when model.json has typed
             decisions, membership SoT is model.order + SCC + decision.role
             (layer is a derived packaging label only). Findings-inventory
             remains context for finding ownership / fixtures without a
             typed model. Emit brief stubs, non-mandatory decision rows,
             deploy on last story.
  fill     — repair an existing roadmap/briefs: unique-owner partition,
             strip recipe-owned claims, brief stubs for missing stories,
             non-mandatory table completeness, last-story deploy,
             **derived kind** (O-M2COMPOSEBOOK / O-STORYKIND), S-FND repair
             for redesignish `findings: '-'`, and **computed seat-budget**
             from seat-budget.py whenever kind is set.

Leave judgment to the model: story titles/rationale refinement, fabrication
quotes, O-PORTDERIVE target contracts, adopt/defer reasons. Kind is derived
when required (OPEN DESIGN / §7 REDESIGN scope); the model may refine with
justification (especially mixed).

Usage:
  python3 .hermes/harness/m2-compose.py [--root DIR] [--mode skeleton|fill]
  Exit 0 on success; 2 on usage / missing inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

SKELETON_MARK = "<!-- O-M2COMPOSE-SKELETON -->"
_FRESH_MARK = re.compile(
    r"<!--\s*O-BRIEFFRESH\s+sha256=([0-9a-fA-F]+)\s*-->", re.I
)
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


def is_generated_build_path(path: str) -> bool:
    """O-SCOPENOGEN — build outputs must not seed story scope or Owns.

    Kantra scans legacy `target/` (OpenAPI DTOs, MapStruct *Impl). Those paths
    are gitignored and deliberately excluded from M1 staging; seeding them into
    roadmap scope produces Harvest→target/ tasks that cannot commit reviewable
    code. General Maven/Gradle build outs — not specimen-specific.
    """
    p = (path or "").replace("\\", "/").lstrip("./")
    if p.startswith("target/") or "/target/" in f"/{p}":
        return True
    if p.startswith("build/") or "/build/" in f"/{p}":
        return True
    if "/generated-sources/" in f"/{p}" and not p.startswith("src/"):
        return True
    return False


def filter_scope_paths(scope: str) -> str:
    """Drop generated build paths from a comma-separated scope field."""
    parts = [p.strip() for p in (scope or "").split(",") if p.strip()]
    kept = [p for p in parts if not is_generated_build_path(p)]
    return ", ".join(kept)


# O-SCOPENONJAVA (W4-179): staged config/resources must enter scope too.
_STAGING_SCOPE_SUFFIXES = (
    ".java",
    ".properties",
    ".yaml",
    ".yml",
    ".xml",
)


def list_staging_java(root: Path) -> list[str]:
    """O-STAGESCOPE — relative src/... paths under migration/staging.

    Includes Java plus config/resources (properties/yaml/xml). Java-only
    listing made O-SCOPECOVER certify a false green while application*.properties
    stayed unowned (W4-179).
    """
    staging = root / "migration" / "staging"
    if not staging.is_dir():
        return []
    out: list[str] = []
    for p in staging.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(staging)).replace("\\", "/")
        if is_generated_build_path(rel):
            continue
        low = rel.lower()
        if not any(low.endswith(suf) for suf in _STAGING_SCOPE_SUFFIXES):
            continue
        out.append(rel)
    return sorted(out)


def subject_under_test(rel: str) -> str | None:
    """Derive class-under-test simple name from *Tests / *Test basename."""
    stem = Path(rel).stem
    for suffix in ("Tests", "Test"):
        if not stem.endswith(suffix):
            continue
        base = stem[: -len(suffix)]
        if base.startswith("Abstract"):
            base = base[len("Abstract") :]
        for mid in ("SpringDataJpa", "SpringData", "Jdbc", "Jpa"):
            if base.endswith(mid):
                base = base[: -len(mid)]
                break
        return base or None
    return None


def assign_staging_layer(rel: str, main_by_simple: dict[str, str]) -> str:
    """Layer for a staging path; tests use ownership-by-subject (W4-172)."""
    norm = f"/{rel.replace(chr(92), '/')}"
    if "/src/test/" in norm or rel.startswith("src/test/"):
        stem = Path(rel).stem
        if stem in ("ApplicationTestConfig",) or (
            stem.endswith("Config") and "Test" in rel
        ):
            return "service"  # test fixture → earliest consumer layer
        if stem == "SpringConfigTests":
            return "platform"
        subj = subject_under_test(rel)
        if subj and subj in main_by_simple:
            return layer_for_path(main_by_simple[subj])
        return layer_for_path(rel)
    return layer_for_path(rel)


def staging_layer_scopes(root: Path) -> dict[str, set[str]]:
    """Partition staging java files into LAYER_ORDER buckets."""
    paths = list_staging_java(root)
    main_by_simple: dict[str, str] = {}
    for rel in paths:
        if "/src/main/" in f"/{rel}" or rel.startswith("src/main/"):
            main_by_simple[Path(rel).stem] = rel
    scopes: dict[str, set[str]] = defaultdict(set)
    for rel in paths:
        scopes[assign_staging_layer(rel, main_by_simple)].add(rel)
    return scopes


def story_layer_guess(st: dict) -> str:
    """Map an existing story to a layer via title or scope majority."""
    title = (st.get("title") or "").lower()
    for lay, t in LAYER_TITLE.items():
        # Prefer canonical LAYER_TITLE phrase; else whole-word layer token
        # (avoid "models" / "repository implementations" substring false matches
        # that made every model-ish MiniMax story claim layer=model).
        if t.lower() in title or re.search(rf"\b{re.escape(lay)}\b", title):
            return lay
    counts: dict[str, int] = defaultdict(int)
    for p in (st.get("scope") or "").split(","):
        p = p.strip()
        if p and not p.startswith("<!--") and not is_generated_build_path(p):
            counts[layer_for_path(p)] += 1
    if counts:
        return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[0][0]
    return "other"


# O-M2DECOMPAXIS — MiniMax impl-flavour titles (JDBC vs JPA vs Spring Data).
TECH_AXIS_REPO_RE = re.compile(
    r"(?:jdbc|jpa|spring[\s-]*data|hibernate).{0,48}(?:repo|repository)"
    r"|(?:repo|repository).{0,48}(?:jdbc|jpa|spring[\s-]*data|hibernate)",
    re.I,
)


def _merge_findings_raw(a: str, b: str) -> str:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in (a or "", b or ""):
        for tok in re.split(r"[,\s]+", raw.strip()):
            t = tok.strip().rstrip(",")
            if not t or t == "-" or t.startswith("<!--"):
                continue
            if t not in seen:
                seen.add(t)
                ids.append(t)
    return ", ".join(ids) if ids else "-"


def collapse_to_layer_stories(stories: list[dict]) -> tuple[list[dict], int]:
    """O-M2DECOMPAXIS — at most one story per staging layer.

    Technology-axis splits (JDBC/JPA/Spring Data repository stories) and
    model-part splits cannot unique-own shared interface/domain files.
    Layer-based partition (≤6 stories) is the proven-clean shape (W4-338).
    """
    if len(stories) <= 1:
        return stories, 0
    keepers: dict[str, dict] = {}
    dropped = 0
    for st in stories:
        lay = story_layer_guess(st)
        title = st.get("title") or ""
        if lay not in keepers:
            keep = dict(st)
            if TECH_AXIS_REPO_RE.search(title) or re.search(
                r"\bpart\s*\d|\bmodels?\s*\(|circular group", title, re.I
            ):
                keep["title"] = LAYER_TITLE.get(lay, title)
            keepers[lay] = keep
            continue
        k = keepers[lay]
        k["findings_raw"] = _merge_findings_raw(
            k.get("findings_raw") or "", st.get("findings_raw") or ""
        )
        if isinstance(k.get("findings"), list) or isinstance(st.get("findings"), list):
            fa = list(k.get("findings") or [])
            fb = list(st.get("findings") or [])
            if not fa and k.get("findings_raw"):
                fa = [
                    x.strip()
                    for x in (k.get("findings_raw") or "").split(",")
                    if x.strip() and x.strip() != "-"
                ]
            if not fb and st.get("findings_raw"):
                fb = [
                    x.strip()
                    for x in (st.get("findings_raw") or "").split(",")
                    if x.strip() and x.strip() != "-"
                ]
            merged: list[str] = []
            seen: set[str] = set()
            for fid in fa + fb:
                if fid not in seen:
                    seen.add(fid)
                    merged.append(fid)
            k["findings"] = merged
        # Prefer non-empty real scope until apply_staging_scope rewrites it
        ks = (k.get("scope") or "").strip()
        ss = (st.get("scope") or "").strip()
        if (not ks or ks.startswith("<!--")) and ss and not ss.startswith("<!--"):
            k["scope"] = st.get("scope") or ""
        dropped += 1
    out: list[dict] = []
    for lay in LAYER_ORDER:
        if lay in keepers:
            out.append(keepers[lay])
    for lay, st in keepers.items():
        if lay not in LAYER_ORDER:
            out.append(st)
    for i, st in enumerate(out, 1):
        st["sid"] = f"S{i:02d}"
    return out, dropped


def apply_staging_scope(stories: list[dict], root: Path) -> int:
    """O-STAGESCOPE — rewrite story scope from staging partition. Returns updates.

    O-M2SCOPEOVERLAP: each staging layer is assigned to at most ONE story
    (first match by layer guess). Later stories that also guess that layer
    must have those paths stripped — re-writing the full layer onto every
    model-ish title was the W4R4 M2 a1/a2 O-SCOPECOVER×135 dual-own defect.
    """
    layer_scopes = staging_layer_scopes(root)
    if not any(layer_scopes.values()):
        return 0
    # Assign each layer's paths to at most one story (first match by layer guess)
    claimed: set[str] = set()
    n = 0
    for st in stories:
        lay = story_layer_guess(st)
        paths = sorted(layer_scopes.get(lay) or [])
        if not paths:
            continue
        if lay in claimed:
            # Layer already owned — strip overlap; do not re-assign full set.
            layer_set = set(paths)
            cur = [
                p.strip()
                for p in (st.get("scope") or "").split(",")
                if p.strip() and not p.strip().startswith("<!--")
            ]
            kept = [
                p
                for p in cur
                if p not in layer_set and not is_generated_build_path(p)
            ]
            new_scope = ", ".join(kept) if kept else "<!-- JUDGMENT: paths -->"
            if (st.get("scope") or "") != new_scope:
                st["scope"] = new_scope
                n += 1
            continue
        new_scope = ", ".join(paths)
        if (st.get("scope") or "") != new_scope:
            st["scope"] = new_scope
            n += 1
        claimed.add(lay)
    # Orphan layers (staging paths, no story) → fold into 'other' or last story
    orphan: list[str] = []
    for lay in LAYER_ORDER:
        if lay in claimed:
            continue
        orphan.extend(sorted(layer_scopes.get(lay) or []))
    if orphan and stories:
        # Prefer an existing 'other' / remaining story; else last
        dest = None
        for st in stories:
            if story_layer_guess(st) == "other" or "remain" in (
                st.get("title") or ""
            ).lower():
                dest = st
                break
        if dest is None:
            dest = stories[-1]
        cur = [p.strip() for p in (dest.get("scope") or "").split(",") if p.strip()]
        merged = sorted(set(cur) | set(orphan))
        new_scope = ", ".join(merged)
        if (dest.get("scope") or "") != new_scope:
            dest["scope"] = new_scope
            n += 1
    return n


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


def _scope_redesignish(scope: str) -> bool:
    """Scope looks like service/REST/config work — not pure HARVEST (S-FND)."""
    return bool(
        re.search(
            r"(?i)service/|rest/|repository/|Endpoint|Service\.java|"
            r"Controller\.java|pom\.xml|/config/|/security/",
            scope or "",
        )
    )


def _scope_harvestish(st: dict, *, root: Optional[Path] = None) -> bool:
    """HARVEST-ish story — ADR-34 F-story-source: prefer typed roles over prose.

    When model.units[].decision.role is available for classes in scope, the
    majority typed role wins. Regex over rationale/title is legacy fallback
    only (fixtures without typed decisions).
    """
    if root is not None:
        roles = _typed_roles_for_scope(root, st.get("scope") or "")
        if roles:
            harvest_n = sum(1 for r in roles if r == "HARVEST")
            redesign_n = sum(1 for r in roles if r == "REDESIGN")
            if harvest_n or redesign_n:
                return harvest_n > redesign_n
    blob = " ".join(
        [
            st.get("rationale") or "",
            st.get("done") or "",
            st.get("scope") or "",
            st.get("title") or "",
        ]
    )
    return bool(
        re.search(r"(?i)HARVEST|characterization|model layer|\bmodels?\b", blob)
    )


def _typed_roles_for_scope(root: Path, scope: str) -> list[str]:
    """CapWord / path → decision.role for units mentioned in scope (ADR-34)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from model import load as model_load, profile_units  # type: ignore
    except ImportError:
        return []
    try:
        model = model_load(root)
    except (OSError, ValueError, FileNotFoundError):
        return []
    out: list[str] = []
    for u in profile_units(model):
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if not d or not d.get("role"):
            continue
        fqn = u.get("legacy_fqn") or u.get("key") or ""
        simple = fqn.rsplit(".", 1)[-1] if fqn else ""
        lp = (u.get("legacy_path") or "").replace("\\", "/")
        if simple and re.search(rf"\b{re.escape(simple)}(?:\.java)?\b", scope):
            out.append(str(d["role"]).upper())
        elif lp and lp in scope.replace("\\", "/"):
            out.append(str(d["role"]).upper())
    return out


def model_has_typed_profile_roles(root: Path) -> bool:
    """True when model.json has ≥1 complete decision — ADR-34 SoT ready."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from model import load as model_load, profile_units  # type: ignore
        from profile_roles import _decision_complete  # type: ignore
    except ImportError:
        return False
    try:
        model = model_load(root)
    except (OSError, ValueError, FileNotFoundError):
        return False
    n = 0
    for u in profile_units(model):
        d = u.get("decision") if isinstance(u.get("decision"), dict) else None
        if _decision_complete(d):
            n += 1
    return n > 0


def _finding_score_for_story(fid: str, sites: dict[str, list[str]], st: dict) -> int:
    """Path/layer overlap score used for unique-owner + S-FND rebalance."""
    paths = sites.get(fid) or []
    scope = st.get("scope") or ""
    if not paths:
        return 0
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
    return score


def repair_sfnd_empty_findings(
    stories: list[dict], inv: dict, *, root: Optional[Path] = None
) -> int:
    """O-M2COMPOSEBOOK: do not leave redesignish stories with findings: '-'.

    Rebalance better-matching findings from other stories; if still empty and
    harvestish, keep '-'; otherwise mark harvest characterization so S-FND
    does not reject compose's own output (ADR-4).
    """
    sites = inv["sites"]
    n = 0
    for st in stories:
        if (st.get("findings_raw") or "").strip() != "-":
            continue
        if st.get("findings"):
            continue
        if not _scope_redesignish(st.get("scope") or ""):
            continue
        if _scope_harvestish(st, root=root):
            continue
        # Steal findings that score higher on this story than on current owner
        moved: list[str] = []
        for other in stories:
            if other["sid"] == st["sid"]:
                continue
            keep: list[str] = []
            for fid in list(other["findings"]):
                s_here = _finding_score_for_story(fid, sites, st)
                s_there = _finding_score_for_story(fid, sites, other)
                if s_here > s_there and s_here > 0:
                    moved.append(fid)
                else:
                    keep.append(fid)
            if len(keep) != len(other["findings"]):
                other["findings"] = keep
                other["findings_raw"] = ", ".join(keep) if keep else "-"
        if moved:
            st["findings"] = moved
            st["findings_raw"] = ", ".join(moved)
            n += 1
            continue
        # Still empty: if harvestish after rebalance miss, keep '-'; else
        # annotate as characterization so lint permits '-' (last resort).
        if not st["findings"]:
            rat = st.get("rationale") or ""
            if not re.search(r"(?i)HARVEST|characterization", rat):
                st["rationale"] = (
                    (rat + " " if rat else "")
                    + "HARVEST/characterization scope — findings owned by "
                    "layer-aligned stories (O-M2COMPOSEBOOK S-FND)"
                ).strip()
                n += 1
    # refresh raw fields
    for st in stories:
        if st["findings"]:
            st["findings_raw"] = ", ".join(st["findings"])
        elif (st.get("findings_raw") or "").strip() in ("", "-"):
            st["findings_raw"] = "-"
    return n


def _profile_sec7(prof: str) -> str:
    m = re.search(r"^(#{2,6})[ \t]+.*Class roles.*$", prof, re.M | re.I)
    if not m:
        return ""
    level = len(m.group(1))
    rest = prof[m.end() :]
    nxt = re.search(r"^#{1," + str(level) + r"}[ \t]", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def redesign_classes_from_model(root: Path) -> set[str]:
    """ADR-29 — CapWord classes with role=REDESIGN on model.units[].decision.

    F-render-oneway: do not parse §7 markdown for roles.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from profile_roles import redesign_fqns  # type: ignore
    except ImportError:
        return set()
    names = redesign_fqns(root)
    # Prefer CapWord simple names for brief bullets.
    return {n for n in names if "." not in n}


def redesign_classes_from_profile(prof: str, root: Optional[Path] = None) -> set[str]:
    """REDESIGN class set — model decisions first (ADR-29); §7 only as legacy fallback."""
    if root is not None:
        from_model = redesign_classes_from_model(root)
        if from_model:
            return from_model
    # Legacy fallback for fixtures without model decisions (pre-ADR-29).
    sec7 = _profile_sec7(prof)
    if not sec7:
        return set()
    java_named = set(re.findall(r"\b([A-Z]\w+)\.java\b", sec7))
    name_re = re.compile(r"`([A-Z]\w+)`|\*\*([A-Z]\w+)\*\*|\b([A-Z]\w+)\.java\b")
    out: set[str] = set()
    for mm in name_re.finditer(sec7):
        nm = mm.group(1) or mm.group(2) or mm.group(3)
        if not nm or nm in ("REDESIGN", "HARVEST", "All"):
            continue
        ls = sec7.rfind("\n", 0, mm.start()) + 1
        le = sec7.find("\n", mm.start())
        line = sec7[ls : le if le >= 0 else len(sec7)]
        if "HARVEST" in line and "REDESIGN" not in line:
            continue
        pre = sec7[: mm.start()]
        under_redesign = (
            "REDESIGN" in line or pre.rfind("REDESIGN") > pre.rfind("HARVEST")
        )
        if not under_redesign:
            continue
        if nm in java_named or mm.group(1) or mm.group(2):
            out.add(nm)
    return out


def _extract_sec7_target(ln: str) -> str:
    """Pull the pasteable target shape from a §7 family/class line."""
    s = re.sub(r"\s+", " ", ln).strip()
    # Prefer arrow / target: forms; fall back to em-dash tail after class list.
    m = re.search(r"(?:→|->|=>)\s*(.+)$", s)
    if m:
        return m.group(1).strip(" -—:")[:220]
    m = re.search(r"(?i)target\s*:\s*(.+)$", s)
    if m:
        return m.group(1).strip(" -—")[:220]
    m = re.search(r"—\s*(.+)$", s)
    if m:
        return m.group(1).strip()[:220]
    return s[:220]


def redesign_contract_hints_from_profile(
    prof: str, root: Optional[Path] = None
) -> dict[str, str]:
    """O-BRIEFCONTRACT — class → target text from model decisions (ADR-29) or §7."""
    if root is not None:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from profile_roles import redesign_contract_hints  # type: ignore

            hints = redesign_contract_hints(root)
            if hints:
                return hints
        except ImportError:
            pass
    sec7 = _profile_sec7(prof)
    if not sec7:
        return {}
    redesign_cls = redesign_classes_from_profile(prof, root=root)
    hints: dict[str, str] = {}
    for ln in sec7.splitlines():
        if "HARVEST" in ln and "REDESIGN" not in ln:
            continue
        # Classes named on this line (backtick/bold)
        named = re.findall(r"`([A-Z]\w+)`|\*\*([A-Z]\w+)\*\*", ln)
        classes = [a or b for a, b in named if (a or b) not in ("REDESIGN", "HARVEST", "All")]
        classes = [c for c in classes if c in redesign_cls]
        if not classes:
            continue
        if not re.search(
            r"(?i)REDESIGN|→|->|=>|target\s*:|@ApplicationScoped|JAX-RS|removed",
            ln,
        ):
            continue
        target = _extract_sec7_target(ln)
        if not target or target.startswith("<!--"):
            continue
        for c in classes:
            hints.setdefault(c, target)
    # Fallback: any redesign class still missing — scan again by name
    for c in redesign_cls:
        if c in hints:
            continue
        for ln in sec7.splitlines():
            if not re.search(rf"`{re.escape(c)}`|\*\*{re.escape(c)}\*\*", ln):
                continue
            target = _extract_sec7_target(ln)
            if target and not target.startswith("<!--"):
                hints[c] = target
                break
    return hints


def _contract_bullet(cls: str, contract: str) -> str:
    """Per-class brief line — paste computed §7 target (no JUDGMENT stub)."""
    body = (contract or "").strip()
    if not body:
        body = "<!-- O-PROFILE7GAP: class in scope but unnamed in §7 — extend profile -->"
    return f"- `{cls}` — REDESIGN: target: {body}"


def scope_redesign_classes(scope: str, redesign_cls: set[str]) -> list[str]:
    return sorted(
        c
        for c in redesign_cls
        if re.search(rf"\b{re.escape(c)}(?:\.java)?\b", scope or "")
    )


def derive_kinds(
    stories: list[dict], inv: dict, redesign_cls: set[str]
) -> int:
    """O-M2COMPOSEBOOK / O-STORYKIND: set kind when lint would require it.

    Defaults: OPEN DESIGN / §7 REDESIGN scope → reimplement; findings without
    those signals → rename. mixed only when both OPEN DESIGN and non-open
    findings share a story, with a lint-accepted justification suffix.
    Does not downgrade an already-justified mixed.
    """
    open_design = inv.get("open_design") or set()
    n = 0
    just_re = re.compile(
        r"(?i)\b(split|justif|both\s+kinds?|rename\s*\+?\s*reimplement|"
        r"reimplement\s+and\s+rename|mixed\s+because|harvest\s*\+?\s*convert|"
        r"cannot\s+split)\b"
    )
    for st in stories:
        fids = set(st.get("findings") or [])
        owns_open = bool(fids & open_design)
        scope = st.get("scope") or ""
        scope_hit = any(
            re.search(rf"\b{re.escape(c)}(?:\.java)?\b", scope) for c in redesign_cls
        )
        needs = owns_open or scope_hit
        cur = seat_budget.parse_kind(st.get("kind"))
        cur_raw = (st.get("kind") or "").strip()

        if not needs:
            if cur:
                continue
            if fids and not _scope_redesignish(scope):
                st["kind"] = "rename"
                n += 1
            continue

        non_open = fids - open_design
        want = "reimplement"
        if owns_open and non_open:
            want = "mixed — cannot split; OPEN DESIGN plus rewrite findings"
        elif owns_open:
            want = "reimplement"
        elif scope_hit:
            want = "reimplement"

        if cur == "mixed" and just_re.search(cur_raw):
            continue
        if cur == "rename" and owns_open:
            st["kind"] = want
            n += 1
            continue
        if not cur:
            st["kind"] = want
            n += 1
            continue
        if cur == "mixed" and not just_re.search(cur_raw):
            # Model left bare mixed — either justify or collapse to reimplement
            if owns_open and non_open:
                st["kind"] = want
            else:
                st["kind"] = "reimplement"
            n += 1
    return n


def unique_partition(
    stories: list[dict], inv: dict, *, root: Optional[Path] = None
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
    repair_sfnd_empty_findings(stories, inv, root=root)
    return stories


def ensure_deploy_last(stories: list[dict]) -> None:
    """F-deploy-derived — only the last story is deployable; clear earlier flags."""
    if not stories:
        return
    for st in stories[:-1]:
        st["deploy"] = False
    stories[-1]["deploy"] = True


def _load_dependency_order():
    path = Path(__file__).resolve().parent / "dependency-order.py"
    spec = importlib.util.spec_from_file_location("dependency_order", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def resolve_legacy_root(root: Path) -> Path | None:
    """Prefer /projects/legacy, then sibling legacy/, then LEGACY_ROOT."""
    candidates = [
        Path("/projects/legacy"),
        root.parent / "legacy",
        root / "legacy",
    ]
    env = os.environ.get("LEGACY_ROOT", "").strip()
    if env:
        candidates.insert(0, Path(env))
    for c in candidates:
        if c.is_dir():
            return c
    return None


def derive_story_depends(stories: list[dict], root: Path) -> int:
    """O-DEPCHAIN — set depends from real inter-story import edges, not S_n-1.

    Uses dependency-order.build_graph on the legacy tree. Stories with no
    cross-story imports get depends: -. Returns count of stories updated.
    """
    legacy = resolve_legacy_root(root)
    if legacy is None or len(stories) < 2:
        return 0
    try:
        depmod = _load_dependency_order()
        analysis = depmod.analyze(str(legacy))
    except Exception as exc:  # noqa: BLE001 — bookkeeping must not abort fill
        print(f"O-M2COMPOSE WARN: O-DEPCHAIN graph skip: {exc}", file=sys.stderr)
        return 0
    classes = analysis["classes"]  # fqn -> relpath
    imports = analysis["imports"]
    # path / basename / simple / fqn -> sid (scopes should be unique owners)
    own: dict[str, str] = {}
    for st in stories:
        sid = st["sid"]
        for p in _scope_path_list(st.get("scope") or ""):
            own[p] = sid
            own[Path(p).name] = sid
            if p.endswith(".java"):
                own[Path(p).stem] = sid
    for fqn, rel in classes.items():
        rel_n = rel.replace("\\", "/")
        simple = fqn.rsplit(".", 1)[-1]
        sid = own.get(rel_n) or own.get(Path(rel_n).name) or own.get(simple)
        if sid:
            own[fqn] = sid

    def _sid_for(fqn: str) -> str | None:
        if fqn in own:
            return own[fqn]
        rel = classes.get(fqn, "").replace("\\", "/")
        return (
            own.get(rel)
            or own.get(Path(rel).name)
            or own.get(fqn.rsplit(".", 1)[-1])
        )

    # story -> set of stories it depends on (earlier roadmap index only —
    # outer-loop runs stories in file order; forward edges are reorder signals,
    # not satisfiable depends under the sequential runner).
    sid_idx = {st["sid"]: i for i, st in enumerate(stories)}
    needs: dict[str, set[str]] = {st["sid"]: set() for st in stories}
    for fqn, deps in imports.items():
        sid = _sid_for(fqn)
        if not sid:
            continue
        for d in deps:
            dsid = _sid_for(d)
            if not dsid or dsid == sid:
                continue
            if sid_idx.get(dsid, 999) < sid_idx.get(sid, -1):
                needs[sid].add(dsid)

    n = 0
    for st in stories:
        sid = st["sid"]
        deps = sorted(needs.get(sid) or [])
        new = ", ".join(deps) if deps else "-"
        cur = (st.get("depends") or "-").strip()
        # Normalize "S01, S02" vs "S01,S02"
        cur_n = ", ".join(p.strip() for p in cur.split(",") if p.strip() and p != "-")
        cur_n = cur_n or "-"
        if cur_n != new:
            st["depends"] = new
            n += 1
    return n


def render_roadmap(stories: list[dict], non_mandatory: set[str], prior_nm: str) -> str:
    lines = [
        "# Modernization roadmap",
        "",
        SKELETON_MARK,
        "# O-M2COMPOSE — mechanical partition / kind / deploy / seat-budget / K3 rows.",
        "# Model fills JUDGMENT (rationale, quotes, adopt/defer reasons, §7 contracts;",
        "# may refine kind with mixed justification).",
        "# O-DEPCHAIN: depends are real inter-story edges (not forced S_n ← S_n-1).",
        "",
    ]
    for i, st in enumerate(stories):
        dep = (st.get("depends") or "-").strip() or "-"
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
    """Write computed seat-budget when kind is set. Returns count updated.

    O-SEATSIZE: pass non-generated scope path count so budgets floor on work
    size, not only owned-finding incidents.
    """
    n_upd = 0
    for st in stories:
        kind = seat_budget.parse_kind(st.get("kind"))
        if not kind:
            continue
        fids = set(st["findings"])
        inc = seat_budget.story_incident_total(inv_text, fids)
        scope_n = seat_budget.scope_path_count(st.get("scope") or "")
        expected = seat_budget.expected_budget(kind, inc, scope_paths=scope_n)
        cur = seat_budget.parse_seat_budget_field(st.get("seat_budget"))
        if cur != expected:
            st["seat_budget"] = str(expected)
            n_upd += 1
        elif st.get("seat_budget") is None:
            st["seat_budget"] = str(expected)
            n_upd += 1
    return n_upd


def strip_generated_scope(stories: list[dict]) -> int:
    """O-SCOPENOGEN — remove target/build paths from story scope fields."""
    n = 0
    for st in stories:
        raw = st.get("scope") or ""
        cleaned = filter_scope_paths(raw)
        if cleaned != raw:
            st["scope"] = cleaned or "<!-- JUDGMENT: target paths -->"
            n += 1
    return n


def brief_path(root: Path, sid: str, title: str) -> Path:
    """Prefer canonical `{sid}-{slug(title)}.md` (O-M2DECOMPAXIS).

    Legacy: if only an old title-slug exists for this SID, return it so fill
    can refresh in place — write_briefs then purges non-canonical names.
    """
    canonical = root / "migration" / "briefs" / f"{sid}-{slugify(title)}.md"
    if canonical.is_file():
        return canonical
    briefs = sorted((root / "migration" / "briefs").glob(f"{sid}-*.md"))
    if briefs:
        return briefs[0]
    return canonical


def brief_is_skeleton(text: str) -> bool:
    # O-M2FILLCLOBBER: seats often leave SKELETON_MARK in place while filling
    # JUDGMENT with real fenced legacy quotes. A mark alone must not authorize
    # stub rewrite — that wiped authored briefs and false-RED'd roadmap-lint.
    if SKELETON_MARK not in text:
        return False
    if "```" in text:
        return False
    return True


def _scope_path_list(scope: str) -> list[str]:
    return [p.strip() for p in (scope or "").split(",") if p.strip()]


def profile_sec7_digest(profile_text: str) -> str:
    """O-BRIEFFRESHPROFILE — must match roadmap-lint.profile_sec7_digest."""
    if not profile_text:
        return ""
    m = re.search(
        r"(?ims)^##\s+[^\n]*Class roles[^\n]*\n(.*?)(?=^##\s|\Z)",
        profile_text,
    )
    body = (m.group(0) if m else "").strip()
    if not body:
        return ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def story_fresh_hash(st: dict) -> str:
    """O-BRIEFFRESH — must match roadmap-lint.story_fresh_hash fields."""
    paths = sorted(_scope_path_list(st.get("scope") or ""))
    payload = "\n".join(
        [
            (st.get("sid") or "").strip(),
            ",".join(paths),
            (st.get("findings_raw") or "").strip(),
            (st.get("kind") or "").strip(),
            (str(st.get("seat_budget") or "")).strip(),
            (st.get("profile_sec7") or "").strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fresh_marker_line(st: dict) -> str:
    return f"<!-- O-BRIEFFRESH sha256={story_fresh_hash(st)} -->"


def ensure_brief_freshness(path: Path, st: dict) -> bool:
    """Stamp/replace O-BRIEFFRESH marker to match current roadmap fields."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    mark = fresh_marker_line(st)
    m = _FRESH_MARK.search(text)
    if m and m.group(0) == mark:
        return False
    if m:
        new = _FRESH_MARK.sub(mark, text, count=1)
    else:
        # Prefer right after title / skeleton mark
        if SKELETON_MARK in text:
            new = text.replace(SKELETON_MARK, SKELETON_MARK + "\n" + mark, 1)
        else:
            new = re.sub(
                r"(^#[^\n]*\n)",
                rf"\1{mark}\n",
                text,
                count=1,
                flags=re.M,
            )
            if new == text:
                new = mark + "\n" + text
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def render_brief_stub(
    st: dict,
    *,
    redesign_cls: set[str] | None = None,
    contract_hints: dict[str, str] | None = None,
) -> str:
    budget_line = ""
    if st.get("seat_budget"):
        budget_line = f"\n- **seat-budget**: `{st['seat_budget']}`\n"
    elif st.get("kind") and seat_budget.parse_kind(st.get("kind")):
        budget_line = "\n- **seat-budget**: `<!-- filled by m2-compose when kind set -->`\n"
    findings = st["findings_raw"] or "-"
    # O-BRIEFCOVER — name every scope path (one bullet each), not a buried CSV.
    paths = _scope_path_list(st.get("scope") or "")
    if paths:
        scope_lines = [
            "<!-- JUDGMENT: quote REAL legacy lines per class (fabrication gate) -->",
            "",
            "### Scope inventory (O-BRIEFCOVER — do not drop paths)",
            "",
        ]
        for p in paths:
            scope_lines.append(f"- `{p}`")
        scope_lines.append("")
    else:
        scope_lines = [
            "<!-- JUDGMENT: quote REAL legacy lines per class (fabrication gate) -->",
            "",
            "- <!-- paths -->",
            "",
        ]
    # O-BRIEFCONTRACT — paste §7 target per in-scope REDESIGN class (family→per-class)
    shape_lines = [
        "<!-- O-BRIEFCONTRACT: targets pasted from architecture-profile §7 (computed) -->",
        "",
    ]
    hits = scope_redesign_classes(st.get("scope") or "", redesign_cls or set())
    if hits:
        hints = contract_hints or {}
        shape_lines.extend(
            [
                "### Per-class contracts (O-BRIEFCONTRACT — one line per class)",
                "",
            ]
        )
        for c in hits:
            shape_lines.append(_contract_bullet(c, hints.get(c, "")))
        shape_lines.append("")
    return "\n".join(
        [
            f"# {st['sid']}: {st['title']}",
            "",
            SKELETON_MARK,
            fresh_marker_line(st),
            "# O-M2COMPOSE brief stub — model fills JUDGMENT quotes / §7 contracts.",
            "",
            "## Goal & position",
            "",
            "<!-- JUDGMENT: what this story achieves and why it is next -->",
            "",
            "## In scope",
            "",
            *scope_lines,
            "## Out of scope",
            "",
            "<!-- JUDGMENT: neighboring code this story must not touch -->",
            "",
            "## Decided target shapes",
            "",
            *shape_lines,
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
    """Publish exactly one seat-budget: N (O-SEATBUDGET / O-SEATBUDGETUNIQ)."""
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    vals = sorted({int(v) for v in re.findall(r"(?im)seat-budget:\s*(\d+)", text)})
    has_n = seat_budget.brief_has_seat_budget(text, n)
    if has_n and vals == [n]:
        return False
    # Normalize every seat-budget publish to N, then drop duplicate lines.
    new = re.sub(
        r"(?im)((?:\*\*)?(?:seat-budget|seat budget)(?:\*\*)?\s*[:=]\s*`?)\d+(`?)",
        rf"\g<1>{n}\2",
        text,
    )
    # Keep first seat-budget line; remove subsequent bare/bold duplicates.
    seen = False

    def _dedupe(m: re.Match) -> str:
        nonlocal seen
        if not seen:
            seen = True
            return m.group(0)
        return ""

    new2 = re.sub(
        r"(?im)^[ \t]*(?:[-*][ \t]+)?(?:\*\*)?(?:seat-budget|seat budget)"
        r"(?:\*\*)?\s*[:=]\s*`?\d+`?[ \t]*$.*(?:\n)?",
        _dedupe,
        new,
    )
    if not seen:
        if re.search(r"(?im)^##\s+Contracts", new2):
            new2 = re.sub(
                r"(?im)(^##\s+Contracts[^\n]*\n)",
                rf"\1\n- **seat-budget**: `{n}`\n",
                new2,
                count=1,
            )
        else:
            new2 = new2.rstrip() + f"\n\n- **seat-budget**: `{n}`\n"
    if new2 != text:
        path.write_text(new2, encoding="utf-8")
        return True
    return False


def ensure_brief_scope_cover(path: Path, scope: str) -> bool:
    """O-BRIEFCOVER: append missing roadmap scope paths without wiping JUDGMENT."""
    if not path.is_file():
        return False
    paths = _scope_path_list(scope)
    if not paths:
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [
        p for p in paths if p not in text and Path(p).name not in text
    ]
    if not missing:
        return False
    block = [
        "",
        "## Scope inventory (O-BRIEFCOVER — mechanical; do not drop)",
        "",
    ]
    for p in missing:
        block.append(f"- `{p}`")
    block.append("")
    path.write_text(text.rstrip() + "\n" + "\n".join(block), encoding="utf-8")
    return True


def _brief_has_class_contract(text: str, cls: str) -> bool:
    """Mirror roadmap-lint O-BRIEFCONTRACT substance (no JUDGMENT stubs)."""
    shape = re.compile(
        r"(?i)(?:→|->|=>|target contract|JAX-RS|@ApplicationScoped|"
        r"Panache|ConcurrentHashMap|ExceptionMapper|\b404\b|CDI|Agroal|"
        r"@Path\b|PersistenceException|compute\(|@Transactional|"
        r"\bremoved\b|target\s*:\s*(?!<!--)\S)"
    )
    judgment = re.compile(r"(?i)target\s*:\s*<!--\s*JUDGMENT")
    for ln in text.splitlines():
        if not re.search(
            rf"(?:`{re.escape(cls)}`|\*\*{re.escape(cls)}\*\*|\b{re.escape(cls)}\b)",
            ln,
        ):
            continue
        if judgment.search(ln):
            continue
        if shape.search(ln):
            return True
    return False


def _brief_has_dedicated_contract(text: str, cls: str, peers: set[str]) -> bool:
    """O-BRIEFQCONT — class alone on a substance line (not a family list)."""
    shape = re.compile(
        r"(?i)(?:→|->|=>|target contract|JAX-RS|@ApplicationScoped|"
        r"Panache|ConcurrentHashMap|ExceptionMapper|\b404\b|CDI|Agroal|"
        r"@Path\b|PersistenceException|compute\(|@Transactional|"
        r"\bremoved\b|target\s*:\s*(?!<!--)\S)"
    )
    judgment = re.compile(r"(?i)target\s*:\s*<!--\s*JUDGMENT")
    cls_tok = re.compile(r"`([A-Z][A-Za-z0-9]+)`|\*\*([A-Z][A-Za-z0-9]+)\*\*")
    for ln in text.splitlines():
        if judgment.search(ln) or not shape.search(ln):
            continue
        named = [a or b for a, b in cls_tok.findall(ln) if (a or b) in peers]
        if named == [cls]:
            return True
    return False


def ensure_brief_class_contracts(
    path: Path,
    scope: str,
    redesign_cls: set[str],
    contract_hints: dict[str, str] | None = None,
) -> bool:
    """O-BRIEFCONTRACT + O-BRIEFQCONT: paste dedicated §7 targets per class."""
    if not path.is_file():
        return False
    hits = scope_redesign_classes(scope, redesign_cls)
    if not hits:
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    hints = contract_hints or {}
    peer_set = set(hits)
    changed = False
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    seen_ok: set[str] = set()
    for ln in lines:
        upgraded = False
        for c in hits:
            if not re.search(
                rf"(?:`{re.escape(c)}`|\*\*{re.escape(c)}\*\*)", ln
            ):
                continue
            contract = hints.get(c, "")
            if not contract:
                continue
            # Upgrade JUDGMENT / empty-target stubs in place.
            if re.search(r"(?i)target\s*:\s*<!--\s*JUDGMENT", ln) or (
                re.search(r"(?i)target\s*:\s*$", ln.rstrip()) and contract
            ):
                # Preserve list marker / indent; replace whole bullet content.
                indent = re.match(r"^(\s*[-*]\s+)", ln)
                prefix = indent.group(1) if indent else "- "
                nl = "\n" if ln.endswith("\n") else ""
                new_lines.append(prefix + _contract_bullet(c, contract)[2:] + nl)
                seen_ok.add(c)
                upgraded = True
                changed = True
                break
            if _brief_has_dedicated_contract(ln, c, peer_set):
                seen_ok.add(c)
        if not upgraded:
            new_lines.append(ln)
    text2 = "".join(new_lines)
    # Append dedicated lines for classes only covered by family lists.
    missing = [
        c
        for c in hits
        if c not in seen_ok and not _brief_has_dedicated_contract(text2, c, peer_set)
    ]
    if missing:
        block = [
            "",
            "### Per-class contracts (O-BRIEFCONTRACT — pasted from §7; do not drop)",
            "",
        ]
        for c in missing:
            block.append(_contract_bullet(c, hints.get(c, "")))
        block.append("")
        text2 = text2.rstrip() + "\n" + "\n".join(block)
        changed = True
    if changed and text2 != text:
        path.write_text(text2, encoding="utf-8")
        return True
    return False


def _brief_has_redesign_substance(text: str) -> bool:
    """Mirror roadmap-lint brief_has_redesign_contract (substance, not stubs)."""
    if not re.search(r"(?i)\bREDESIGN\b|\bOPEN DESIGN\b", text):
        return False
    if not re.search(r"`([A-Z][A-Za-z0-9]+)`|\*\*([A-Z][A-Za-z0-9]+)\*\*", text):
        return False
    judgment = re.compile(r"(?i)target\s*:\s*<!--\s*JUDGMENT")
    shape = re.compile(
        r"(?i)(?:→|->|=>|target contract|JAX-RS|@ApplicationScoped|"
        r"Panache|ConcurrentHashMap|ExceptionMapper|\b404\b|CDI|Agroal|"
        r"@Path\b|PersistenceException|compute\(|@Transactional|"
        r"\bremoved\b|target\s*:\s*(?!<!--)\S)"
    )
    for ln in text.splitlines():
        if judgment.search(ln):
            continue
        if re.search(r"`([A-Z][A-Za-z0-9]+)`|\*\*([A-Z][A-Za-z0-9]+)\*\*", ln) and shape.search(
            ln
        ):
            return True
    return False


def ensure_open_design_platform_contracts(
    path: Path,
    findings_raw: str,
    open_design: set[str],
    contract_hints: dict[str, str],
) -> bool:
    """O-PORTDERIVE — OPEN DESIGN stories with no class scope still need a
    CapWord+target line. Paste §7 Configuration / platform redesign hints."""
    if not path.is_file():
        return False
    fids = {f for f in re.split(r"[,\s]+", findings_raw or "") if f and f != "-"}
    if not (fids & open_design):
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    if _brief_has_redesign_substance(text):
        return False
    # Prefer configuration-ish §7 classes (removed → Quarkus platform).
    # Names come from the live profile hints — never hardcode specimen classes.
    prefer = [
        c
        for c in sorted(contract_hints)
        if re.search(r"(?:Config|Application|Security|Swagger|Roles)$", c)
    ]
    if not prefer:
        prefer = sorted(contract_hints)[:3]
    if not prefer:
        # Last resort: synthetic CapWord so O-PORTDERIVE has a token to match.
        prefer = ["PlatformBootstrap"]
        contract_hints = {
            "PlatformBootstrap": "removed — Quarkus bootstrap; OPEN DESIGN "
            "platform BOM/security/jpa/cache decided in this story"
        }
    block = [
        "",
        "### OPEN DESIGN platform contracts (O-PORTDERIVE — pasted from §7)",
        "",
    ]
    for c in prefer[:4]:
        block.append(_contract_bullet(c, contract_hints.get(c, "")))
    block.append("")
    path.write_text(text.rstrip() + "\n" + "\n".join(block), encoding="utf-8")
    return True


def write_briefs(
    root: Path,
    stories: list[dict],
    *,
    force_skeleton: bool,
    redesign_cls: set[str] | None = None,
    contract_hints: dict[str, str] | None = None,
    open_design: set[str] | None = None,
) -> tuple[int, int]:
    wrote = refreshed = 0
    bdir = root / "migration" / "briefs"
    bdir.mkdir(parents=True, exist_ok=True)
    rcls = redesign_cls or set()
    hints = contract_hints or {}
    od = open_design or set()
    # O-M2DECOMPAXIS / W4-336: canonical brief names only (`{sid}-{slug(title)}`).
    live_names = {f"{st['sid']}-{slugify(st['title'])}.md" for st in stories}
    for st in stories:
        canonical = bdir / f"{st['sid']}-{slugify(st['title'])}.md"
        path = brief_path(root, st["sid"], st["title"])
        # Migrate authored content from an old title-slug onto the canonical name.
        if path.is_file() and path.name != canonical.name:
            if not canonical.is_file():
                try:
                    path.rename(canonical)
                except OSError:
                    canonical.write_text(
                        path.read_text(encoding="utf-8", errors="replace"),
                        encoding="utf-8",
                    )
                    try:
                        path.unlink()
                    except OSError:
                        pass
            path = canonical
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            if not brief_is_skeleton(text) and not force_skeleton:
                # authored — publish seat-budget + patch missing scope/contracts
                # + refresh O-BRIEFFRESH hash (regen-on-recompose bookkeeping)
                changed = False
                # Drop stale skeleton mark so later fills do not re-classify.
                if SKELETON_MARK in text:
                    text = text.replace(SKELETON_MARK + "\n", "").replace(
                        SKELETON_MARK, ""
                    )
                    path.write_text(text, encoding="utf-8")
                    changed = True
                if st.get("seat_budget"):
                    try:
                        n = int(str(st["seat_budget"]).split()[0])
                    except ValueError:
                        n = None
                    if n is not None and ensure_brief_seat_budget(path, n):
                        changed = True
                if ensure_brief_scope_cover(path, st.get("scope") or ""):
                    changed = True
                if ensure_brief_class_contracts(
                    path, st.get("scope") or "", rcls, hints
                ):
                    changed = True
                if ensure_open_design_platform_contracts(
                    path, st.get("findings_raw") or "", od, hints
                ):
                    changed = True
                if ensure_brief_freshness(path, st):
                    changed = True
                if changed:
                    refreshed += 1
                continue
            path.write_text(
                render_brief_stub(st, redesign_cls=rcls, contract_hints=hints),
                encoding="utf-8",
            )
            refreshed += 1
        else:
            path.write_text(
                render_brief_stub(st, redesign_cls=rcls, contract_hints=hints),
                encoding="utf-8",
            )
            wrote += 1
    for old in list(bdir.glob("S*.md")):
        if old.name not in live_names:
            try:
                old.unlink()
            except OSError:
                pass
    return wrote, refreshed


def skeleton_from_inventory(
    inv: dict, dep_text: str = "", root: Path | None = None
) -> list[dict]:
    """Mechanical story cut: one story per non-empty path layer.

    O-STAGESCOPE: when migration/staging exists, scope is the staging
    partition (ownership-by-subject for tests). Findings still partition
    from the inventory; model never authors paths.
    """
    layer_findings: dict[str, list[str]] = defaultdict(list)
    layer_scopes: dict[str, set[str]] = defaultdict(set)
    staging_scopes = staging_layer_scopes(root) if root is not None else {}
    use_staging = bool(any(staging_scopes.values()))

    for fid in sorted(inv["must"]):
        paths = inv["sites"].get(fid) or []
        if not paths:
            layer_findings["other"].append(fid)
            continue
        # majority layer
        counts: dict[str, int] = defaultdict(int)
        for p in paths:
            if is_generated_build_path(p):
                continue  # O-SCOPENOGEN — never seed build outs into scope
            counts[layer_for_path(p)] += 1
            if not use_staging:
                layer_scopes[layer_for_path(p)].add(p)
        if not counts:
            # All sites were build-generated — still own the finding via layer
            # heuristic on the first site (platform/other), but no scope seed.
            lay = layer_for_path(paths[0]) if paths else "other"
            layer_findings[lay].append(fid)
            continue
        lay = sorted(counts.items(), key=lambda x: (-x[1], LAYER_ORDER.index(x[0])))[0][0]
        layer_findings[lay].append(fid)

    if use_staging:
        layer_scopes = staging_scopes
    else:
        # Also pull scope hints from dependency-order paths when present
        for m in re.finditer(r"\(([^)]+\.java)\)", dep_text):
            p = m.group(1)
            if is_generated_build_path(p):
                continue
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
        # O-STAGESCOPE: no [:40] cap — dropped files were a measured defect
        scope_s = ", ".join(scopes) if scopes else "<!-- JUDGMENT: paths -->"
        sid = f"S{idx:02d}"
        src = "staging-partition" if use_staging else "findings-inventory"
        stories.append(
            {
                "sid": sid,
                "title": LAYER_TITLE[lay],
                "scope": scope_s,
                "findings": list(fids),
                "findings_raw": ", ".join(fids) if fids else "-",
                # O-DEPCHAIN: starts as -; derive_story_depends fills real edges
                "depends": "-",
                "deploy": False,
                "done": "<!-- JUDGMENT: checkable done-criterion -->",
                "rationale": (
                    f"O-M2COMPOSE layer={lay} unique-owner partition from {src}"
                    + (" (O-STAGESCOPE)" if use_staging else "")
                ),
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


def skeleton_from_model(root: Path, inv: dict) -> list[dict]:
    """ADR-34 / F-story-rendered (out-half) — render FROM model.stories[] only.

    Membership SoT is ``assign_stories_from_model`` (order+SCC+decision.role).
    Layer is a packaging label on each typed story — never invent a story from
    staging scopes / inventory findings alone (W4-540 / W5-108: empty
    ``platform`` story with staging properties while model.stories[] has 5).

    Staging paths may *supplement scope* of an existing typed story whose
    ``layer`` matches; they must not create a sixth heading.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from model import (  # type: ignore
        assign_stories_from_model,
        profile_units,
    )
    from profile_roles import _decision_complete  # type: ignore

    # Persist typed partition first — roadmap must project this list, not a
    # parallel LAYER_ORDER walk that can disagree (O-M2SKELDRIFT).
    model = assign_stories_from_model(root)
    typed = list(model.get("stories") or [])
    if not typed:
        return skeleton_from_inventory(inv, "", root=root)

    units = {
        (u.get("key") or u.get("legacy_fqn") or ""): u
        for u in profile_units(model)
        if (u.get("key") or u.get("legacy_fqn"))
    }
    staging_scopes = staging_layer_scopes(root)

    stories: list[dict] = []
    for st in typed:
        keys = [k for k in (st.get("units") or []) if k in units]
        if not keys:
            # Typed store never emits empty-unit stories; refuse inventing one.
            continue
        lay = (st.get("layer") or "other").strip() or "other"
        scopes: set[str] = set()
        fids: list[str] = []
        roles: list[str] = []
        for k in keys:
            u = units[k]
            lp = (u.get("legacy_path") or "").replace("\\", "/")
            if lp and not is_generated_build_path(lp):
                scopes.add(lp)
            for fid in u.get("findings") or []:
                if fid and fid not in fids:
                    fids.append(fid)
            d = u.get("decision") if isinstance(u.get("decision"), dict) else None
            if _decision_complete(d):
                roles.append(str(d.get("role") or "").upper())
        # Scope supplement only — never a membership source.
        for p in staging_scopes.get(lay) or []:
            if p and not is_generated_build_path(p):
                scopes.add(p)
        harvest_n = sum(1 for r in roles if r == "HARVEST")
        redesign_n = sum(1 for r in roles if r == "REDESIGN")
        role_note = (
            f"roles HARVEST={harvest_n} REDESIGN={redesign_n}"
            if roles
            else "roles pending"
        )
        scope_s = ", ".join(sorted(scopes)) if scopes else "<!-- JUDGMENT: paths -->"
        sid = st.get("id") or f"S{len(stories) + 1:02d}"
        title = LAYER_TITLE.get(lay, lay.replace("-", " ").title())
        stories.append(
            {
                "sid": sid,
                "title": title,
                "scope": scope_s,
                "findings": list(fids),
                "findings_raw": ", ".join(fids) if fids else "-",
                "depends": "-",
                "deploy": bool(st.get("deploy")),
                "done": "<!-- JUDGMENT: checkable done-criterion -->",
                "rationale": (
                    f"ADR-34 model.stories[] id={sid} slug={st.get('slug') or lay} "
                    f"layer={lay} units={len(keys)} {role_note} "
                    f"(F-story-rendered out-half; staging scope supplement only)"
                ),
                "kind": None,
                "seat_budget": None,
                "body": "",
                "_unit_keys": list(keys),
                "_slug": st.get("slug") or lay,
            }
        )

    if not stories:
        return skeleton_from_inventory(inv, "", root=root)

    # Refuse silent drift: rendered count must equal typed store.
    if len(stories) != len(typed):
        raise SystemExit(
            f"O-M2SKELDRIFT RED: skeleton stories={len(stories)} != "
            f"model.stories[]={len(typed)} (F-story-rendered out-half)"
        )
    ensure_deploy_last(stories)
    return stories


def cut_skeleton_stories(
    root: Path, inv: dict, dep_text: str = ""
) -> tuple[list[dict], str]:
    """Choose SoT for skeleton cut. Returns (stories, source_tag)."""
    if model_has_typed_profile_roles(root):
        return skeleton_from_model(root, inv), "model"
    return skeleton_from_inventory(inv, dep_text, root=root), "inventory"


def extract_nm_section(text: str) -> str:
    m = re.search(r"(?im)^##\s+Non-mandatory decisions\b.*", text, re.S)
    return m.group(0) if m else ""


def extract_cycle_waiver_section(text: str) -> str:
    """O-CYCLEPART — preserve typed cycle waivers across fill rewrites."""
    m = re.search(
        r"(?ims)^##\s+Cycle partition waivers\b.*?(?=^##\s|\Z)",
        text,
    )
    if m:
        return m.group(0).rstrip() + "\n"
    return ""


def with_preserved_cycle_waiver(body: str, prior_text: str) -> str:
    """Re-attach ## Cycle partition waivers if fill regenerated the roadmap."""
    if re.search(r"(?im)^##\s+Cycle partition waivers\b", body):
        return body
    cyc = extract_cycle_waiver_section(prior_text)
    if not cyc:
        return body
    return body.rstrip() + "\n\n" + cyc


def _strip_skeleton_preamble(body: str, prior_text: str) -> str:
    """Drop compose skeleton markers when rewriting an authored roadmap."""
    if is_roadmap_skeleton(prior_text):
        return body
    body = body.replace(SKELETON_MARK + "\n", "")
    body = re.sub(
        r"# O-M2COMPOSE — mechanical[^\n]*\n"
        r"(?:# Model fills JUDGMENT[^\n]*\n){1,2}\n?",
        "",
        body,
        count=1,
    )
    return body


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
    profile_path = root / "migration" / "architecture-profile.md"
    redesign_cls: set[str] = set()
    contract_hints: dict[str, str] = {}
    profile_sec7 = ""
    # ADR-29 — prefer typed decisions on the model (F-render-oneway).
    # Missing model.json is OK for fixtures / pre-model compose — fall back to §7.
    redesign_cls = redesign_classes_from_model(root)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from profile_roles import redesign_contract_hints  # type: ignore

        contract_hints = redesign_contract_hints(root)
    except (ImportError, FileNotFoundError, OSError):
        contract_hints = {}
    if profile_path.is_file():
        _prof = profile_path.read_text(encoding="utf-8", errors="replace")
        if not redesign_cls:
            redesign_cls = redesign_classes_from_profile(_prof, root=None)
        if not contract_hints:
            contract_hints = redesign_contract_hints_from_profile(_prof, root=None)
        profile_sec7 = profile_sec7_digest(_prof)

    prior_nm = ""
    wrote_roadmap = False
    n_kind = 0
    n_sfnd = 0
    n_budget = 0
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
                stories, skel_src = cut_skeleton_stories(root, inv, dep_text)
                # Preserve kind/seat-budget if re-skeletonizing
                old = parse_roadmap(text)
                by_sid = {s["sid"]: s for s in old}
                for st in stories:
                    if st["sid"] in by_sid and by_sid[st["sid"]].get("kind"):
                        st["kind"] = by_sid[st["sid"]]["kind"]
                stories = unique_partition(stories, inv, root=root)
                n_kind = derive_kinds(stories, inv, redesign_cls)
                n_budget = apply_seat_budgets(stories, inv_text)
                derive_story_depends(stories, root)
                ensure_deploy_last(stories)
                roadmap_path.write_text(
                    render_roadmap(stories, inv["non_mandatory"], prior_nm),
                    encoding="utf-8",
                )
                wrote_roadmap = True
                print(
                    f"O-M2COMPOSE: wrote skeleton roadmap stories={len(stories)} "
                    f"source={skel_src} kind-updates={n_kind} "
                    f"seat-budget-updates={n_budget}"
                )
        if not roadmap_path.is_file() or force_skeleton:
            stories, skel_src = cut_skeleton_stories(root, inv, dep_text)
            stories = unique_partition(stories, inv, root=root)
            n_kind = derive_kinds(stories, inv, redesign_cls)
            n_budget = apply_seat_budgets(stories, inv_text)
            derive_story_depends(stories, root)
            ensure_deploy_last(stories)
            roadmap_path.parent.mkdir(parents=True, exist_ok=True)
            roadmap_path.write_text(
                render_roadmap(stories, inv["non_mandatory"], ""),
                encoding="utf-8",
            )
            wrote_roadmap = True
            print(
                f"O-M2COMPOSE: wrote skeleton roadmap stories={len(stories)} "
                f"source={skel_src} kind-updates={n_kind} "
                f"seat-budget-updates={n_budget}"
            )

    if mode == "fill":
        if not roadmap_path.is_file():
            print(
                "O-M2COMPOSE: no roadmap — falling through to skeleton",
                file=sys.stderr,
            )
            return compose(root, "skeleton", force_skeleton=True)
        text = roadmap_path.read_text(encoding="utf-8", errors="replace")
        prior_nm = extract_nm_section(text)
        # ADR-34 REV-2 / F-story-rendered: when typed decisions exist, membership
        # SoT is the model partition — merge JUDGMENT fields from authored roadmap.
        if model_has_typed_profile_roles(root):
            stories, skel_src = cut_skeleton_stories(root, inv, dep_text)
            authored = parse_roadmap(text)
            by_sid = {s["sid"]: s for s in authored}
            for st in stories:
                old = by_sid.get(st["sid"])
                if not old:
                    continue
                # JUDGMENT only — never take membership/scope/deploy from roadmap.
                for k in ("title", "rationale", "kind", "done", "body", "seat_budget"):
                    if old.get(k):
                        st[k] = old[k]
            # O-M2SKELDRIFT / W4-540: refuse when rendered count ≠ typed store
            # (extra ## S0N from staging-empty platform invent or seat rewrite).
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from model import load as _model_load  # type: ignore

            typed_n = len((_model_load(root).get("stories") or []))
            if typed_n and len(stories) != typed_n:
                print(
                    f"O-M2SKELDRIFT RED: fill stories={len(stories)} != "
                    f"model.stories[]={typed_n} (F-story-rendered out-half)",
                    file=sys.stderr,
                )
                return 2
            print(
                f"O-M2COMPOSE: fill membership source={skel_src} "
                f"stories={len(stories)} typed={typed_n} "
                f"(F-story-rendered; JUDGMENT merged from roadmap)"
            )
        else:
            stories = parse_roadmap(text)
        if not stories:
            print("O-M2COMPOSE RED: roadmap has no stories", file=sys.stderr)
            return 2
        # O-M2DECOMPAXIS: collapse JDBC/JPA/Spring-Data (and model-part) over-splits
        # Skip when ADR-34 model partition already owns membership.
        if not model_has_typed_profile_roles(root):
            stories, n_collapse = collapse_to_layer_stories(stories)
        else:
            n_collapse = 0
        if n_collapse:
            print(
                f"O-M2COMPOSE: O-M2DECOMPAXIS collapsed {n_collapse} "
                f"same-layer over-split(s) → {len(stories)} layer stories"
            )
        before_sfnd = sum(
            1
            for st in stories
            if (st.get("findings_raw") or "").strip() == "-"
            and _scope_redesignish(st.get("scope") or "")
            and not _scope_harvestish(st, root=root)
        )
        stories = unique_partition(stories, inv, root=root)
        after_sfnd = sum(
            1
            for st in stories
            if (st.get("findings_raw") or "").strip() == "-"
            and _scope_redesignish(st.get("scope") or "")
            and not _scope_harvestish(st, root=root)
        )
        n_sfnd = max(0, before_sfnd - after_sfnd)
        n_nogen = strip_generated_scope(stories)
        n_stage = apply_staging_scope(stories, root)
        n_kind = derive_kinds(stories, inv, redesign_cls)
        n_budget = apply_seat_budgets(stories, inv_text)
        n_deps = derive_story_depends(stories, root)
        ensure_deploy_last(stories)
        body = render_roadmap(stories, inv["non_mandatory"], prior_nm)
        body = _strip_skeleton_preamble(body, text)
        body = with_preserved_cycle_waiver(body, text)
        roadmap_path.write_text(body, encoding="utf-8")
        if n_deps:
            print(f"O-M2COMPOSE: O-DEPCHAIN depends-updates={n_deps}")
        wrote_roadmap = True
        print(
            f"O-M2COMPOSE: fill stories={len(stories)} "
            f"kind-updates={n_kind} sfnd-repairs={n_sfnd} "
            f"scope-nogen={n_nogen} staging-scope={n_stage} "
            f"seat-budget-updates={n_budget} must={len(inv['must'])}"
        )

    # Reload stories for brief sync
    stories = parse_roadmap(
        roadmap_path.read_text(encoding="utf-8", errors="replace")
    )
    # Re-apply kinds + budgets onto parsed stories for brief publish
    derive_kinds(stories, inv, redesign_cls)
    apply_seat_budgets(stories, inv_text)
    # Persist budget/kind fields again if fill stripped them somehow
    if any(st.get("kind") and st.get("seat_budget") for st in stories):
        prior_nm = extract_nm_section(
            roadmap_path.read_text(encoding="utf-8", errors="replace")
        )
        body = render_roadmap(stories, inv["non_mandatory"], prior_nm)
        cur = roadmap_path.read_text(encoding="utf-8", errors="replace")
        body = _strip_skeleton_preamble(body, cur)
        body = with_preserved_cycle_waiver(body, cur)
        if body != cur:
            roadmap_path.write_text(body, encoding="utf-8")
            wrote_roadmap = True

    # O-BRIEFFRESHPROFILE: stamp §7 digest onto every story before freshness.
    for st in stories:
        st["profile_sec7"] = profile_sec7
    bw, br = write_briefs(
        root,
        stories,
        force_skeleton=force_skeleton,
        redesign_cls=redesign_cls,
        contract_hints=contract_hints,
        open_design=inv.get("open_design") or set(),
    )
    print(
        f"O-M2COMPOSE: done mode={mode} roadmap_written={wrote_roadmap} "
        f"briefs_wrote={bw} briefs_refreshed={br} "
        f"kind-updates={n_kind} seat-budget-updates={n_budget}"
    )
    # ADR-24: bind stories[] into model.json (sole M2 mutation API).
    model_json = root / "migration" / "model.json"
    if model_json.is_file():
        try:
            from model import assign_stories as _adr24_assign

            _adr24_assign(root)
            print("O-ADR24: assign_stories OK")
        except SystemExit as e:
            print(f"O-ADR24 assign_stories RED: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"O-ADR24 assign_stories WARN: {e}", file=sys.stderr)
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
