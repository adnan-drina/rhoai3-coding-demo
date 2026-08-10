# Body immutability after dispatch (Architect E-20260810T111424Z)

**Status:** binding proving-min  
**Sources:** Deputy `E-20260810T111250Z` · Architect BIND · AR-4.3

## Rule

Once a Kanban task is created with an AR-4.3 body digest, the typed body file
and that digest are **immutable for the life of the task**.

- Mid-run edits to `migration/bodies/*.json` (including “helpful” stamps) are
  **FORBIDDEN**.
- Later authoring belongs on the **next** dispatch only.
- Digest mismatch ⇒ **REFUSE** (worker/harness), not silent proceed.

## Check

```bash
# Sidecar (create-time stamp) vs current body bytes
python3 .hermes/skills/auditability-repeatability/scripts/check-body-digest-match.py .

# Explicit expect (card Body digest line)
python3 .hermes/skills/auditability-repeatability/scripts/check-body-digest-match.py . \
  --body migration/bodies/m3-s-010.json \
  --expect 1a117038a78e4c725f191fe654bf01d73747dce534e66a79886546cac3050bf3
```

Also covered by `check-run-digests.py` sidecar drift scan.
