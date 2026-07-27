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

## M2 SEQUENCE — running

(appended as the dry run progresses)
