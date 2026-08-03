#!/usr/bin/env bash
# O-M3ALL — whole-plan-set lint (cross-story properties) + JIT re-lint helper.
#
# After M2, every story plan is authored and linted as a set before any M4.
# This script computes properties that are invisible to per-story plan-lint:
#   - K1 partition (finding ids owned by exactly one story)
#   - File-level Owns partition (same path/class Owned by >1 story — A4)
#   - Port coverage (repository-layer stories declare Port)
#   - Later-class leakage (story N names a class owned by a later story's scope)
#   - Projected-tree (dest ∪ prior Owns; RED on create-into-prior collision)
#   - Oracle completeness (every task declares Oracle: present|absent)
#   - Assumes closure (A6 — every Assumes: satisfied by earlier Owns/output)
#
# Waterfall antidotes (mandatory — never optional):
#   JIT re-lint before each story M4; Owns/Port/Shape amend → whole-set re-lint;
#   treat plan-vs-reality delta as first-class signal.
#
# Operator gate + prediction freeze (between whole-set GREEN and first M4):
#   --mode=freeze-predictions  write migration/.m3-all-predictions.md
#   --mode=operator-gate       require APPROVED gate (+ auto if M3_ALL_OPERATOR_AUTO=1)
#
# Usage:
#   bash .hermes/harness/m3-all-lint.sh --mode=whole-set
#   bash .hermes/harness/m3-all-lint.sh --mode=jit --story S03
#   bash .hermes/harness/m3-all-lint.sh --mode=wire-check   # outer-loop hooks present
#   bash .hermes/harness/m3-all-lint.sh --mode=freeze-predictions
#   bash .hermes/harness/m3-all-lint.sh --mode=operator-gate
#   bash .hermes/harness/m3-all-lint.sh --specs-root DIR --roadmap FILE
#
# Exit 0 = GREEN; 1 = LINT findings; 2 = usage / missing inputs; 3 = JIT amend.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="whole-set"
STORY=""
SPECS_ROOT=""
ROADMAP=""
ROOT="."

while [ $# -gt 0 ]; do
  case "$1" in
    --mode=*) MODE="${1#--mode=}"; shift ;;
    --mode) MODE="${2:-}"; shift 2 || true ;;
    --story=*) STORY="${1#--story=}"; shift ;;
    --story) STORY="${2:-}"; shift 2 || true ;;
    --specs-root=*) SPECS_ROOT="${1#--specs-root=}"; shift ;;
    --specs-root) SPECS_ROOT="${2:-}"; shift 2 || true ;;
    --roadmap=*) ROADMAP="${1#--roadmap=}"; shift ;;
    --roadmap) ROADMAP="${2:-}"; shift 2 || true ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    --root) ROOT="${2:-}"; shift 2 || true ;;
    -h|--help)
      sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) shift ;;
  esac
done

ROOT="$(cd "$ROOT" && pwd)"
SPECS_ROOT="${SPECS_ROOT:-$ROOT/specs}"
ROADMAP="${ROADMAP:-$ROOT/migration/roadmap.md}"
OUTER="${HARNESS_DIR}/outer-loop.sh"

if [ "$MODE" = "wire-check" ]; then
  missing=0
  for needle in 'O-M3ALL' 'm3-all-lint.sh' 'M3_ALL_PASS' 'waterfall' \
                'freeze-predictions' 'operator-gate' 'OPERATOR_GATE' \
                'm3-all-compose.py' 'skeleton-first'; do
    if ! grep -q -- "$needle" "$OUTER"; then
      echo "O-M3ALL: outer-loop.sh missing hook marker: $needle" >&2
      missing=1
    fi
  done
  if [ ! -f "${HARNESS_DIR}/m3-all-compose.py" ]; then
    echo "O-M3ALL: missing m3-all-compose.py (skeleton-first)" >&2
    missing=1
  fi
  # Waterfall antidotes must stay mandatory (not behind a soft skip).
  # Match live assignments / case arms only — comments may name the ban.
  if grep -Eq '^[^#]*\b(M3_ALL_SKIP_JIT|WATERFALL_OPTIONAL)=' "$OUTER" \
    || grep -Eq '^[^#]*\$\{M3_ALL_SKIP_JIT' "$OUTER"; then
    echo "O-M3ALL: outer-loop must not offer optional waterfall skip flags" >&2
    missing=1
  fi
  if [ "$missing" -ne 0 ]; then
    exit 1
  fi
  echo "O-M3ALL: wire-check OK (outer-loop hooks + mandatory waterfall antidotes + skeleton-first)"
  exit 0
