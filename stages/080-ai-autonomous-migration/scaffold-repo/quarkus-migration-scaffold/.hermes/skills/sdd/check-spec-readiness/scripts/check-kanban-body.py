#!/usr/bin/env python3
"""W2 §6.1 — typed Kanban body vocabulary + stable failure codes.

Looks for body objects in:
  - evidence/tasks/*.json  (field body, or whole object if phase+refs present)
  - evidence/bodies/*.json
  - evidence/kanban/*.json (field body)

Idle (exit 0) when no body artifacts exist.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


def _operand_count_rc(label: str, body: dict) -> int:
    """Architect E-104925Z / E-110403Z — measured operand_count refuse."""
    path = Path(__file__).with_name("check-operand-count.py")
    spec = importlib.util.spec_from_file_location("check_operand_count", path)
    if spec is None or spec.loader is None:
        print(f"BODY_SIZE: {label}: cannot load check-operand-count.py", file=sys.stderr)
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Board-wide lint: count match + caps only. Wall-fit is create-time
    # (--wall-fit) so historical undecomposed verification bodies do not block
    # unrelated authoring (Architect E-111450Z).
    return int(mod.check_one(label, body, wall_fit=False))

REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "M1": ("harvest_referent",),
    "M2": ("mta_findings", "m1_findings_ack"),
    "M3": ("brief_identity_ack", "legacy_locus"),
    "M4": ("story_tip",),
    "M5": ("m4_verdict", "mta_rescan_input"),
    "FACTORY": ("m5_accept",),
}

ALLOWED_EXTRA: dict[str, frozenset[str]] = {
    "M1": frozenset({"legacy_at_3_manifest"}),
    "M2": frozenset({"entry_point_inventory", "brief_draft"}),
    "M3": frozenset(
        {
            "spec_path",
            "plan_path",
            "tasks_path",
            "derive_apply_log",
            "legacy_locus",
            # Operator E-20260811T144200Z — dest paths+digests at create
            "destination_inventory",
        }
    ),
    "M4": frozenset({"g1_fixture", "g2_fixture"}),
    "M5": frozenset({"g3_baseline", "g4_inventory"}),
    "FACTORY": frozenset(),
}

# All known keys = required ∪ allowed for any phase
ALL_KEYS = frozenset(
    k for keys in REQUIRED_KEYS.values() for k in keys
) | frozenset(k for extra in ALLOWED_EXTRA.values() for k in extra)

INLINE_MARKERS = re.compile(
    r"(?i)(BEGIN\s+FINDINGS|BEGIN\s+BLOB|-----BEGIN|"
    r"<html|package\s+com\.|class\s+\w+\s*\{)"
)

# Deputy E-20260811T131200Z — digest slots are hex only; prose sentinels forbidden.
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
# Creation-time typed pending — only for ack refs that do not yet exist.
PENDING_SHA = "pending"
PENDING_ALLOWED_KEYS = frozenset({"brief_identity_ack", "m1_findings_ack"})


def fail(code: str, detail: str) -> None:
    print(f"{code}: {detail}", file=sys.stderr)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def bodies_from(path: Path) -> list[tuple[str, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else [data]
    out: list[tuple[str, dict]] = []
    for i, obj in enumerate(items):
        if not isinstance(obj, dict):
            continue
        label = str(path) if len(items) == 1 else f"{path}[{i}]"
        if isinstance(obj.get("body"), dict):
            out.append((label + ".body", obj["body"]))
        elif "phase" in obj and ("refs" in obj or "task_id" in obj):
            out.append((label, obj))
    return out


def check_body(label: str, body: dict, root: Path) -> int:
    bad = 0
    if not isinstance(body, dict):
        fail("BODY_SCHEMA", "body must be typed object with task_id, role, phase, refs[]")
        return 1
    tid = body.get("task_id") or body.get("id")
    role = body.get("role")
    phase = str(body.get("phase") or "").upper()
    refs = body.get("refs")
    if not tid or not role or not phase or not isinstance(refs, list):
        fail(
            "BODY_SCHEMA",
            "body must be typed object with task_id, role, phase, refs[]",
        )
        bad = 1
        return bad

    # inline content heuristic — exclude large legitimate path lists
    # (W2 §6.4 compile-closure can push files_in_scope past 12k JSON chars).
    slim = {
        k: v
        for k, v in body.items()
        if k not in ("files_in_scope", "filesInScope", "exit_criteria", "done_when")
    }
    raw = json.dumps(slim)
    if len(raw) > 12000 or INLINE_MARKERS.search(raw):
        fail(
            "BODY_INLINE",
            "body must not carry derived content (digest refs only)",
        )
        bad = 1

    vocab = set(REQUIRED_KEYS.get(phase, ())) | set(ALLOWED_EXTRA.get(phase, frozenset()))
    if phase not in REQUIRED_KEYS:
        fail("BODY_SCHEMA", f"body must be typed object with task_id, role, phase, refs[]")
        bad = 1
        return bad

    seen: dict[str, dict] = {}
    for ref in refs:
        if not isinstance(ref, dict):
            fail("BODY_SCHEMA", "body must be typed object with task_id, role, phase, refs[]")
            bad = 1
            continue
        key = str(ref.get("key") or "")
        if key not in ALL_KEYS and key not in vocab:
            fail("BODY_REF_UNKNOWN", f"key={key} not in phase vocabulary")
            bad = 1
            continue
        if key not in vocab:
            fail("BODY_REF_UNKNOWN", f"key={key} not in phase vocabulary")
            bad = 1
            continue
        seen[key] = ref
        path_s = str(ref.get("path") or "")
        exp_raw = str(ref.get("sha256") or "")
        exp = exp_raw.lower()
        if not exp_raw:
            fail(
                "BODY_REF_SHA256",
                f"key={key} sha256 missing (need 64 hex or typed pending)",
            )
            bad = 1
            continue
        if exp == PENDING_SHA:
            if key not in PENDING_ALLOWED_KEYS:
                fail(
                    "BODY_REF_SHA256",
                    f"key={key} sha256=pending not allowed "
                    f"(pending only for {sorted(PENDING_ALLOWED_KEYS)})",
                )
                bad = 1
                continue
            if not path_s:
                fail(
                    "BODY_REF_SHA256",
                    f"key={key} sha256=pending requires intended future path",
                )
                bad = 1
            # Creation-time: skip digest verify until Operator/first-implement fills hex.
            continue
        if not SHA256_HEX.match(exp):
            fail(
                "BODY_REF_SHA256",
                f"key={key} sha256 must be 64 lowercase hex or typed "
                f"pending (got {exp_raw!r})",
            )
            bad = 1
            continue
        if path_s:
            p = (root / path_s).resolve() if not Path(path_s).is_absolute() else Path(path_s)
            # Also try relative to root without resolve escape
            if not p.is_file():
                p = root / path_s
            if p.is_file():
                actual = sha256_file(p)
                if actual != exp:
                    fail(
                        "BODY_REF_DIGEST",
                        f"key={key} path={path_s} expected={exp} actual={actual}",
                    )
                    bad = 1
            # missing file: digest check deferred (path may be workspace-only)
            # do not BODY_REF_DIGEST on missing — create-time may precede files

    for req in REQUIRED_KEYS[phase]:
        if req not in seen:
            fail("BODY_REF_MISSING", f"phase={phase} missing ref key={req}")
            bad = 1

    if phase == "M3":
        scope = body.get("files_in_scope") or body.get("filesInScope")
        if not isinstance(scope, list) or not scope:
            fail("BODY_SCOPE", "M3 requires non-empty files_in_scope")
            bad = 1
        else:
            # Deputy E-20260809T220100Z — legacy-only scope cannot check writes.
            paths: list[str] = []
            for item in scope:
                if isinstance(item, str):
                    paths.append(item)
                elif isinstance(item, dict):
                    for k in ("legacy", "src", "source", "dest", "dst", "destination"):
                        if item.get(k):
                            paths.append(str(item[k]))
            has_legacy = any(
                "/.derived/legacy" in p or "/legacy-" in p for p in paths
            )
            has_dest = any(
                "/modernized/" in p or p.startswith("/projects/modernized")
                for p in paths
            )
            if has_legacy and not has_dest:
                fail(
                    "BODY_SCOPE_DEST",
                    "M3 files_in_scope needs destination paths (not legacy-only)",
                )
                bad = 1

    # ER#2 F6 / §G.2 — transform class + G-2 applicability stamped into identity.
    # Silence must not skip G-2; stamp is evidence-derived, not worker-optional.
    TRANSFORM_CLASSES = frozenset({"NONE", "HARVEST", "REWRITE", "CONFIG", "OTHER"})
    G2_APPLICABILITY = frozenset(
        {"required", "not_applicable", "undetermined_pending_derive"}
    )
    if phase in ("M3", "M4", "M5"):
        identity = body.get("identity")
        if not isinstance(identity, dict):
            fail(
                "BODY_IDENTITY",
                f"phase={phase} identity missing F6 transform_class / "
                f"g2_applicability (must be object)",
            )
            bad = 1
        else:
            tc = str(identity.get("transform_class") or "").upper()
            g2 = str(identity.get("g2_applicability") or "").lower()
            if tc not in TRANSFORM_CLASSES or g2 not in G2_APPLICABILITY:
                fail(
                    "BODY_IDENTITY",
                    f"phase={phase} identity missing F6 transform_class / "
                    f"g2_applicability "
                    f"(got transform_class={tc!r} g2_applicability={g2!r})",
                )
                bad = 1

    # Deputy E-20260809T190500Z / W2 §6 completion half — M3/M4/M5 must name
    # falsifiable done-when (exit_criteria), not only refs + scope.
    if phase in ("M3", "M4", "M5"):
        exits = body.get("exit_criteria") or body.get("done_when")
        if not isinstance(exits, list) or not exits:
            fail(
                "BODY_EXIT",
                f"phase={phase} requires non-empty exit_criteria[]",
            )
            bad = 1
        else:
            for i, item in enumerate(exits):
                if not isinstance(item, dict) or not item.get("check"):
                    fail(
                        "BODY_EXIT",
                        f"phase={phase} exit_criteria[{i}] needs check + "
                        f"(cmd/expect or assert)",
                    )
                    bad = 1
                    continue
                if not (item.get("cmd") or item.get("assert")):
                    fail(
                        "BODY_EXIT",
                        f"phase={phase} exit_criteria[{i}] needs cmd or assert",
                    )
                    bad = 1

        # AD-002D — preload ≠ consultation; M3 must name a skills check.
        if phase == "M3":
            checks = {
                str(item.get("check") or "")
                for item in exits
                if isinstance(item, dict)
            }
            if "skills" not in checks:
                fail(
                    "BODY_EXIT",
                    "phase=M3 requires exit_criteria check=skills "
                    "(AD-002E: consult each preload or typed skills_unused; "
                    "silence invalid)",
                )
                bad = 1
            else:
                # Soft authoring nudge: skills assert should forbid silence /
                # false-consult (AD-002E). Missing keywords → warning-as-fail
                # only when assert present but still says silence is OK without
                # AD-002E language — keep required presence only above.
                for item in exits if isinstance(exits, list) else []:
                    if not isinstance(item, dict) or item.get("check") != "skills":
                        continue
                    assert_s = str(item.get("assert") or item.get("cmd") or "")
                    if assert_s and "skills_unused" not in assert_s:
                        fail(
                            "BODY_EXIT",
                            "phase=M3 skills assert must allow typed "
                            "skills_unused (AD-002E)",
                        )
                        bad = 1
                    if assert_s and "silence" not in assert_s.lower() and "AD-002E" not in assert_s:
                        # Prefer explicit silence-invalid / AD-002E marker.
                        fail(
                            "BODY_EXIT",
                            "phase=M3 skills assert must mark silence invalid "
                            "(AD-002E / AD-002D)",
                        )
                        bad = 1

            # S-010 Class A / Deputy E-20260810T104752Z — test scope ⇒ in-loop
            # testCompile exit (red compile must not reach Review silently).
            scope_paths = body.get("files_in_scope") or body.get("filesInScope") or []
            if isinstance(scope_paths, list):
                touches_tests = any(
                    isinstance(p, str) and "/src/test/" in p.replace("\\", "/")
                    for p in scope_paths
                )
            else:
                touches_tests = False
            if touches_tests and "test_compile" not in checks:
                fail(
                    "BODY_EXIT",
                    "phase=M3 with src/test in files_in_scope requires "
                    "exit_criteria check=test_compile "
                    "(cmd: mvn -q test-compile; in-loop invariant — "
                    "governance/contracts/test-toolchain.md)",
                )
                bad = 1

            # Deputy E-20260810T025100Z — exit criteria must not require paths
            # outside files_in_scope (S-003: jpa_entities needed pom.xml OOS).
            # Architect:rule-body-self-consistency may tighten further; this is
            # the authoring-time catch for known pom-implying checks + explicit
            # pom.xml mentions in cmd/assert text.
            scope = body.get("files_in_scope") or body.get("filesInScope") or []
            scope_paths: list[str] = []
            for item in scope:
                if isinstance(item, str):
                    scope_paths.append(item)
                elif isinstance(item, dict):
                    for k in ("legacy", "src", "source", "dest", "dst", "destination"):
                        if item.get(k):
                            scope_paths.append(str(item[k]))
            scope_text = "\n".join(scope_paths)
            has_pom = any(p.endswith("pom.xml") or p.endswith("/pom.xml") for p in scope_paths) or (
                "pom.xml" in scope_text
            )
            pom_implied_checks = {"quarkus_pom", "jpa_entities"}
            needs_pom = bool(checks & pom_implied_checks)
            for item in exits if isinstance(exits, list) else []:
                if not isinstance(item, dict):
                    continue
                blob = " ".join(
                    str(item.get(k) or "") for k in ("cmd", "assert", "expect", "check")
                )
                if "pom.xml" in blob:
                    needs_pom = True
            if needs_pom and not has_pom:
                fail(
                    "BODY_SCOPE_EXIT",
                    "exit_criteria imply pom.xml but files_in_scope omits it "
                    "(add dual-path pom; do not force workers to breach scope)",
                )
                bad = 1

        # F6 — when G-2 applies, M4/M5 consumers must name check=g2 (silence ≠ skip).
        if phase in ("M4", "M5") and isinstance(body.get("identity"), dict):
            g2 = str(body["identity"].get("g2_applicability") or "").lower()
            if g2 in {"required", "undetermined_pending_derive"}:
                checks = {
                    str(item.get("check") or "")
                    for item in (exits if isinstance(exits, list) else [])
                    if isinstance(item, dict)
                }
                if "g2" not in checks:
                    fail(
                        "BODY_G2",
                        f"g2_applicability={g2} requires exit_criteria "
                        f"check=g2 (M4/M5; F6 / §G.2)",
                    )
                    bad = 1

        # Architect E-104925Z / E-110403Z — measured operand denominator.
        if phase == "M3":
            if _operand_count_rc(label, body) != 0:
                bad = 1

    return bad


def main() -> int:
    # Operator E-20260811T124000Z: create-path validates THE body being created
    # (--body PATH). Whole-corpus scan remains the default (R0 / board lint).
    args = sys.argv[1:]
    only: list[Path] = []
    pos: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in ("--body", "--only") and i + 1 < len(args):
            only.append(Path(args[i + 1]))
            i += 2
            continue
        if args[i].startswith("-"):
            print(f"FAIL: unknown flag {args[i]}", file=sys.stderr)
            return 1
        pos.append(args[i])
        i += 1
    root = Path(pos[0] if pos else ".").resolve()
    files: list[Path] = []
    if only:
        for p in only:
            path = p if p.is_absolute() else (root / p)
            path = path.resolve()
            if not path.is_file():
                print(f"FAIL: --body not a file: {path}", file=sys.stderr)
                return 1
            files.append(path)
    else:
        for d in (
            root / "evidence/tasks",
            root / "evidence/bodies",
            root / "evidence/kanban",
        ):
            if d.is_dir():
                files.extend(sorted(d.glob("*.json")))
    pairs: list[tuple[str, dict]] = []
    for f in files:
        try:
            pairs.extend(bodies_from(f))
        except Exception as e:
            try:
                rel = f.relative_to(root)
            except ValueError:
                rel = f
            print(f"FAIL: {rel}: {e}", file=sys.stderr)
            return 1

    if not pairs:
        print("OK: no Kanban body artifacts — §6.1 body lint idle")
        return 0

    bad = 0
    for label, body in pairs:
        rel = label.replace(str(root) + "/", "")
        bad |= check_body(rel, body, root)

    if bad:
        print(f"Kanban body checks FAILED ({len(pairs)} body(ies)).", file=sys.stderr)
        return 1
    scope = "single-body" if only else "corpus"
    print(f"OK: Kanban body §6.1 checks passed ({len(pairs)} body(ies); {scope}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
