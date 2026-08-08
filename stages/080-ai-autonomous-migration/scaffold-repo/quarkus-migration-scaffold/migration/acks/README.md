# Human checkpoint acks (AD-H §16.3)

Place ack files here. Schema: `migration/schemas/ack.md`.

| File pattern | Before |
|--------------|--------|
| `m1-findings.ack.yaml` | M1 → M2 |
| `brief-identity.ack.yaml` or `brief-identity-<story_id>.ack.yaml` | First IMPLEMENT for that story |

Do not commit live acknowledged acks with real operator names into the golden
scaffold — only the schema/README. Per-run repos get real acks in the workspace.
