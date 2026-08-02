#!/usr/bin/env bash
# O-WAKE-CATCHUP — script-enforced review-doc catch-up (not memory).
#
# Every wake tick must absorb ALL entries after the agent's last
# "### Implementing note" — not only the final heading in the doc.
#
#   refresh  — write tmp/V10-REVIEW-SINCE-LAST.md; open PENDING if unabsorbed
#   status   — print catchup state (ok|pending)
#   ack      — clear PENDING only when a newer Implementing note exists
#              AND that note passes the O-REVIEWDOC lead contract
#              (Agent: Grok + Reviewed:/ACK: + — Grok signature).
#   check    — validate the newest Implementing note contract (exit 1 if bad)
#
# Usage (from wake emit / agent turn):
#   bash scripts/track-b/v10-review-catchup.sh refresh
#   bash scripts/track-b/v10-review-catchup.sh ack
#   bash scripts/track-b/v10-review-catchup.sh check
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REVIEW_DOC="${V10_REVIEW_DOC:-${ROOT}/tmp/KAI-WAVE4-REVIEW.md}"
SINCE_FILE="${V10_REVIEW_SINCE_LAST:-${ROOT}/tmp/V10-REVIEW-SINCE-LAST.md}"
PENDING="${V10_REVIEW_CATCHUP_PENDING:-${ROOT}/tmp/V10-REVIEW-CATCHUP-PENDING.md}"
ACK_SHA="${V10_REVIEW_CATCHUP_SHA:-${ROOT}/tmp/V10-REVIEW-CATCHUP.sha}"
MARKER='### Implementing note'

cmd="${1:-status}"

python3 - "$cmd" "$REVIEW_DOC" "$SINCE_FILE" "$PENDING" "$ACK_SHA" "$MARKER" <<'PY'
import hashlib, os, re, sys, time
from pathlib import Path

cmd, review_p, since_p, pending_p, ack_p, marker = sys.argv[1:7]
review = Path(review_p)
since = Path(since_p)
pending = Path(pending_p)
ack = Path(ack_p)

def note_starts(text: str):
    starts = []
    i = 0
    while True:
        j = text.find(marker, i)
        if j < 0:
            break
        # only at line starts
        if j == 0 or text[j - 1] == "\n":
            starts.append(j)
        i = j + len(marker)
    return starts

def extract(text: str):
    starts = note_starts(text)
    if not starts:
        return 0, -1, text  # whole doc is unabsorbed if no notes yet
    last = starts[-1]
    # after = from end of that note's heading line… actually from after the note
    # body until EOF. Use content after the last note start: the note itself is
    # "ours"; unabsorbed is everything AFTER the next ---/## boundary following
    # the note, OR simpler: everything after the last note block.
    # Practical rule: unabsorbed = text[last_note_end:] where last_note_end is
    # the start of the next ## / ### heading that is NOT a continuation, or EOF
    # if the last note is the final section.
    # Simpler durable rule matching operator intent:
    #   after_last_note = text[last:]  # includes our last note
    #   unabsorbed = text after the last note's first line, until we hit a new
    #   top-level reviewer section (## ) that is NOT "### Implementing note".
    # Even simpler (operator wording): all entries FROM the last entry YOU made
    # — i.e. everything after your last Implementing note heading's section.
    rest = text[last:]
    lines = rest.splitlines(keepends=True)
    if not lines:
        return last, last, ""
    # skip the Implementing note section until next ## heading (Poll/F/R/…)
    i = 1
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("---"):
            # blank/hr often precedes next section; keep scanning
            i += 1
            # if following is ## , break before it by continuing; content after ---
            continue
        if ln.startswith("## ") or (
            ln.startswith("### ") and not ln.startswith(marker)
        ):
            break
        i += 1
    after = "".join(lines[i:])
    after_start = last + sum(len(x) for x in lines[:i])
    return last, after_start, after

def reviewer_signal(after: str) -> bool:
    if not after.strip():
        return False
    return bool(
        re.search(
            r"(?m)^(## |### )?(Poll |Poll W4-|Review poll|F-[0-9]|W4-[0-9]|Idle note|Model-efficiency|KAI-IDLE-NUDGE)"
            r"|\*\*Verdict:\*\*|## F-[0-9]|## W4-[0-9]|## Review poll|## Poll W4-",
            after,
        )
    ) or bool(re.search(r"(?m)^## ", after))

