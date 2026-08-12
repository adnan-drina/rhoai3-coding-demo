# Completion consumer — reject N/A self-amend

**Law:** Operator `E-20260811T120200Z` / Architect `E-20260811T115550Z`.

Workers may **satisfy** or typed-**BLOCK** binding Done criteria. They must **never**
rewrite a criterion to N/A / not-applicable and `kanban_complete`.

## Gate

```bash
python3 .hermes/skills/harness/phase-dispatch/scripts/check-completion-na-reject.py \
  --task-id t_…   # or --text / --file
```

- Exit **0** — OK
- Exit **1** — REJECT → `needs_input` (Lead/Review reclaim + block if already completed)
- Exit **2** — harness/usage error
