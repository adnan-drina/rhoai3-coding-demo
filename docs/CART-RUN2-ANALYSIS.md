# Cart migration run #2 — deep analysis log

Method: after every phase/task event, the operator (Claude) reviews the
generated artifacts directly (git diffs, specs, run-log rows), reads the
Hermes session transcript for that stage, and inspects worker sessions in
opencode.db. Entries are appended live; nothing here is inferred from
supervisor log lines alone.

- Run: cart service (Spring Boot 2.7 → Quarkus), fresh baseline `9c18fcd`
- Started: 2026-07-26 21:47 UTC; supervisor v-1b269b90 (full N1–N4 stack)
- Seats: MiniMax M2 orchestrator / Qwen3.6-27B worker
- Contract deltas vs run #1: escalation acceptance bars (N1),
  `preserve: [CATALOG_ENDPOINT]` (N2 — lint + pre-flight enforced),
  wiring invariants (N3), escalation KPI reconciliation (N4), worker
  tool-discipline rules (subagent ban, glob guidance, path quoting)
- Prior attempt preserved on branch `run-1-attempt`; its opencode.db
  archived as `opencode-run1.db`

---

## Entries

### 21:47 — Launch
Supervisor start verified (version stamp, run base, seats logged).
Isolated Maven repo seeding. Analysis JSON present in
`legacy/.vscode/mta-core/` (20 rules / 35 incidents baseline, reviewed
before run #1).

### 21:48 — Phase A (script step) — VERIFIED
Commit `4d49ac9`. Artifact read directly: `migration/mta-findings.json`
parses as konveyor JSON with exactly 20 rules / 35 incidents — identical
to the pre-run review of the user's analysis (no drift, no truncation).
Commit message embeds the scripted summary. Elapsed within the launch
minute (vs ~20-min model sessions in runs 1–3). No model involvement by
design — nothing to analyze on the Hermes/model side for this phase.

### 21:56 — Phase B (M2 session) + lint rejection — REVIEWED
Commit `2c8b537`; post-commit task sensor GREEN (supervisor-verified).
Artifacts read directly:
- 20 task headings; **id discipline failed**: `T-006` used for two
  different tasks (heading-level duplicate), and the lint flagged every
  task for a missing `**Class**` marker — 19 distinct LINT:ids findings.
- **The preserve contract worked at authoring time**: `CATALOG_ENDPOINT`
  appears 4× in tasks.md (mapped to a task) — the lint's N2 check passed
  on the first plan. First live success of that mechanism.
- Transcript facts: the session read `MAPPINGS.md` and referenced the
  tasks template — read exposure did NOT produce format compliance
  (Class markers omitted everywhere). Deterministic lint remains the
  only reliable format guarantee; the revision round is dispatching.
Duplicate-id detection is a lint gap: `plan-lint.py` checks parseability
and Class, not uniqueness — T-006×2 would corrupt the task loop's
committed() checks. Adding a `dup-ids` lint check is required before the
task loop starts.

### 22:07–22:20 — Post-revision lint: MY CHECK WAS THE DEFECT — fixed
The second revision "failed" with 28/28 missing Class markers. Artifact
read shows M2 writes `- **Type:** `Class: rewrite`` — compliant in
substance; my regex demanded my exact syntax. Two revision sessions were
wasted on a false lint. Fixed (substance-over-syntax detection) and
re-run against the same plan: 27/28 tasks pass; TRUE findings are
T-005 (no class), T-020..T-028 minus T-022 (design-less tail tasks), and
`spring-components-00002` unmapped. Also fixed this cycle: id-uniqueness
check (T-006 duplication in the first plan — heading dedup happened in
revision 2 on its own). Supervisor being relaunched with the enforced
in-loop sonar build; its lint gate re-runs revision against the true
findings with a fresh budget.
Accountability note: this is the second instrument defect (after the
star-file confusion) that burned model budget. Instrument verification
before deployment (X1 test suite) is no longer optional-parked in
priority terms.
