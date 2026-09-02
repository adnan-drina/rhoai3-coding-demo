# Migration examples (non-operative)

Neutral examples only. **Do not** ship operative M3 specimen bodies under
`evidence/bodies/` (R-HX.15 / Operator E-20260811T113700Z).

M3 typed bodies come from the typed partition via K4 payloads consumed by
`.hermes/kernel/k4_mint.py` (`hermes kanban create --body`). See
`.hermes/kernel/k4_convert.py`.
Coverage contracts stay in `.hermes/skills/sdd/check-spec-readiness/`.
There is no `governance/` folder. Do not dest-apply K4. Do not scrape
`tasks.md` for write-sets.