def refresh():
    if not review.is_file():
        since.write_text("# no review doc\n", encoding="utf-8")
        if pending.exists():
            pending.unlink()
        print("ok empty (no review doc)")
        return 0
    text = review.read_text(encoding="utf-8", errors="replace")
    last_start, after_start, after = extract(text)
    fp = hashlib.sha256(after.encode("utf-8")).hexdigest()[:16]
    header = (
        f"# V10-REVIEW-SINCE-LAST — auto-refreshed by wake/catchup\n"
        f"# Rule: absorb EVERY section below (all entries after your last "
        f"Implementing note) — do NOT only read the final heading.\n"
        f"# last_note_start={last_start} after_start={after_start} "
        f"slice_bytes={len(after.encode('utf-8'))} slice_fp={fp}\n"
        f"# Clear: bash scripts/track-b/v10-review-catchup.sh ack "
        f"(requires a newer Implementing note)\n\n"
    )
    since.write_text(header + (after if after.strip() else "_empty — nothing after your last Implementing note._\n"), encoding="utf-8")
    if after.strip() and reviewer_signal(after):
        pending.write_text(
            "\n".join(
                [
                    "# V10-REVIEW-CATCHUP-PENDING — O-WAKE-CATCHUP (script-enforced)",
                    "",
                    "Unabsorbed review-doc content exists AFTER your last "
                    "`### Implementing note`.",
                    "Read `tmp/V10-REVIEW-SINCE-LAST.md` in full (every section).",
                    "Bank / act / lead. Then append an Implementing note that",
                    "passes O-REVIEWDOC (required fields):",
                    "",
                    "- `**Agent:** Grok (lead)`",
                    "- `**Reviewed:**` bullets and/or `ACK:W4-NNN` / `ACK:R-NNN` / `ACK:F-NN` / `ACK:O-*`",
                    "- live action taken (not chat-only)",
                    "- closing line `— Grok (lead)`",
                    "",
                    "Then run:",
                    "",
                    "```bash",
                    "bash scripts/track-b/v10-review-catchup.sh ack",
                    "```",
                    "",
                    f"last_note_start_at_emit={last_start}",
                    f"doc_size_at_emit={len(text.encode('utf-8'))}",
                    f"after_start_at_emit={after_start}",
                    f"slice_fp={fp}",
                    f"slice_bytes={len(after.encode('utf-8'))}",
                    f"emitted_at={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"pending slice_fp={fp} bytes={len(after.encode('utf-8'))}")
        return 2
    # caught up
    if pending.exists():
        pending.unlink()
    ack.write_text(f"{fp}\n", encoding="utf-8")
    print(f"ok empty slice_fp={fp}")
    return 0

def note_body(text: str, start: int) -> str:
    """Body of Implementing note at start (through next ## / foreign ###)."""
    rest = text[start:]
    lines = rest.splitlines(keepends=True)
    if not lines:
        return ""
    i = 1
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("## ") or (
            ln.startswith("### ") and not ln.startswith(marker)
        ):
            break
        i += 1
    return "".join(lines[:i])

def validate_lead_note(body: str):
    """O-REVIEWDOC contract for Wave-4 lead (Grok) Implementing notes."""
    errors = []
    if not re.search(r"(?im)\*\*Agent:\*\*\s*Grok(\s*\(lead\))?", body):
        errors.append("missing **Agent:** Grok (lead)")
    has_ack = bool(
        re.search(r"\bACK:(W4-\d+|R-\d+|F-\d+|O-[A-Z0-9-]+)\b", body)
    )
    has_reviewed = bool(re.search(r"(?im)\*\*Reviewed:\*\*", body))
    if not (has_ack or has_reviewed):
        errors.append(
            "missing **Reviewed:** section and/or ACK:W4-|R-|F-|O- tokens"
        )
    if not re.search(r"(?m)^—\s*Grok(\s*\(lead\))?\s*$", body):
        errors.append("missing closing signature line '— Grok (lead)'")
    return errors

def check_newest():
    if not review.is_file():
        print("FAIL: review doc missing", file=sys.stderr)
        return 1
    text = review.read_text(encoding="utf-8", errors="replace")
    starts = note_starts(text)
    if not starts:
        print("FAIL: no ### Implementing note in review doc", file=sys.stderr)
        return 1
    body = note_body(text, starts[-1])
    errors = validate_lead_note(body)
    if errors:
        print("FAIL: O-REVIEWDOC — " + "; ".join(errors), file=sys.stderr)
        return 1
    print("ok O-REVIEWDOC newest Implementing note")
    return 0

def status():
    if pending.is_file():
        print("pending")
        return 2
    print("ok")
    return 0

def ack_clear():
    if not pending.is_file():
        print("ok (no pending)")
        return 0
    if not review.is_file():
        print("FAIL: review doc missing", file=sys.stderr)
        return 1
    meta = pending.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"last_note_start_at_emit=(\d+)", meta)
    if not m:
        print("FAIL: pending missing last_note_start_at_emit", file=sys.stderr)
        return 1
    prev_last = int(m.group(1))
    text = review.read_text(encoding="utf-8", errors="replace")
    starts = note_starts(text)
    if not starts or starts[-1] <= prev_last:
        print(
            "FAIL: append a new ### Implementing note after the previous one "
            "before ack (catch-up not recorded in review doc)",
            file=sys.stderr,
        )
        return 1
    body = note_body(text, starts[-1])
    errors = validate_lead_note(body)
    if errors:
        print(
            "FAIL: O-REVIEWDOC — newest Implementing note incomplete: "
            + "; ".join(errors),
            file=sys.stderr,
        )
        return 1
    # refresh to confirm slice state
    last_start, after_start, after = extract(text)
    fp = hashlib.sha256(after.encode("utf-8")).hexdigest()[:16]
    # Allow residual empty/non-signal after the new note
    if after.strip() and reviewer_signal(after):
        print(
            "FAIL: still unabsorbed reviewer sections after your newest "
            "Implementing note — absorb those too, then re-ack",
            file=sys.stderr,
        )
        # keep pending; refresh file for agent
        refresh()
        return 1
    pending.unlink(missing_ok=True)
    ack.write_text(f"{fp}\ncleared_note_start={starts[-1]}\n", encoding="utf-8")
    since.write_text(
        f"# V10-REVIEW-SINCE-LAST — cleared\n# slice_fp={fp}\n_empty — catch-up acked._\n",
        encoding="utf-8",
    )
    print(f"cleared slice_fp={fp} new_note_start={starts[-1]}")
    return 0

if cmd == "refresh":
    sys.exit(refresh())
if cmd == "status":
    sys.exit(status())
if cmd == "check":
    sys.exit(check_newest())
if cmd == "ack":
    sys.exit(ack_clear())
print(f"usage: {sys.argv[0]} refresh|status|ack|check", file=sys.stderr)
sys.exit(2)
PY
