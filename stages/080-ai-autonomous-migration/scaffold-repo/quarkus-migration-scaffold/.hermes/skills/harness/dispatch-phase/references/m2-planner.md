# M2 planner body contract

Architect `E-20260817T203500Z` / `E-20260817T200540Z`. The created M2
card instructs the worker to, in order:

1. Spec Kit preseed verify-or-BLOCK (provision owns `specify init`).
2. Findings-handoff gate.
3. Read `evidence/entry-point-inventory.json` **before** `/speckit-specify`.
   Spec FR enumerates every inventory `http_path` (not a count).
4. Spec Kit resume ladder (`specify` → `plan` → `tasks`). Resource task
   lines emit literal `@Path("...")` with the inventory path.
5. Stop — no dest `partition.json`, no M3 children. Before Done, run
   `scratch-assemble-mint.py` (copy `tasks.md` + `evidence/` to a throwaway
   dir, `handover-mint.py --write` there, exit 0). `--dry-run` is not this
   gate. Holder follows `mint-m3-hermes.md`.
