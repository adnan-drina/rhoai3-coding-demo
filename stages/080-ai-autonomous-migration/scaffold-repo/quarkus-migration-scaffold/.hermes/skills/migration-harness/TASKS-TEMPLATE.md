# Tasks template — typed M3 (write-inversion)

**Seats do not author this file.** Under `M3_TYPED_LOOP=1` (default):

1. Harness `assign_tasks` / `render-tasks` owns `specs/<S0N-slug>/tasks.md`.
2. The coding seat returns **JSON judgment only** (`unit_keys`, `goal`, `plan`, `risk`).
3. Harness `upsert_task_judgment` merges judgment into `migration/model.json` and re-renders.
4. Editing or writing `specs/**` or `migration/**` is refused (`REFUSED:F-no-spec-edit`).

Do **not** copy prose task headings into the workspace. Do **not** invent
`id` or `Acceptance` (refused: `F-taskid-generated` / `F-acceptance-derived`).
Do **not** use legacy `T-NNN:` heading grammar — live ids are `S0N-T-NNN-Slug`
and plan-lint reads the typed store, not markdown headings.

## Judgment shape (seat reply)

```json
{
  "unit_keys": ["org.example.legacy.Type"],
  "goal": "<one sentence ≥ 20 chars from brief + SNIPPET>",
  "plan": "<short plan>",
  "risk": "low|medium|high"
}
```

## Rendered task view (harness-owned — for humans / lint)

The markdown below is **illustrative of the rendered view only**. Seats never
write it; skills that still mention “copy the structure” are obsolete.

```markdown
# <Migration name> Tasks

#### S0N-T-001-Slug: <title>
**Class**: harvest | redesign | …
**Port**: carry | reimplement | …
**Shape**: create | …
**Goal**: <from seat judgment>
**Acceptance**: <harness-derived — never seat-authored>
```
