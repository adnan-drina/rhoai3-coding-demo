# M3 typed judgment seat (write-inversion)

**This is the only skill file typed M3 Qwen seats should load**
(`M3_TYPED_LOOP=1`, default). Do **not** follow [PLANNING.md](PLANNING.md)
or the legacy “edit `tasks.md` first” runbook — that path is for
`M3_TYPED_LOOP=0` MiniMax/wchat authoring only.

## Contract

1. The harness already owns task **id**, **Acceptance**, **Class/Shape/Port**,
   and the rendered view at `specs/<S0N-slug>/tasks.md` (example:
   `specs/S04-rest-surface-and-configuration/tasks.md` — never `004-…`).
2. Your packet (argv) already inlines the story brief + DERIVED FACTS /
   SNIPPETs + bounded **STAGING FACTS** (ADR-41 Move 2 / F-staging-projected)
   when HARVEST acceptance needs byte-fidelity. Do **not** Read
   `migration/briefs/**`, `migration/staging/**`, `/projects/legacy`,
   prompt files, or `TASKS-TEMPLATE.md`.
3. Reply with **JSON only** — no file edits, no tools required:

```json
{
  "unit_keys": ["<exact keys from the packet>"],
  "goal": "<one sentence ≥ 20 chars from brief + SNIPPET>",
  "plan": "<short plan>",
  "risk": "low|medium|high"
}
```

4. Forbidden (harness refuses):
   - inventing `id` or `acceptance` → `REFUSED:F-taskid-generated` /
     `REFUSED:F-acceptance-derived`
   - Read of own prompt → `REFUSED:F-packet-by-value`
   - Read of `/projects/legacy` → `REFUSED:F-no-discovery`
   - Read of `migration/briefs/**` → `REFUSED:F-brief-projected`
   - edit/write of `specs/**` or `migration/**` → `REFUSED:F-no-spec-edit`

## Slug grammar (one definition)

Story directories are always `S0N-<kebab-slug>` (from
`migration/briefs/S0N-*.md`). There is no `NNN-` / zero-padded form.
