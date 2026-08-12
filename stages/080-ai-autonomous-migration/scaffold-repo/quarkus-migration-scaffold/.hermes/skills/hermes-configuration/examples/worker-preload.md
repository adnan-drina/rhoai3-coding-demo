# AD-002E / worker preload — per-task skill injection (official)

Official: attach skills on the task rather than editing the assignee profile
every time — `kanban_create(skills=[...])` / CLI `--skill`.

## Create / mint

```bash
# CLI shape (illustrative)
hermes kanban create ... --skill hermes-configuration --skill grounded-generation

# API / mint path
kanban_create(..., skills=["hermes-configuration", "grounded-generation"])
```

## When to attach `hermes-configuration`

Any card whose body or exit criteria touch `config.yaml`, Managed Scope,
`kanban.*`, `skills.*`, hooks, bundles, taps, or provider pins.

## Related Managed Scope excerpt

See also `managed-scope-pin.yaml` for `skills.external_dirs` /
`write_approval` when those keys are platform-pinned.
