# Dry run of the redesigned migration process (M1–M5)

2026-07-27, executed autonomously on the real cart material in the
round3 workspace, on branch `dryrun-m-process` (main untouched). Method:
run each stage exactly as the automated process will, then review the
input/output quality of every artifact by hand — no claims from gate
exit codes alone. Defects found are fixed and synced (scaffold, golden,
round3) before the next stage runs.

## M1 ANALYZE — verdict: PASS (after 4 defects fixed)

**Deterministic layer** (committed `c2a799e`):
- Analysis: 24 rules / 47 incidents with the corrected contract —
  targets `quarkus, jakarta-ee9, cloud-readiness, openjdk17`, custom
  rules, NO source filter, source-only mode, Java 21.
- Inventory: 1 recipe / 15 rewrite / 8 infer / 0 OPEN DESIGN (after two
  new MAPPINGS joins); preserve candidates correctly surfaced
  (CATALOG_ENDPOINT via the demo-env-integration rule).
- Dependency order: models-first order, god nodes flagged (validated
  earlier against the tree).
- Recipe transform: first successful IN-POD execution — jakarta imports
  staged, recipe-log written.

**Defects found by this stage's dry run** (all fixed + synced):
1. **kantra had never worked in-pod** — JDTLS requires Java 21
   (`osgi.ee=JavaSE-21`); under the pod-default 17 the provider waits
   forever. This was the real cause of both earlier "wedges"; my prior
   dependency-resolution diagnosis was wrong. Supervisor now exports
   `JAVA_HOME_21` for the analysis. With it: analysis completes in
   <1 min.
2. **`--source` filtering is harmful** — A/B measured: with
   `--source springboot` 11 rules (jakarta + pom families and ALL
   custom rules silently excluded); without: 21. Source flag removed
   from contract, supervisor, and template.
3. **`jakarta-ee9` target was missing** — the jakarta family carries
   `jakarta-ee*`/`eap` labels, not `quarkus`; the old baseline only had
   them because the committed IDE profile selected `jakarta-ee`.
   Decided set now includes `jakarta-ee9`; result is a strict superset
   of the baseline (24 vs 20 rules).
4. **demo-inmemory-state rule missed plain `HashMap`** (legacy uses
   it) — widened to HashMap + ConcurrentHashMap.

**Analyst session** (M2-seat model, one session, committed `a980421`,
rubric PROFILE OK): 130-line architecture profile. Quality review:
- Strong: behavioral contract extraction (the 2000.0 / −10.99
  assertions quoted with test citations; honest gap list — shipping
  tiers and dedup logic untested); modernization surface re-keyed by
  component; in-memory persistence flagged; single-bounded-context
  conclusion correct.
- Verified against source: the "hybrid `@RestController` + JAX-RS"
  description is CORRECT (my own challenge of it was wrong — the
  legacy endpoint carries both).