fi

# Prediction freeze — durable copy of the merged prediction table (HANDOFF).
if [ "$MODE" = "freeze-predictions" ]; then
  PRED_DIR="$ROOT/migration"
  mkdir -p "$PRED_DIR"
  PRED_FILE="$PRED_DIR/.m3-all-predictions.md"
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  STAMP_FP=""
  if [ -d "$PRED_DIR/.m3-all-stamps" ]; then
    STAMP_FP="$(cat "$PRED_DIR/.m3-all-stamps"/*.fields 2>/dev/null | shasum -a 256 | awk '{print $1}')"
  fi
  cat >"$PRED_FILE" <<EOF
# O-M3ALL prediction table — FROZEN
# frozen_at: ${TS}
# whole-set_fields_fp: ${STAMP_FP:-none}
# Judge restart on row 1 (time to first plan defect). Rename-class is the control.

| Metric | This wave (measured) | Predicted next wave |
|---|---|---|
| **Time to first plan defect detected** | ≈4.7–6.0h (outcome-to-outcome) | ≤30 min from M2 commit |
| S03 repository tasks declaring \`Port\` | 0 of 5 | 5 of 5 |
| Tasks declaring \`Oracle\` | 1 of 5 | all (skeleton-generated field) |
| Reimplement-class task seat cost | 11 seats, ~3h | ≤4 seats |
| Rename-class task seat cost | 1 seat, 5 min | unchanged (control) |
| M3 revisions to reach accepted plan (S03) | 7 | ≤3 |
| Whole-set lint clean before first M4 | not computable | GREEN, recorded |
| Plans passing current lint | 1 of 3 (S01 only) | 3 of 3 |
| S03 outcome | debt-freeze, T-004 unresolved | shipped |
EOF
  echo "O-M3ALL: prediction table frozen → $PRED_FILE"
  exit 0
fi

# Operator gate — whole-set GREEN + frozen predictions before first M4.
if [ "$MODE" = "operator-gate" ]; then
  PRED_FILE="$ROOT/migration/.m3-all-predictions.md"
  GATE_FILE="$ROOT/migration/.m3-all-operator-gate"
  if [ ! -f "$PRED_FILE" ]; then
    echo "O-M3ALL OPERATOR_GATE RED: missing $PRED_FILE — run --mode=freeze-predictions first" >&2
    exit 1
  fi
  PRED_FP="$(shasum -a 256 "$PRED_FILE" | awk '{print $1}')"
  AUTO="${M3_ALL_OPERATOR_AUTO:-0}"
  if [ ! -f "$GATE_FILE" ] || ! grep -qE '^status:[[:space:]]*APPROVED\b' "$GATE_FILE"; then
    if [ "$AUTO" = "1" ]; then
      cat >"$GATE_FILE" <<EOF
# O-M3ALL operator gate (auto-approved — M3_ALL_OPERATOR_AUTO=1)
status: APPROVED
predictions_fp: ${PRED_FP}
approved_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
      echo "O-M3ALL: OPERATOR_GATE auto-APPROVED → $GATE_FILE"
      exit 0
    fi
    echo "O-M3ALL OPERATOR_GATE RED: write $GATE_FILE with status: APPROVED after reviewing whole-set + predictions" >&2
    echo "  predictions_fp expected: $PRED_FP" >&2
    echo "  (non-interactive: M3_ALL_OPERATOR_AUTO=1)" >&2
    exit 1
  fi
  GATE_FP="$(sed -n 's/^predictions_fp:[[:space:]]*//p' "$GATE_FILE" | head -1)"
  if [ -z "$GATE_FP" ] || [ "$GATE_FP" != "$PRED_FP" ]; then
    echo "O-M3ALL OPERATOR_GATE RED: predictions_fp mismatch (gate=$GATE_FP live=$PRED_FP) — re-approve after freeze" >&2
    exit 1
  fi
  echo "O-M3ALL: OPERATOR_GATE APPROVED (predictions_fp=$PRED_FP)"
  exit 0
fi

python3 - "$MODE" "$STORY" "$SPECS_ROOT" "$ROADMAP" "$ROOT" <<'PY'
import os, re, sys
from pathlib import Path

mode, story, specs_root, roadmap, root = sys.argv[1:6]
specs_root = Path(specs_root)
roadmap_p = Path(roadmap)
root = Path(root)
lint_n = 0

def lint(klass: str, msg: str) -> None:
    global lint_n
    lint_n += 1
    print(f"LINT:{klass}: {msg}")

def ok(msg: str) -> None:
    print(f"OK: {msg}")

FINDING_RE = re.compile(
    r"\b([a-z][a-z0-9]*(?:-[a-z0-9]+)+-\d+)\b"
)
PORT_RE = re.compile(
    r"(?im)^\*\*Port\*\*\s*:?\s*(rename|reimplement)\b"
    r"|^\*\*Port\s*:\s*(rename|reimplement)\*\*"
    r"|^Port\s*:\s*(rename|reimplement)\b"
)
OWNS_RE = re.compile(
    r"(?im)^\*\*(?:Owns|Absorbs|Target(?:\s*design)?)\*\*\s*:?\s*(.+)$"
)
JAVA_PATH = re.compile(
    r"(?:src/(?:main|test)/java/)?([\w]+(?:/[\w]+)*/[A-Z][\w]*)\.java"
)
CLASS_NAME = re.compile(r"\b([A-Z][A-Za-z0-9]+)\b")
REPO_SIGNAL = re.compile(
    r"(?i)\b(repository|spring\s*data|springdatajpa|panache|"
    r"jdbctemplate|namedparameterjdbc|agroal|crudrepository|"
    r"jpa\.repository|entitymanager)\b"
)
TASK_HEAD = re.compile(r"(?m)^####\s+(T-\d+)\b")
SHAPE_RE = re.compile(
    r"(?im)^\*\*Shape\*\*\s*:?\s*(create|modify|delete)\b"
    r"|^Shape\s*:\s*(create|modify|delete)\b"
)
ORACLE_RE = re.compile(
    r"(?im)^\*\*Oracle\*\*\s*:?\s*(present|absent)\b"
    r"|^Oracle\s*:\s*(present|absent)\b"
)
ASSUMES_RE = re.compile(
    r"(?im)^\*\*Assumes\*\*\s*:?\s*(.+)$"
    r"|^Assumes\s*:\s*(.+)$"
)
ASSUME_OWED = re.compile(
    r"\((S\d{2,})\s+(T-\d+)\)"
)

def parse_roadmap(text: str):
    heads = re.findall(r"^##\s+(S\d{2,})\s*:", text, re.M)
    parts = re.split(r"^##\s+(S\d{2,})\s*:.*$", text, flags=re.M)
    bodies = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    stories = []
    for sid in heads:
        body = bodies.get(sid, "")
        def field(name: str) -> str:
            m = re.search(rf"^-\s*{name}:\s*(.+)$", body, re.M)
            return m.group(1).strip() if m else ""
        findings = [
            f for f in re.split(r"[,\s]+", field("findings"))
            if f and f != "-" and FINDING_RE.fullmatch(f)
        ]
        scope = [s.strip().rstrip(",") for s in field("scope").split(",") if s.strip()]
        stories.append({"sid": sid, "findings": findings, "scope": scope})
    return stories

def tasks_for(sid: str):
    if not specs_root.is_dir():
        return None
    matches = sorted(specs_root.glob(f"{sid}-*/tasks.md"))
    if not matches:
        # also allow exact slug dirs without forcing specimen names
        matches = sorted(
            p for p in specs_root.glob("*/tasks.md")
            if p.parent.name.startswith(sid + "-") or p.parent.name == sid
        )
    return matches[0] if matches else None

def parse_tasks(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = sorted(set(FINDING_RE.findall(text)))
    ports = PORT_RE.findall(text)
    owns_paths = []
    for m in OWNS_RE.finditer(text):
        owns_paths.extend(JAVA_PATH.findall(m.group(1)))
    # bare Owns lists: path tokens on the line
    for m in re.finditer(r"(?im)^\*\*Owns\*\*\s*:?\s*(.+)$", text):
        owns_paths.extend(JAVA_PATH.findall(m.group(1)))
    class_names = set()
    for p in owns_paths:
        class_names.add(p.rsplit("/", 1)[-1])
    for m in JAVA_PATH.finditer(text):
        class_names.add(m.group(1).rsplit("/", 1)[-1])
    repo = bool(REPO_SIGNAL.search(text))
    task_ids = TASK_HEAD.findall(text)
    # Per-task blocks so Shape=create collisions don't false-red modify Owns.
    create_owns = []
    task_meta = []  # [{tid, oracle, assumes, owns, classes}]
    parts = re.split(r"(?m)^(?=####\s+T-\d+\b)", text)
    for block in parts:
        th = TASK_HEAD.search(block)
        if not th:
            continue
        tid = th.group(1)
        shape_m = SHAPE_RE.search(block)
        if shape_m:
            shape = next(g for g in shape_m.groups() if g).lower()
            if shape == "create":
                block_owns = []
                for m in re.finditer(r"(?im)^\*\*Owns\*\*\s*:?\s*(.+)$", block):
                    block_owns.extend(JAVA_PATH.findall(m.group(1)))
                create_owns.extend(block_owns)
        oracle_m = ORACLE_RE.search(block)
        oracle = ""
        if oracle_m:
            oracle = next(g for g in oracle_m.groups() if g).lower()
        assumes_lines = []
        for m in ASSUMES_RE.finditer(block):
            assumes_lines.append(next(g for g in m.groups() if g).strip())
        block_owns = []
        for m in re.finditer(r"(?im)^\*\*Owns\*\*\s*:?\s*(.+)$", block):
            block_owns.extend(JAVA_PATH.findall(m.group(1)))
        block_classes = {o.rsplit("/", 1)[-1] for o in block_owns}
        task_meta.append(
            {
                "tid": tid,
                "oracle": oracle,
                "assumes": assumes_lines,
                "owns": sorted(set(block_owns)),
                "classes": sorted(block_classes),
            }
        )
    return {
        "path": path,
        "findings": findings,
        "has_port": bool(ports),
        "owns_paths": sorted(set(owns_paths)),
        "classes": sorted(class_names),
        "repo": repo,
        "tasks": task_ids,
        "create_owns": sorted(set(create_owns)),
        "task_meta": task_meta,
        "text": text,
    }

roadmap_stories = []
if roadmap_p.is_file():
    roadmap_stories = parse_roadmap(roadmap_p.read_text(encoding="utf-8", errors="replace"))
else:
    # Fixture mode: discover SNN-* dirs under specs_root
    if specs_root.is_dir():
        for d in sorted(specs_root.iterdir()):
            if d.is_dir() and re.match(r"S\d{2,}", d.name):
                sid = re.match(r"(S\d{2,})", d.name).group(1)
                roadmap_stories.append({"sid": sid, "findings": [], "scope": []})

if not roadmap_stories:
    lint("O-M3ALL", "no stories discovered (roadmap missing and specs empty)")
    print(f"O-M3ALL: {lint_n} LINT(s) — RED")
    sys.exit(1)

# Attach plans
for s in roadmap_stories:
    tp = tasks_for(s["sid"])
    s["tasks_path"] = tp
    s["plan"] = parse_tasks(tp) if tp else None

missing = [s["sid"] for s in roadmap_stories if s["plan"] is None]
if mode == "whole-set" and missing:
    for sid in missing:
        lint("O-M3ALL-MISSING", f"{sid}: no specs/{sid}-*/tasks.md — author all plans before any M4")

# --- Projected tree: dest ∪ prior Owns ------------------------------------
dest_java = set()
src_main = root / "src" / "main" / "java"
if src_main.is_dir():
    for p in src_main.rglob("*.java"):
        try:
            rel = str(p.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
        dest_java.add(rel)
        dest_java.add(p.stem)

projected = set(dest_java)
projection_log = []
for s in roadmap_stories:
    prior = set(projected)
    plan = s["plan"]
    owns = plan["owns_paths"] if plan else []
    classes = plan["classes"] if plan else []
    projection_log.append((s["sid"], sorted(prior), owns, classes))
    for o in owns:
        projected.add(o)
        projected.add(o.rsplit("/", 1)[-1])
    for c in classes:
        projected.add(c)

ok(
    "projected-tree built for %d stories (dest∪prior Owns)"
    % len(roadmap_stories)
)

# Projected-tree RED: Shape=create Owns into dest ∪ prior Owns (collision).
# modify into existing dest is allowed; dual-Owns is O-M3ALL-FILE below.
for s, (sid, prior, _owns, _classes) in zip(roadmap_stories, projection_log):
    plan = s["plan"]
    if not plan:
        continue
    prior_set = set(prior)
    for o in plan.get("create_owns", []):
        stem = o.rsplit("/", 1)[-1]
        if o in prior_set or stem in prior_set:
            lint(
                "O-M3ALL-TREE",
                f"{sid}: Shape=create Owns `{o}` already in projected "
                f"tree (dest∪prior Owns) — projected-tree collision",
            )

# --- File-level Owns partition (A4 — cross-story incident ownership) ------
# Finding-level K1 is checked at M2/M3 per-story; this is the genuine
# cross-story prize: same file/class Owned by more than one story.
file_owners = {}
for s in roadmap_stories:
    plan = s["plan"]
    if not plan:
        continue
    keys = set(plan["owns_paths"])
    for o in plan["owns_paths"]:
        keys.add(o.rsplit("/", 1)[-1])
    for key in keys:
        file_owners.setdefault(key, []).append(s["sid"])

for key, sids in sorted(file_owners.items()):
    uniq = sorted(set(sids))
    if len(uniq) > 1:
        lint(
            "O-M3ALL-FILE",
            f"path/class {key} Owned by multiple stories: {','.join(uniq)} "
            f"(file-level Owns partition — projected-tree / A4)",
        )

# --- K1 partition (cross-story finding ownership) -------------------------
owners = {}  # finding -> [sid, ...]
for s in roadmap_stories:
    claimed = set(s["findings"])
    if s["plan"]:
        claimed |= set(s["plan"]["findings"])
    for fid in claimed:
        owners.setdefault(fid, []).append(s["sid"])

for fid, sids in sorted(owners.items()):
    uniq = sorted(set(sids))
    if len(uniq) > 1:
        lint(
            "O-M3ALL-K1",
            f"finding {fid} owned by multiple stories: {','.join(uniq)} "
            f"(K1 partition — exactly one story)",
        )

# Roadmap-mandatory findings must appear in some plan when plans exist
planned_any = any(s["plan"] for s in roadmap_stories)
if planned_any:
    for s in roadmap_stories:
        if not s["findings"]:
            continue
        if s["plan"] is None:
            continue
        plan_f = set(s["plan"]["findings"])
        for fid in s["findings"]:
            # Allow roadmap claim without task cite only if another story
            # doesn't also claim it (already covered). Still require the
            # owning story's plan to mention it when that plan exists.
            if fid not in plan_f and owners.get(fid, [s["sid"]]) == [s["sid"]]:
                lint(
                    "O-M3ALL-K1",
                    f"{s['sid']}: roadmap finding {fid} not cited in {s['tasks_path'].name} "
                    f"(K1 closure)",
                )

# --- Port coverage --------------------------------------------------------
for s in roadmap_stories:
    plan = s["plan"]
    if not plan:
        continue
    scope_blob = " ".join(s["scope"])
    if plan["repo"] or REPO_SIGNAL.search(scope_blob):
        if not plan["has_port"]:
            lint(
                "O-M3ALL-PORT",
                f"{s['sid']}: repository-layer plan/scope without any "
                f"**Port**: rename|reimplement (Port coverage)",
            )

# --- Later-class leakage --------------------------------------------------
# Class simple-names appearing in later stories' roadmap scope must not be
# Owned/Targeted by an earlier story.
later_classes_by_sid = {}
all_scope_classes = {}
for idx, s in enumerate(roadmap_stories):
    classes = set()
    for path in s["scope"]:
        base = path.rstrip("/").split("/")[-1]
        base = re.sub(r"\.java$", "", base)
        if re.fullmatch(r"[A-Z][A-Za-z0-9]*", base):
            classes.add(base)
            all_scope_classes.setdefault(base, []).append(s["sid"])
    later_classes_by_sid[s["sid"]] = set()
    for later in roadmap_stories[idx + 1 :]:
        for path in later["scope"]:
            base = re.sub(r"\.java$", "", path.rstrip("/").split("/")[-1])
            if re.fullmatch(r"[A-Z][A-Za-z0-9]*", base):
                later_classes_by_sid[s["sid"]].add(base)

for s in roadmap_stories:
    plan = s["plan"]
    if not plan:
        continue
    leaked = sorted(set(plan["classes"]) & later_classes_by_sid.get(s["sid"], set()))
    for cls in leaked:
        lint(
            "O-M3ALL-LATER",
            f"{s['sid']}: plan Owns/Target class {cls} assigned to a later "
            f"story scope (later-class leakage)",
        )

# --- Oracle completeness (whole-set) --------------------------------------
# Every task must declare Oracle: present|absent (skeleton field; not silent default).
for s in roadmap_stories:
    plan = s["plan"]
    if not plan:
        continue
    for tm in plan.get("task_meta", []):
        if tm["oracle"] not in ("present", "absent"):
            lint(
                "O-M3ALL-ORACLE",
                f"{s['sid']} {tm['tid']}: missing **Oracle**: present|absent "
                f"(Oracle completeness — whole-set)",
            )

# --- Assumes closure (A6) -------------------------------------------------
# Declared Assumes must be satisfied by dest ∪ earlier stories' Owns/output.
# Format: Assumes: ClassOrPath … (SNN T-NNN) — citation optional but preferred.
sid_order = [s["sid"] for s in roadmap_stories]
# Build cumulative prior symbols after each story (for same-story earlier tasks
# we also allow earlier task Owns within the story).
prior_by_sid = {}
running = set(dest_java)
for s in roadmap_stories:
    prior_by_sid[s["sid"]] = set(running)
    plan = s["plan"]
    if plan:
        running.update(plan["owns_paths"])
        running.update(plan["classes"])

# Per-task Owns within a story for same-story Assumes.
for s in roadmap_stories:
    plan = s["plan"]
    if not plan:
        continue
    sid = s["sid"]
    earlier_in_story = set()
    for tm in plan.get("task_meta", []):
        prior = set(prior_by_sid.get(sid, set())) | earlier_in_story
        for line in tm.get("assumes", []):
            # Extract class/path tokens from the Assumes line
            refs = set(JAVA_PATH.findall(line))
            for tok in re.findall(r"\b([A-Z][A-Za-z0-9]+)\b", line):
                # Skip story/task ids (S01, T-001) and field/prose tokens
                if re.fullmatch(r"S\d{2,}", tok) or re.fullmatch(r"T-\d+", tok):
                    continue
                if tok in (
                    "Assumes", "Oracle", "Exists", "Present", "Absent",
                    "Shape", "Class", "Port", "Target", "Source",
                ):
                    continue
                refs.add(tok)
            owed = ASSUME_OWED.search(line)
            if owed:
                owed_sid, owed_tid = owed.group(1), owed.group(2)
                if owed_sid not in sid_order:
                    lint(
                        "O-M3ALL-ASSUMES",
                        f"{sid} {tm['tid']}: Assumes cites unknown story "
                        f"{owed_sid} — {line}",
                    )
                elif sid_order.index(owed_sid) > sid_order.index(sid):
                    lint(
                        "O-M3ALL-ASSUMES",
                        f"{sid} {tm['tid']}: Assumes cites later story "
                        f"{owed_sid} {owed_tid} — not closed by earlier output",
                    )
                else:
                    # Owning story must declare the symbol (or same-story earlier task)
                    donor = next(
                        (x for x in roadmap_stories if x["sid"] == owed_sid), None
                    )
                    donor_syms = set()
                    if donor and donor["plan"]:
                        if owed_sid == sid:
                            donor_syms = set(earlier_in_story)
                        else:
                            donor_syms = set(donor["plan"]["owns_paths"]) | set(
                                donor["plan"]["classes"]
                            )
                            # Prefer the cited task's Owns when present
                            for dtm in donor["plan"].get("task_meta", []):
                                if dtm["tid"] == owed_tid:
                                    donor_syms = set(dtm["owns"]) | set(dtm["classes"])
                                    break
                    for ref in refs:
                        stem = ref.rsplit("/", 1)[-1]
                        if ref not in donor_syms and stem not in donor_syms:
                            lint(
                                "O-M3ALL-ASSUMES",
                                f"{sid} {tm['tid']}: Assumes `{stem}` not in "
                                f"{owed_sid} {owed_tid} Owns/output — {line}",
                            )
            else:
                # No citation: symbol must already be in projected prior tree
                for ref in refs:
                    stem = ref.rsplit("/", 1)[-1]
                    if ref not in prior and stem not in prior:
                        lint(
                            "O-M3ALL-ASSUMES",
                            f"{sid} {tm['tid']}: Assumes `{stem}` not in "
                            f"projected prior (dest∪earlier Owns) — {line}",
                        )
        earlier_in_story.update(tm.get("owns", []))
        earlier_in_story.update(tm.get("classes", []))

# --- JIT mode: single-story focus + delta vs projection -------------------
if mode == "jit":
    if not story:
        print("O-M3ALL: --mode=jit requires --story SNN", file=sys.stderr)
        sys.exit(2)
    hit = next((s for s in roadmap_stories if s["sid"] == story), None)
    if hit is None:
        lint("O-M3ALL-JIT", f"unknown story {story}")
    elif hit["plan"] is None:
        lint("O-M3ALL-JIT", f"{story}: missing tasks.md for JIT re-lint")
    else:
        ok(f"JIT re-lint focus {story} tasks={hit['tasks_path']}")
        # Projection for this story = dest ∪ owns of prior stories
        prior_owns = set(dest_java)
        for s in roadmap_stories:
            if s["sid"] == story:
                break
            if s["plan"]:
                prior_owns.update(s["plan"]["owns_paths"])
                prior_owns.update(s["plan"]["classes"])
        ok(
            "JIT projected prior tree size=%d (dest∪prior Owns) — "
            "delta vs reality is a first-class signal (waterfall antidote)"
            % len(prior_owns)
        )

# --- Amend stamp helper (used by outer-loop) ------------------------------
# Fingerprint Owns/Port/Shape blocks so amend → whole-set re-lint is computable.
stamp_dir = root / "migration" / ".m3-all-stamps"
if mode == "whole-set" and planned_any and not missing:
    stamp_dir.mkdir(parents=True, exist_ok=True)
    for s in roadmap_stories:
        if not s["plan"]:
            continue
        text = s["plan"]["text"]
        # Stable fingerprint of partition-sensitive fields only
        fields = []
        for line in text.splitlines():
            if re.match(
                r"(?i)^\s*\*?\*?(Owns|Absorbs|Port|Shape|Oracle|Assumes|"
                r"Target(?:\s*design)?)\*?\*?\s*:",
                line,
            ):
                fields.append(line.strip())
        fp = "\n".join(fields)
        (stamp_dir / f"{s['sid']}.fields").write_text(fp + "\n", encoding="utf-8")
    ok("wrote Owns/Port/Shape/Oracle/Assumes stamps under migration/.m3-all-stamps/ (amend→whole-set)")

if mode == "jit" and story:
    stamp = stamp_dir / f"{story}.fields"
    hit = next((s for s in roadmap_stories if s["sid"] == story), None)
    if hit and hit["plan"] and stamp.is_file():
        fields = []
        for line in hit["plan"]["text"].splitlines():
            if re.match(
                r"(?i)^\s*\*?\*?(Owns|Absorbs|Port|Shape|Oracle|Assumes|"
                r"Target(?:\s*design)?)\*?\*?\s*:",
                line,
            ):
                fields.append(line.strip())
        cur = "\n".join(fields) + "\n"
        old = stamp.read_text(encoding="utf-8")
        if cur != old:
            print(
                "O-M3ALL-AMEND: Owns/Port/Shape/Oracle/Assumes changed since whole-set stamp "
                f"— whole-set re-lint REQUIRED for {story}"
            )
            # Non-zero so outer-loop can branch to whole-set; still a soft signal
            # when only fingerprint drifts — emit as notice + exit 3 for amend.
            print(f"O-M3ALL: JIT amend detected for {story}")
            sys.exit(3)

if lint_n:
    print(f"O-M3ALL: {lint_n} LINT(s) — RED ({mode})")
    sys.exit(1)
print(f"O-M3ALL: PLAN-SET OK ({mode})")
sys.exit(0)
PY
