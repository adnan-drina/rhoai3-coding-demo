# Migration examples (non-operative)

Neutral examples only. **Do not** ship operative M3 specimen bodies under
`evidence/bodies/` (R-HX.15 / Operator E-20260811T113700Z).

M3/M4 bodies are written by `.hermes/kernel/k4_convert.py` from the sealed
`evidence/planning/worklist.json` (one card per step: the head cluster) and an ADMITTED
`evidence/planning/admission-receipt.json`, then minted by
`.hermes/kernel/k4_mint.py` (`hermes kanban create --body`). Planning
contracts live in `.hermes/planning/` (schemas, catalogs, MTA rules).
There is no `governance/` folder, no partition file, and no task list to
scrape for write-sets. Do not dest-apply K4.
