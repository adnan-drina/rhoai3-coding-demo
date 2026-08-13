# Human checkpoint acks (AD-H §16.3)

Place ack files here. Schema: `governance/schemas/ack.md`.

| File pattern | Before |
|--------------|--------|
| `m1-findings.ack.yaml` | M1 → M2 |
| `brief-identity.ack.yaml` or `brief-identity-<story_id>.ack.yaml` | First IMPLEMENT for that story (Operator only — never worker `brief-identity.json`) |

Do not commit live acknowledged acks with real operator names into the golden
scaffold — only the schema/README. Per-run repos get real acks in the workspace.

## Provision / permissions (F-M1.5)

- Keep `evidence/acks/` **owner-writable** (`chmod u+rwx`) so Operator/Lead can
  write `*.ack.yaml` out of band. `README.md` may stay mode 444.
- Worker write-fence may lock this directory mid-run — Operator unlocks with
  `bash .hermes/enforcement/enforce-authority-boundary/scripts/apply-write-fence.sh unlock`
  before granting stage-advance acks, then re-locks if policy requires.
- Bare `m1-findings.json` / `brief-identity.json` worker grants are **not**
  authoritative (`ack.md` / AR-1.1).
