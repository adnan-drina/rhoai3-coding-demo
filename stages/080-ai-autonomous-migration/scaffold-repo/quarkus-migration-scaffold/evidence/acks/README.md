# Stage-advance acks (AD-H §16.3 / 5.1)

Place ack files here. Schema:
`.hermes/skills/harness/enforce-authority-boundary/references/ack-authority.md`.

| File pattern | Before | Who signs |
|--------------|--------|-----------|
| `m1-findings.ack.yaml` | M1 → M2 | **5.1 gate-record** — `issue-m1-findings-ack.py` writes `acknowledged_by: gate:check-findings-handoff` when `check-findings-handoff.py` rc=0. Not a human GO. rc≠0 still typed-blocks. |
| `m3-brief-identity.ack.yaml` (and `brief-identity.ack.yaml`) | First IMPLEMENT | **5.1 gate-record** — `issue-m3-brief-identity-ack.py` writes `acknowledged_by: gate:check-body-digest-match` when `check-body-digest-match.py` passes on every minted body. Not a human GO. rc≠0 names the mismatching body. |

Do not commit live acknowledged acks with real operator names into the golden
scaffold — only the schema/README. Per-run repos get real acks in the workspace.

Example **5.1 gate-record** (placeholders only; block-mapping digests are valid YAML):

```yaml
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: gate:check-findings-handoff
acknowledged_at: 2026-08-19T00:00:00Z
task_id: t_example
gate_rc: 0
artifact_digests:
  evidence/mta-findings.json: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  evidence/findings-handoff.json: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
```

`brief-identity` example is the same 5.1 shape (placeholders only):

```yaml
kind: migration-ack
ack_type: brief-identity
status: acknowledged
acknowledged_by: gate:check-body-digest-match
acknowledged_at: 2026-08-20T00:00:00Z
task_id: t_example
gate_rc: 0
artifact_digests:
  evidence/bodies/m3-setup.json: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
```

## Provision / permissions (F-M1.5)

- Keep `evidence/acks/` **owner-writable** (`chmod u+rwx`) so the 5.1 issuers
  and Operator can write `*.ack.yaml`. `README.md` may stay mode 444.
- Each issuer chmod-unlocks `evidence/acks/` only long enough to write its
  grant, then re-locks. Do **not** leave the directory unlocked.
- Worker write-fence may lock this directory mid-run — unlock with
  `bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh unlock`
  before a **human** grant on rc≠0, then re-lock if policy requires.
- Bare `m1-findings.json` / `brief-identity.json` worker grants are **not**
  authoritative (AR-1.1).
