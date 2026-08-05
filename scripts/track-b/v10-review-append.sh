#!/usr/bin/env bash
# O-REVIEWAPPEND / W4-559 — append-only write to Wave-5 review doc.
# Usage: bash scripts/track-b/v10-review-append.sh [path] <<'MD'
# ...markdown...
# MD
#
# Portable exclusive lock via O_EXCL (macOS has no flock). Append-only —
# never rewrite the whole file (prevents silent lost updates).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOC="${1:-$ROOT/tmp/KAI-WAVE5-REVIEW.md}"
mkdir -p "$(dirname "$DOC")"
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT
cat >"$BODY_FILE"
python3 - "$DOC" "$BODY_FILE" <<'PY'
import os, sys, time
from pathlib import Path

doc = Path(sys.argv[1])
body = Path(sys.argv[2]).read_text(encoding="utf-8")
lock = Path(str(doc) + ".lock")
if not body.startswith("\n"):
    body = "\n" + body
if not body.endswith("\n"):
    body += "\n"

deadline = time.time() + 30.0
while True:
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n")
        break
    except FileExistsError:
        if time.time() > deadline:
            print(f"v10-review-append: lock timeout on {lock}", file=sys.stderr)
            sys.exit(2)
        try:
            if time.time() - lock.stat().st_mtime > 120:
                lock.unlink(missing_ok=True)
                continue
        except FileNotFoundError:
            continue
        time.sleep(0.05)

try:
    before = doc.stat().st_size if doc.is_file() else 0
    with doc.open("a", encoding="utf-8") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    after = doc.stat().st_size
    print(f"v10-review-append: ok before={before} after={after} path={doc}")
finally:
    lock.unlink(missing_ok=True)
PY
