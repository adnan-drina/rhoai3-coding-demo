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

## M4/M5 — mechanical checks (fresh workspace)

- SONAR_TOKEN + SONAR_HOST auto-mounted in the new workspace (the
  namespace secret mount works without manual steps — run #2's manual
  provisioning is no longer needed). ✓
- Supervisor task-id parser reads all S01 task headings (parity with
  plan-lint held after the earlier fix). ✓
- Sensor machinery (cold isolated-repo seed + task sensor): running.
- **Design note for the outer loop** (found by inspection, not yet
  code): the preflight `preserved_integrations` check greps src/main
  for every preserve item — on a per-story M5 this fails before the
  story that introduces the item (CATALOG_ENDPOINT arrives with S02).
  The outer loop must scope preserve checks to stories at/after the
  owning story (or defer to deploy-story preflights).
