# Tasks template (copy the structure exactly — the plan lint enforces it)

```markdown
# <Migration name> Tasks

#### T-001: <title>
**Class**: rewrite | infer
**Findings**: <rule-id> (<incident count>), ...
**Goal**: <one sentence>
**Target design** (infer tasks — REQUIRED, cite MAPPINGS.md):
- <legacy file> → <destination file>
- <signatures / annotations / decided shapes>
**Acceptance**: <files expected>; sensors green

#### T-002: ...
```

Rules the lint enforces: 3–6 hash headings with `T-NNN:` ids; a Class
marker per task; rewrite tasks before infer tasks; every infer task
carries file mappings/signatures; every mandatory finding mapped; the
legacy UI surface covered or explicitly waived (note: the demo
acceptance overrides a waive at M5 ship).