- One genuine miss: `@Scope(SCOPE_SESSION)` on CartEndpoint
  (session-scoped bean — cloud-readiness nuance). Fed forward to M2
  explicitly; candidate for an ANALYSIS.md checklist item ("stereotype
  AND scope annotations on every endpoint/service").
- Known limitation (accepted): the rubric checks citation PRESENCE,
  not accuracy. Claim verification stays a review/retro concern.

## M2 SEQUENCE — verdict: PASS with operator closure (2 lint gaps hardened)

**Session** (3m46s, 88 tool calls): authored `migration/roadmap.md` + 2
briefs, then died in a repeat-call loop WITHOUT committing (hermes'
own repetition guard ended it). In the automated flow this is exactly
what run_stage retry + mechanical commit closure absorb; for the dry
run the operator played that role.

**Artifact quality — genuinely good:**
- 2 stories, natural sizing: S01 models+pom foundation (no deploy),
  S02 services+endpoint+config (deploy milestone). Order follows the
  dependency graph; done-criteria include characterization tests; the
  fed-forward `SCOPE_SESSION` fact is explicitly handled in S02's
  done-criteria ("replaced with appropriate session management
  strategy") — the M1→M2 information flow works.
- Briefs carry all template sections and 14 code-excerpt fences.

**Defects the dry run caught (both now deterministic lint checks +
suite cases, 36/36):**
1. **Non-contiguous numbering passed the lint** — the session
   renumbered mid-flight leaving S01,S03. Lint now requires S01..S0N.
2. **Prose inside the findings field counted as owned ids** ("28
   findings owned" from parenthetical class lists). Lint now accepts
   rule-id-shaped tokens only.

Closure commit `19e41d8`: ROADMAP OK — 2 stories, exactly 23 findings
owned, deploy milestone S02.

## M3 SPECIFY (S01) — session + revision cycle exercised; 1 false positive and 2 real defects → lint hardened

**Session** (committed `e0def30` autonomously): specs/S01 with
spec/plan/tasks, 10 tasks — structure good: 4 package-migration tasks
harvesting from `migration/staging/` (recipe outputs correctly
consumed), 3 characterization-test tasks with the legacy assertions
quoted (2000.0 / −10.99, shipping tiers), S02's files untouched.

**But the session committed with the lint RED** — session discipline
failure; the automated M3 gate (supervisor lint → revision dispatch)
is exactly right, and the dry run exercised it manually.

**Lint findings triaged:**
- FALSE POSITIVE (fixed): the package-identity check fired on the
  legacy package in SOURCE position ("from com.redhat.coolstore.model
  to com.demo.model" + staging paths). Check now fires only on
  TARGET-position references; from→to plans pass. Suite case added.
- REAL: T-005 "Legacy UI Surface Waiver" — a ceremonial task (T-029
  class). plan-lint now has a task-substance check (every task body
  must name a code/config path). Suite case added. (38/38.)
- REAL: stale story references — the plan cites "S03", which stopped
  existing after M2's renumbering, and waives a finding S02 owns.
  Cross-stage consistency issue; revision session dispatched with the
  exact findings.

**Revision cycle findings (two more, one of them mine):**
- **Operator-injected misinformation**: my first revision prompt told
  the session to REMOVE `springboot-web-to-quarkus-00000` "because S02
  owns it" — trusting the plan's stale waiver prose. The roadmap (the
  ownership authority) assigns it to S01; the lint immediately went
  red on the correct ground. Rule for the automated dispatcher: the
  revision prompt derives ownership claims from the ROADMAP, never
  from the plan under revision.
- **Missing pom task — the string-presence coverage limit with teeth**:
  the plan "covered" all pom-family findings by listing their ids in
  the final validation task's body; no task actually converts the pom,
  and jakarta-import models cannot compile without jakarta deps. The
  findings check (string presence) is structurally blind to this —
  documented limitation now demonstrated. Mitigation in the second
  revision (dedicated pom task FIRST); durable mitigation is M4
  itself (the first task sensor run fails compilation immediately) —
  but plan-order correctness should not wait for implementation to
  discover it. Candidate lint idea recorded: findings ids appearing
  ONLY in validation/final tasks is a smell worth flagging.

## M4/M5 — mechanical checks (fresh workspace)

- SONAR_TOKEN + SONAR_HOST auto-mounted in the new workspace (the
  namespace secret mount works without manual steps — run #2's manual
  provisioning is no longer needed). ✓
- Supervisor task-id parser reads all S01 task headings (parity with
  plan-lint held after the earlier fix). ✓
- Sensor machinery in the fresh workspace: cold seed 105M, then task
  sensor GREEN in 4s. The full M4 gate stack is operational without any
  manual provisioning. ✓
- **Design note for the outer loop** (found by inspection, not yet
  code): the preflight `preserved_integrations` check greps src/main
  for every preserve item — on a per-story M5 this fails before the
  story that introduces the item (CATALOG_ENDPOINT arrives with S02).
  The outer loop must scope preserve checks to stories at/after the
  owning story (or defer to deploy-story preflights).

## M3 closure

Second revision `807a6bd`: **PLAN OK — 10 tasks (5 rewrite / 5
infer)**, pom conversion inserted as T-001 (compile-order correct),
pom-family findings moved from the validation task to their owner,
zero stale story references anywhere in specs/. The lint→revise loop
converged in two rounds, each round on true findings.

## Verdict

**Confidence: M1→M3 are ready for the joint test run; M4/M5 machinery
is validated; the outer-loop automation is the remaining build.**

The full audit trail is on `coolstore-cart-round3` branch
`dryrun-m-process` (pushed): `M1 analyze:` ×2 → `M2 sequence:` →
`S01 spec:` + two revisions — exactly the commit narrative the
redesign promised.

**Defect ledger: 14 findings this dry run.**
Fixed and instrument-tested (suite 38/38): kantra Java-21 wedge (the
historic root cause), harmful `--source` filter, missing `jakarta-ee9`
target, HashMap rule gap, roadmap-lint contiguity, roadmap-lint
prose-in-findings, plan-lint package false positive, plan-lint
ceremonial-task gap. Fixed by revision in-flow: stale cross-stage
refs, missing pom task. Absorbed by designed mechanisms: M2 no-commit
loop (mechanical closure), M3 commit-on-red (gate + revision).
Recorded as outer-loop design rules: revision prompts take ownership
facts from the ROADMAP only; per-story preserve-check scoping.
Known accepted limits: rubric checks citation presence not accuracy;
findings coverage is string-presence (M4's first sensor run is the
backstop; validation-task-only smell noted as a lint candidate).

## V3 — S01 story run (joint test, 2026-07-27): STORY SHIPPED ITS GATE

Wall clock 12:26→15:31 (~3h). 10 tasks + 4 autonomous sensor-fix
commits + 2 operator correctives; preflight GREEN (full gate + boot);
pipeline + sonar quality gate green; **story-gate-passed (first live
non-deploy-story path)**; Phase F retro authored and committed
autonomously. Findings delta (harness-run): legacy 24/47 → destination
8/12, remaining = S02 surfaces + 3 pom rules falsifying part of
T-001's resolved-by-scaffold claim (carried as S01 debt → S02).

Interventions (2, both scope-corrections, zero truth-corrections):
serialVersionUID restore (fix-session drift), T-008 shipping-tier
calculator moved from src/main to test scope (story-scope invention).
V3 ledger: fix-session scope discipline; harvest-fidelity sensor
candidate; story-scope sensor candidate; M3 gap (service-logic
characterization in models story); same-package edges in
dependency-order; Phase D re-analysis needs to be a supervisor script
step (sessions lack the Java 21 export); session workspace hygiene
(broken stray test file); promo-composition semantics watch for S02.

## V3 — S02 launch incident (operator error, mechanism fixed)

My first S02 launch script started a supervisor even though its `git
pull` had failed; my corrected relaunch then rebased the branch (moving
the spec SHA out from under instance #1's RUN_BASE) and started
instance #2 — **two concurrent supervisors**, which produced a phantom
lint failure, a session run against the wrong story's task list, and a
"T-001" commit containing JDTLS droppings, a forbidden Quarkus main
class, and the run-#1-era wrong config key. Recovery: both killed;
contaminated commits reverted (content verified commit-by-commit);
droppings gitignored. Mechanism fixes, live-proven: **single-instance
guard** in the supervisor (second launch now refuses with FATAL) and
**STORY_TASKS as plan-stage authority** (a revert in the commit range
can no longer resurrect Phase B). Launch scripts must abort on pull
failure — mine now do.

**Not exercised, deliberately** — this is the joint test run (V3):
M4 implementation sessions on S01's 10 tasks (the most battle-tested
part of the harness, 5 runs of history), M5 factory/deploy/acceptance
live, and the per-story retro. The outer-loop supervisor (story
iteration, M-stage dispatch, the three recorded design rules) is the
one build item between the dry run and full autonomy (V4).
