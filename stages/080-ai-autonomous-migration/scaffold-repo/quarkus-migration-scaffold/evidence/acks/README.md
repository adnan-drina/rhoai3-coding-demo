# Stage-advance acks (AD-H §16.3 / 5.1)

Place ack files here. Schema:
`.hermes/skills/harness/enforce-authority-boundary/references/ack-authority.md`.

| File pattern | Before | Who signs |
|--------------|--------|-----------|
| `m1-findings.ack.yaml` | M1 → M2 | **5.1 gate-record** — `issue-m1-findings-ack.py` writes `acknowledged_by: gate:check-findings-handoff` when `check-findings-handoff.py` rc=0. Not a human GO. rc≠0 still typed-blocks. |
| `brief-identity.ack.yaml` or `brief-identity-<story_id>.ack.yaml` | First IMPLEMENT for that story | **Operator only** — never worker `brief-identity.json` |

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

`brief-identity` example stays Operator:

```yaml
kind: migration-ack
ack_type: brief-identity
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-16T00:00:00Z
task_id: t_example
artifact_digests:
  evidence/briefs/partition.json: "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
```

## Provision / permissions (F-M1.5)

- Keep `evidence/acks/` **owner-writable** (`chmod u+rwx`) so the 5.1 issuer
  and Operator can write `*.ack.yaml`. `README.md` may stay mode 444.
- The issuer chmod-unlocks `evidence/acks/` only long enough to write
  `m1-findings.ack.yaml`, then re-locks that grant. Do **not** leave the
  directory unlocked for `brief-identity`.
- Worker write-fence may lock this directory mid-run — Operator unlocks with
  `bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh unlock`
  before granting **brief-identity**, then re-locks if policy requires.
- Bare `m1-findings.json` / `brief-identity.json` worker grants are **not**
  authoritative (AR-1.1).
