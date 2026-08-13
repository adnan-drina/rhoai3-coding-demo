# Body immutability after dispatch

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Rule

Once a Kanban task is created with an AR-4.3 body digest, the typed body file
and that digest are **immutable for the life of the task**.

- Mid-run edits to `evidence/bodies/*.json` (including “helpful” stamps) are
 **FORBIDDEN**.
- Later authoring belongs on the **next** dispatch only.
- Digest mismatch ⇒ **REFUSE** (worker/harness), not silent proceed.

## Check

```bash
# Own-body sidecar (exit_criteria / complete — )
python3 .hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py . \
 --body evidence/bodies/m3-s-010.json

# Explicit expect (card Body digest line)
python3 .hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py . \
 --body evidence/bodies/m3-s-010.json \
 --expect 1a117038a78e4c725f191fe654bf01d73747dce534e66a79886546cac3050bf3

# Harness inventory only — whole-corpus sidecar scan (not an exit criterion)
python3 .hermes/enforcement/record-run-evidence/scripts/check-body-digest-match.py .
```

Also covered by `check-run-digests.py` sidecar drift scan. See
`body-digest-own-story.md`.
