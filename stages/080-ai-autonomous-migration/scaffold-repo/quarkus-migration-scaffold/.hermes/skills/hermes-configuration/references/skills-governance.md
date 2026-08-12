# Skills governance

**Official sources (cite these):**
- Skills: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
- Skill bundles (same page, §Skill Bundles)
- AD-012 / R-SK authoring law (architecture): `architecture/SOLUTION-ARCHITECTURE.md` §H.12

## Official surfaces

| Knob | Meaning |
|------|---------|
| `skills.external_dirs` | Extra skill roots scanned **in place** (not a write boundary) |
| `skills.write_approval` | Stage agent skill writes for `/skills approve` |
| Bundles | YAML manifests under skill-bundles; `instruction:` + `skills:` |
| Taps | Workshop / remote skill sources |
| Per-task injection | `kanban_create(skills=[...])` / card `skills` JSON |

## Platform pins (validated)

```yaml
skills:
  write_approval: false   # headless Kanban: true → timeout-deny (R-AD011.5)
  inline_shell: false
  external_dirs:
    - /projects/modernized/.hermes/skills
    - /home/user/.hermes/skills
```

## Authoring law (AD-012)

New/edited skills: R-SK.1–6 (layout, frontmatter ≤60-char imperative
description, When→Procedure→Verification, progressive disclosure,
conformance lint, install hygiene). Lint:

```bash
python3 .hermes/skills/harness-validate/scripts/check-skill-conformance.py . --skill NAME --strict
```

## CS-7 bundles

Phase bundles use `m<phase>-*` names only. Official "missing skills skipped"
is **FORBIDDEN** here — fail-closed exists-assert before dispatch.
