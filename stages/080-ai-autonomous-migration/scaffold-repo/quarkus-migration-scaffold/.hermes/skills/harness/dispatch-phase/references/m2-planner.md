# M2 planner body contract

Architect `E-20260817T203500Z` / `E-20260817T200540Z`. The created M2
card instructs the worker to, in order:

0. Init/load checkpoint (V34-3, same script as the holder):
   `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py init --kind m2 --root /projects/modernized`
   (uses `HERMES_KANBAN_TASK`). Resume at checkpoint `next`. Stamp after
   each step (`--next preseed|findings|inventory|speckit|assemble|done`).
   Before Done: `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py check --kind m2 --root /projects/modernized`
1. Spec Kit preseed verify-or-BLOCK (provision owns `specify init`).
2. Findings-handoff gate. Then 5.1
   `python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m1-findings-ack.py`
   — auto-issue `m1-findings.ack.yaml` as a gate-record. Do **not**
   `needs_input` for a human yaml. **M3 brief-identity** is the same
   5.1 pattern (`issue-m3-brief-identity-ack.py` /
   `gate:check-body-digest-match`).
3. Read `evidence/entry-point-inventory.json`, `evidence/type-inventory.json`,
   and `evidence/required-extensions.json` **before** `/speckit-specify`.
   Spec FR enumerates every inventory `http_path` (not a count). Cover every
   **source** type-inventory `dest_file` as a repository-relative `.java`
   Create. Generated types (classified at read time by `generated_sources`,
   not a stored boolean) carry the spec + configure
   the dest generator — do not Create their `.java`. Setup T001 must name
   every artifactId in `required-extensions.json` (T-3 native rewrite).
4. Spec Kit resume ladder (`specify` → `plan` → `tasks`). Resource task
   lines emit literal `@Path("...")` with the inventory path.
5. Stop — no dest `partition.json`, no M3 children. Before Done, run
   `python3 .hermes/skills/harness/dispatch-phase/scripts/scratch-assemble-mint.py`
   (copy `tasks.md` + `evidence/` to a throwaway
   dir, `python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py --write` there, then
   `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-partition-invented-routes.py` on that receipt).
   When scratch has `legacy-at-3`, that oracle also runs
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py`
   and `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py`
   on minted bodies (V34-8; same graph as M3; no second gate), then
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py`
   (M2 must not complete with a partition the holder would refuse), then
   `python3 .hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py`
   (MULTI_OWNER fails M2 assemble, not the holder). Exit 0. Invented
   routes (`union(stories[].endpoints) - inventory`) are refuse — the only
   plan-level HTTP gate (Architect `070430Z`).    Type-inventory **source** dest twins are covered when that file is present
   (`types_uncovered`; skip dest twins `generated_sources` classifies as
   generated — do not trust a stored `generated: true` boolean). Generated types stamp
   `provider: generated`; closure requires generator inputs (spec + build)
   owned (`GENERATOR_INPUTS`). Scratch also refuses if generated types
   exist and `tasks.md` has no generator plugin token (V35-M2-UPTAKE;
   T013 already requires configure-in-pom). V34-8 stamp +
   assert-dependency-closure remains the backstop. Constitution VII is guidance, not
   a gate. `--dry-run` is not this gate. Do not grow `handover-mint.py`. Keep
   code-level `assert-compiled-route-fidelity.py` (compiled `.bak`). Holder follows
   `mint-m3-hermes.md`.
