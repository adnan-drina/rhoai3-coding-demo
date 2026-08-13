#!/usr/bin/env python3
"""AD-H §19.1 — reconstruct audit packet from an IMPLEMENT commit (fail closed).

Start at any Quarkus IMPLEMENT commit (subject carries task_id). Rebuild:

  packet · loci · skill/SOUL tips · session · gates · approval

Exit 0 only when every mandatory link is recovered with digests/ids.
Missing mandatory link → exit 1 (fail closed). Never invent session ids,
acks, or gate rows.

Usage:
  reconstruct-from-commit.py <repo-root> [<commit-ish>] [-o packet.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TASK_RE = re.compile(r"\b(t_[0-9a-fA-F]{6,})\b")
MANDATORY_LINKS = (
    "task_id",
    "packet",
    "loci",
    "soul_sha",
    "skill_tips",
    "session",
    "gates",
    "approval",
)


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_task_id(subject: str, body: str = "") -> str | None:
    for text in (subject, body):
        m = TASK_RE.search(text or "")
        if m:
            return m.group(1)
    return None


def skill_tree_sha(repo: Path, commit: str, skill: str) -> str | None:
    path = f".hermes/skills/{skill}"
    try:
        # Prefer tree oid of the skill directory at commit
        out = run_git(repo, "ls-tree", commit, path)
    except subprocess.CalledProcessError:
        return None
    if not out:
        return None
    # format: <mode> tree|blob <sha>\t<path>
    parts = out.split()
    if len(parts) >= 3:
        return parts[2]
    return None


def find_provenance(repo: Path, task_id: str) -> tuple[Path | None, dict | None]:
    candidates = [
        repo / "evidence" / "provenance" / f"{task_id}-provenance.json",
        repo / "evidence" / "provenance" / f"{task_id}.json",
    ]
    for path in candidates:
        data = load_json(path)
        if isinstance(data, dict):
            return path, data
    prov_dir = repo / "evidence" / "provenance"
    if prov_dir.is_dir():
        for path in sorted(prov_dir.glob("*.json")):
            data = load_json(path)
            if isinstance(data, dict) and data.get("task_id") == task_id:
                return path, data
    return None, None


def find_task_packet(repo: Path, task_id: str) -> tuple[Path | None, dict | None]:
    for d in ("evidence/tasks", "evidence/kanban"):
        base = repo / d
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.json")):
            data = load_json(path)
            items = data if isinstance(data, list) else [data]
            for obj in items:
                if not isinstance(obj, dict):
                    continue
                if obj.get("id") == task_id or obj.get("task_id") == task_id:
                    return path, obj
    return None, None


def session_anchors(repo: Path, task_id: str, prov: dict | None) -> dict:
    """Locate Hermes session / kanban log for task_id — never invent."""
    found: dict = {
        "worker_session_id": None,
        "session_paths": [],
        "kanban_log": None,
        "ok": False,
        "gaps": [],
    }
    sess = None
    if isinstance(prov, dict):
        sess = (
            prov.get("worker_session_id")
            or prov.get("workerSessionId")
            or prov.get("session_id")  # export may use alias; still must resolve
        )
    found["worker_session_id"] = sess

    home = Path.home() / ".hermes"
    candidates: list[Path] = []
    if sess:
        candidates.extend(
            [
                home / "sessions" / str(sess),
                home / "sessions" / f"{sess}.json",
                home / "sessions" / f"{sess}.jsonl",
            ]
        )
    # Kanban log is a secondary surface (§7.5 join) — not a substitute for
    # worker_session_id, but recorded when present.
    kanban_log = home / "kanban" / "logs" / f"{task_id}.log"
    if kanban_log.is_file():
        found["kanban_log"] = {
            "path": str(kanban_log),
            "sha256": sha256_file(kanban_log),
            "bytes": kanban_log.stat().st_size,
        }

    for c in candidates:
        if c.exists():
            found["session_paths"].append(
                {
                    "path": str(c),
                    "sha256": sha256_file(c) if c.is_file() else None,
                    "is_dir": c.is_dir(),
                }
            )

    # Fail closed: §19 requires Hermes-stamped worker_session_id AND a
    # resolvable session store entry. Alias session_id alone + kanban log
    # is incomplete (named gap) — not a PASS.
    if not sess:
        found["gaps"].append("missing_worker_session_id")
    elif not found["session_paths"]:
        found["gaps"].append("session_store_unresolved")
        # If only alias session_id present (not worker_session_id), note it
        if isinstance(prov, dict) and not (
            prov.get("worker_session_id") or prov.get("workerSessionId")
        ):
            found["gaps"].append("worker_session_id_alias_only")
    else:
        found["ok"] = True
    return found


def loci_from_prov(prov: dict | None) -> dict:
    out: dict = {"ok": False, "brief_or_story_id": None, "legacy_locus": None, "gaps": []}
    if not isinstance(prov, dict):
        out["gaps"].append("missing_provenance")
        return out
    cites = prov.get("citations") or prov.get("citation") or {}
    if not isinstance(cites, dict):
        cites = {}
    brief = (
        cites.get("brief_or_story_id")
        or cites.get("brief_id")
        or cites.get("story_id")
        or prov.get("brief_id")
        or prov.get("story_id")
    )
    locus = cites.get("legacy_locus") or cites.get("locus")
    legacy_block = prov.get("legacy_locus")
    if locus is None and isinstance(legacy_block, (str, dict)):
        locus = legacy_block
    out["brief_or_story_id"] = brief
    out["legacy_locus"] = locus
    if not brief:
        out["gaps"].append("missing_brief_or_story_id")
    if not locus:
        out["gaps"].append("missing_legacy_locus")
    out["ok"] = not out["gaps"]
    return out


def skill_tips_ok(repo: Path, commit: str, prov: dict | None) -> dict:
    """skill_tips must be name→git sha for phase skills (AD-H §19.2)."""
    out: dict = {"ok": False, "tips": {}, "computed": {}, "gaps": []}
    tips = {}
    if isinstance(prov, dict):
        tips = prov.get("skill_tips") or prov.get("skillTips") or {}
    if not isinstance(tips, dict) or not tips:
        out["gaps"].append("missing_skill_tips")
        return out
    out["tips"] = tips
    # Accept either already-sha values or nested tip objects — but nested
    # narrative without git sha is a gap (fail closed for reconstruct).
    bad = []
    for name, val in tips.items():
        computed = skill_tree_sha(repo, commit, name)
        if computed:
            out["computed"][name] = computed
        if isinstance(val, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", val):
            continue
        # nested object / tip prose — not a git sha
        bad.append(name)
    if bad:
        out["gaps"].append(f"skill_tips_not_git_sha:{','.join(bad)}")
    out["ok"] = not out["gaps"]
    return out


def soul_at_commit(repo: Path, commit: str, prov: dict | None = None) -> dict:
    """Prefer provenance soul_path (loaded-path rule); else git .hermes/SOUL.md."""
    out: dict = {
        "ok": False,
        "soul_sha": None,
        "soul_path": None,
        "prov_soul_sha": None,
        "gaps": [],
    }
    if isinstance(prov, dict):
        sp = prov.get("soul_path") or prov.get("soulPath")
        if sp:
            out["soul_path"] = str(sp)
            p = Path(str(sp))
            if p.is_file():
                out["soul_sha"] = sha256_bytes(p.read_bytes())
                out["ok"] = True
                return out
            out["gaps"].append("soul_path_unreadable_at_reconstruct")
    # Fallback: committed project SOUL (may diverge from loaded path — name gap)
    try:
        blob = subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{commit}:.hermes/SOUL.md"],
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        try:
            blob = subprocess.check_output(
                ["git", "-C", str(repo), "show", f"{commit}:.hermes/home/SOUL.md"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            out["gaps"].append("soul_missing_at_commit")
            return out
        out["soul_path"] = ".hermes/home/SOUL.md"
    else:
        out["soul_path"] = ".hermes/SOUL.md"
    digest = sha256_bytes(blob)
    out["soul_sha"] = digest
    out["ok"] = True
    return out


def find_gates(repo: Path, task_id: str, story_id: str | None) -> dict:
    out: dict = {"ok": False, "verdicts": [], "gaps": []}
    vdir = repo / "evidence" / "verdicts"
    if not vdir.is_dir():
        out["gaps"].append("missing_verdicts_dir")
        return out
    for path in sorted(vdir.glob("*.json")):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        hit = False
        if data.get("task_id") == task_id:
            hit = True
        if story_id and data.get("story_id") == story_id:
            hit = True
        # an M4 verdict may only carry story_id — accept the story join
        if hit:
            out["verdicts"].append(
                {
                    "path": str(path.relative_to(repo)),
                    "sha256": sha256_file(path),
                    "phase": data.get("phase"),
                    "verdict": data.get("verdict"),
                    "g1_kill_ratio": data.get("g1_kill_ratio"),
                    "ship": data.get("ship"),
                    "story_id": data.get("story_id"),
                    "task_id": data.get("task_id"),
                }
            )
    if not out["verdicts"]:
        out["gaps"].append("no_gate_verdict_for_task_or_story")
    out["ok"] = not out["gaps"]
    return out


def find_approval(repo: Path, story_id: str | None) -> dict:
    """§19.4 — acks prove human acceptance; digests do not substitute."""
    out: dict = {"ok": False, "acks": [], "gaps": []}
    adir = repo / "evidence" / "acks"
    if not adir.is_dir():
        out["gaps"].append("missing_acks_dir")
        return out
    patterns = [
        "m1-findings.ack.yaml",
        "m1-findings.ack.yml",
        "brief-identity.ack.yaml",
        "brief-identity.ack.yml",
    ]
    if story_id:
        patterns.extend(
            [
                f"brief-identity-{story_id}.ack.yaml",
                f"brief-identity-{story_id}.ack.yml",
            ]
        )
    for name in patterns:
        path = adir / name
        if path.is_file():
            out["acks"].append(
                {"path": str(path.relative_to(repo)), "sha256": sha256_file(path)}
            )
    # Also accept any non-README ack file that mentions story_id
    for path in sorted(adir.glob("*.ack.y*ml")):
        rel = str(path.relative_to(repo))
        if any(a["path"] == rel for a in out["acks"]):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if story_id and story_id in text:
            out["acks"].append({"path": rel, "sha256": sha256_file(path)})
    if not out["acks"]:
        out["gaps"].append("missing_required_acks")
    out["ok"] = not out["gaps"]
    return out


def packet_from_sources(
    task_id: str,
    commit: str,
    subject: str,
    task_obj: dict | None,
    prov: dict | None,
    loci: dict,
) -> dict:
    """Rebuild a minimal packet view — references only (W2 §6), never invented body."""
    refs = []
    if isinstance(task_obj, dict) and isinstance(task_obj.get("body"), dict):
        body_refs = task_obj["body"].get("refs") or []
        if isinstance(body_refs, list):
            refs = body_refs
    artifacts = []
    if isinstance(prov, dict) and isinstance(prov.get("artifacts"), list):
        artifacts = prov.get("artifacts") or []
    return {
        "task_id": task_id,
        "commit": commit,
        "commit_subject": subject,
        "brief_or_story_id": loci.get("brief_or_story_id"),
        "files_in_scope": (task_obj or {}).get("files_in_scope")
        or (task_obj or {}).get("files")
        or (prov or {}).get("implementation_details", {}).get("files_modified"),
        "refs": refs,
        "artifacts": artifacts,
        "source": "task_json" if task_obj else ("provenance_export" if prov else None),
    }


def reconstruct(repo: Path, commit_ish: str) -> dict:
    commit = run_git(repo, "rev-parse", commit_ish)
    subject = run_git(repo, "log", "-1", "--format=%s", commit)
    body = run_git(repo, "log", "-1", "--format=%b", commit)
    task_id = extract_task_id(subject, body)
    result: dict = {
        "schema": "migration/audit-reconstruction/v1",
        "authority": "AD-H §19.1",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit,
        "commit_subject": subject,
        "task_id": task_id,
        "links": {},
        "mandatory_ok": {},
        "gaps": [],
        "verdict": "REFUSE",
    }
    if not task_id:
        result["gaps"].append("commit_subject_missing_task_id")
        result["verdict"] = "REFUSE"
        return result

    prov_path, prov = find_provenance(repo, task_id)
    task_path, task_obj = find_task_packet(repo, task_id)
    loci = loci_from_prov(prov)
    soul = soul_at_commit(repo, commit, prov if isinstance(prov, dict) else None)
    if isinstance(prov, dict):
        soul["prov_soul_sha"] = prov.get("soul_sha") or prov.get("soulSha")
        if soul.get("soul_sha") and soul.get("prov_soul_sha"):
            if soul["soul_sha"] != soul["prov_soul_sha"]:
                soul["gaps"].append("soul_sha_mismatch_vs_provenance")
                soul["ok"] = False
        elif not soul.get("prov_soul_sha"):
            soul["gaps"].append("provenance_missing_soul_sha")
            soul["ok"] = False
    else:
        soul["gaps"].append("missing_provenance_for_soul_crosscheck")
        soul["ok"] = False

    tips = skill_tips_ok(repo, commit, prov)
    session = session_anchors(repo, task_id, prov)
    story_id = loci.get("brief_or_story_id")
    gates = find_gates(repo, task_id, story_id if isinstance(story_id, str) else None)
    approval = find_approval(repo, story_id if isinstance(story_id, str) else None)
    packet = packet_from_sources(task_id, commit, subject, task_obj, prov, loci)
    packet_ok = bool(task_obj or prov) and bool(packet.get("brief_or_story_id"))

    result["links"] = {
        "packet": {
            "ok": packet_ok,
            "task_packet_path": str(task_path.relative_to(repo)) if task_path else None,
            "provenance_path": str(prov_path.relative_to(repo)) if prov_path else None,
            "packet": packet,
            "gaps": []
            if packet_ok
            else ["missing_task_packet_and_or_provenance_brief"],
        },
        "loci": loci,
        "soul_sha": soul,
        "skill_tips": tips,
        "session": session,
        "gates": gates,
        "approval": approval,
    }

    for key in MANDATORY_LINKS:
        if key == "task_id":
            ok = True
        elif key == "packet":
            ok = packet_ok
        else:
            ok = bool(result["links"].get(key, {}).get("ok"))
        result["mandatory_ok"][key] = ok
        if not ok:
            gaps = result["links"].get(key, {}).get("gaps") if key != "task_id" else []
            if key == "packet":
                gaps = result["links"]["packet"].get("gaps") or ["packet_incomplete"]
            result["gaps"].append(f"{key}:{','.join(gaps) if gaps else 'incomplete'}")

    result["verdict"] = "ACCEPT" if not result["gaps"] else "REFUSE"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", type=Path, help="modernized repo root")
    ap.add_argument(
        "commit",
        nargs="?",
        default=None,
        help="commit-ish (default: latest IMPLEMENT task-id commit)",
    )
    ap.add_argument("-o", "--output", type=Path, help="write reconstruction packet JSON")
    args = ap.parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        # allow worktree / linked git
        try:
            run_git(repo, "rev-parse", "--git-dir")
        except Exception:
            print(f"FAIL: not a git repo: {repo}", file=sys.stderr)
            return 1

    commit = args.commit
    if not commit:
        # Walk recent commits for first task-id subject
        log = run_git(repo, "log", "--format=%H %s", "-n", "50")
        commit = None
        for line in log.splitlines():
            sha, _, subj = line.partition(" ")
            if extract_task_id(subj):
                commit = sha
                break
        if not commit:
            print(
                "FAIL: no IMPLEMENT commit with task_id in subject (last 50)",
                file=sys.stderr,
            )
            return 1

    result = reconstruct(repo, commit)
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    if result["verdict"] == "ACCEPT":
        print(
            f"OK: reconstruction ACCEPT for {result['task_id']} @ {result['commit'][:12]}",
            file=sys.stderr,
        )
        return 0
    print(
        f"FAIL: reconstruction REFUSE (fail closed) gaps={result['gaps']}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
