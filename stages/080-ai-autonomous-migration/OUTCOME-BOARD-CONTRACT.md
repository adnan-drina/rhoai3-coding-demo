# Outcome board — implementation contract (disabled by default)

Status: implementation contract for the approved native outcome-board design
(architect decision "APPROVE WITH CONDITIONS", 2026-09-25, findings F1–F5).
Applies to **new runs only**. Every existing run, board, deadline and evidence
record keeps the serial loop protocol. Execution stays **disabled** until the
conditions in section 8 are demonstrated.

Code: `.hermes/lib/planner/outcome_{protocol,graph,store,lifecycle}.py`,
`.hermes/kernel/{k4_graph,outcome_gate,outcome_reconcile}.py`, and a guarded
branch at the top of `.hermes/kernel/pre_tool_call.sh`. Paths below are
relative to the destination root unless they start with `.hermes/`.

## 1. Selection and gating

| Question | Answer | Where |
|---|---|---|
| Which protocol does a run use? | `configuration.board_protocol` in `run-defaults.json`. Absent means `serial-loop/v1`. The value is bound by the destination's root commit through `run_declaration.py`, so a run cannot switch it | `outcome_protocol.select_protocol` |
| Is execution allowed? | `.hermes/pins.json` `pins.planner.outcome_board.execution` ∈ `disabled` (default when absent), `qualification`, `enabled` | `outcome_protocol.execution_gate` |
| `qualification` | Honoured only when no factory run declaration exists (`RUN_DECLARATION_MISSING`): a disposable local fixture. A factory-stamped run can never enter it | same |
| `enabled` | Requires a protected authority backend (section 3). None exists in the current architecture, so `enabled` refuses with `AUTHORITY_UNPROTECTED` | same |
| Mixed state | Outcome protocol with serial-loop records (`verification/loop/issued.json` naming a K4 loop card, `k4:` mint receipts, a K1 JSON fence in an outcome card body), or serial protocol with an outcome store, refuses `PROTOCOL_MIXED` on every path | `outcome_protocol.mixed_state` |

The golden ships neither key, so the next golden behaves exactly as today.

## 2. Records and storage

One SQLite database, `verification/outcome-board/authority.sqlite3`, holds every
deciding record. JSON files beside it (`account.json`, `briefs/`) are derived
observer views; nothing reads them back as authority.

| Table | Content | Written by (transition) | Read by |
|---|---|---|---|
| `meta` | protocol version, run id, board, M2 control task, execution generation, publication/release state, ledger chain head | publish, grant, release | every check |
| `revisions` | plan revision documents (outcomes, ownership, dispositions, dependencies, unresolved rows), digest, parent, state `proposed/published/superseded` | derive, revise | publish, issue, account |
| `outcomes` | frozen identity: `outcome_id`, native key, role (`repair`/`assess`/`deliver`), generation/cycle, budget key and limit, lineage | publish (freeze) | everything |
| `ownership` | obligation id → outcome, disposition (`owned`, `satisfied`, `superseded`, `optional`, `unresolved`) per revision | derive, revise | conservation, acceptance |
| `publication` | outcome → native task id, expected fields digest, attachment id + independently computed sha256, state | publish/reconcile | read-back, issue |
| `issues` | task, native run id, claim-lock digest, outcome, revision, baseline commit + product tree, allowed paths, procedure pins, budget key, writer generation, state | issue (after claim) | pre-write/complete checks |
| `ledger` | append-only attempt / reject / pending / restore / accept-begin / accept-commit / accept rows, hash-chained | advance in outcome mode, gate CLI | budget, acceptance, account |
| `intents` | durable continuation intents (`m2-release`, `m4-assessed`, `m5-stage-done`, `revision`), step progress, result | pre-completion hook | reconciler |
| `effects` | commit / push / deploy intents: candidate, operation id, revision, generation, state `admitted/sent/landed/failed/uncertain` | effect admission | revision commit, recovery |
| `writer` | the one shared-tree writer: task, run, pid, process group, generation | issue | issue, transfer |

**Durable write order.** Every decision is one `BEGIN IMMEDIATE` transaction
that re-reads what it decides on. No transaction is held across a build, a
native CLI call or an external request. A native operation is always preceded
by a durable intent row and followed by a recording transaction; recovery reads
native state by the recorded identity before repeating anything.

## 3. Writer principal and trust boundary (C2, F1)

**Concrete writer.** `OutcomeAuthority` in `outcome_store.py`. Its only
mutation surface is a fixed set of transition methods; each validates the
request against the current records and the native board (run identity,
revision, baseline, budget, ownership) and refuses anything else. It never
accepts worker-supplied PASS, scope or budget values: it recomputes them.

**Serialization.** SQLite's database lock (`BEGIN IMMEDIATE`) is the one
cross-process exclusion mechanism for revision commit, writer-grant ownership
and external-effect admission. A process that dies releases it; its durable rows
say what it had decided.

**Principal.** In the current architecture the authority runs in the calling
process, which is the worker, the dispatcher or a hook, all under the workspace
UID in one container. The database is worker-writable. This is a
**cooperative** boundary. It refuses missing, inconsistent, stale, foreign,
redirected and older-budget records through every supported path. It
**cannot** refuse a consistent rewrite of the whole store by the worker UID.
That is the F1 blocker, reported in section 8. `enabled` execution requires
`authority_protected()` to be true: the store directory must be owned by another
UID and not writable by the calling process. It is false in every current
workspace, so execution cannot be enabled. The claim is exactly that. No claim is
made against a compromised administrator, the kernel or arbitrary subprocesses.
`claimed_control` stays false.

## 4. Transition table

| # | Transition | Caller (principal) | Durable write order | Native operation | Recovery | Budget effect |
|---|---|---|---|---|---|---|
| T1 | Derive initial graph | M2 worker via `k4_graph.py publish` (identity retained) | revision `proposed` (digest of derivation inputs) | none | re-derive; identical digest reuses the row, a different digest while unpublished replaces it | none |
| T2 | Publish node | same | publication row `creating` with native key → create → record task id → write brief → attach → record attachment id + sha256 | `hermes kanban create` (parents, assignee M3/M4 only, skill, workspace, idempotency key), `hermes kanban attach` | look the key up in `kanban.db` including archived rows: one live row = recover id; none = create again under the same key; archived or duplicate = stop `PUBLICATION_ARCHIVED` / `PUBLICATION_DUPLICATE`; a recorded attachment whose bytes differ = stop | none |
| T3 | Complete publication | same | read back the whole graph → generation `complete` | `show`/`kanban.db` read | a mismatch keeps the generation incomplete; M2 cannot complete | none |
| T4 | M2 completion | M2 terminator; hook | read back again → `release_in_progress` + intent `m2-release` → allow | native complete; dispatcher promotes assigned M3 | reconciler confirms M2 done, marks `released`; revisions refuse while `release_in_progress` | none |
| T5 | Claim → execution issue | worker `outcome_gate.py issue` | validate native run (current run id, claim lock, status, assignee) → validate prior baseline and retained candidate → supersede the prior issue → grant writer (generation+1) → write issue | none | a stale or foreign run, a manual claim of an unadmitted card, a missing grant or an unaccepted parent refuses; read-only diagnosis continues | none; spent budget carried |
| T6a | Attempt rejected | `advance.py` in outcome mode via gate | ledger `reject` (spent+1 on the outcome budget key) → restore baseline → clear candidate | none; the card stays open | a replayed reject for the same attempt sequence is a no-op | +1, never reset |
| T6b | Attempt pending | same | ledger `pending` with candidate digest, original baseline and retained paths | runtime 0011 stop request (unchanged) | restart restores the candidate only if its digest and baseline match | none |
| T6c | Attempt accepted (cluster) | same | ledger `accept-begin` → git commit → ledger `accept-commit` (commit, tree) → outcome `accepted` when every owned obligation is discharged | none | the NEXT issue (T5) first recovers an `accept-begin` without a commit record from Git history: a unique commit whose parent is the baseline and whose product tree is the candidate is recorded (`recovered`), ambiguity refuses, no match aborts to pending. advance.py (`resume_recovered`) then finishes THAT acceptance on the re-measured tree (`accept-evaluated`). Never while the previous writer may be alive; never spends twice | none |
| T6d | Scope amendment | `amend-scope.py` via the bridge | amend-scope validates evidence and locus → authority `amend_issue` re-checks issue, cluster, path class, dirtiness, count (4) and file bound (20) → new issue (same run, outcome, baseline, generation, budget) + sealed `amend` row → only then the `issued.json` projection | none | amendments are carried into every later issue of the cluster (restart keeps them) | none |
| T7 | Outcome completion | worker `kanban_complete`; hook | require an `accepted` outcome row whose tree is the current product tree and no owned obligation open | native complete | refused completion leaves the card open | none |
| T8 | M4 assessment completion | reviewer `kanban_complete`; hook | require the existing M4 audit green and a verdict bound to this assessment generation → intent `m4-assessed` (verdict, digest, candidate) → allow | native complete | intent without native done: nothing happens; native done without follow-up: reconciler executes the intent | none |
| T9 | REFUSE → repair → successor | reconciler (`on_kanban_dispatch_tick`) | revision (owners for new obligations, follow-ups with lineage, successor assessment `g+1`, M5 rebinding) → create unassigned → read back → assign → mark intent done | create, attach, assign, link (successor → M5 PREFLIGHT, visibility only) | every step keyed and recorded; a crash repeats the lookup, never the effect | follow-ups share the parent budget key |
| T10 | M5 stage grant | reconciler | stage predicate (section 6) from DERIVED facts → intent step `granted` → assign → record grant | `hermes kanban assign <stage> implementer` | an assignment already on the board is recorded, not repeated | M5 budget unchanged (run-defaults) |
| T10b | M5 stage completion | implementer `kanban_request_review reviewer=reviewer`; reviewer `kanban_complete`; hook | grant held → reviewer only → stage audit green → stage evidence DERIVED from the stage's own receipts, bound to HEAD and the bound assessment → `stage-result` (receipt digests) → intent | native review, complete | a supplied result refuses `STAGE_RESULT_ASSERTED`; missing/failed/contradictory receipts refuse | none |
| T11 | External effect (push) | granted M5 DEPLOY via `outcome_gate.py push` | admission transaction (the granted DEPLOY stage only; HEAD = the candidate its recorded preflight admitted; revision current; none in flight) → `admitted` → `git push` → `sent` → result by `ls-remote` identity | git push to the configured remote | the dispatcher tick probes an unresolved push of a finished run by identity: `landed` / `failed` / `uncertain`; `push` again reports or probes, never re-pushes | none |

A revision commit refuses while any effect is `admitted`, `sent` or
`uncertain` (`REVISION_BLOCKED_BY_EFFECT`). An effect admission refuses when
the revision it checked is no longer current. That makes the order total for
participating processes.

## 5. Identity, acceptance and counts

- Stable key `outcome:v1:<run>:<outcome_id>`; assessment `assess:v1:<run>:m4:g<N>`;
  delivery `deliver:v1:<run>:<stage>:c<N>`. Frozen at first publication.
- Later derivation resolves each group through the ownership map: a group that
  shares obligations with exactly one frozen outcome is that outcome, whatever its
  derived key now says. A group spanning two frozen outcomes refuses
  `IDENTITY_AMBIGUOUS`. Renames and regrouping never create a new budget.
- Acceptance is historical and bound to `(outcome, tree, checks)`. Its **proof
  applies** to the current candidate only when the product tree is unchanged, or a
  later recorded measurement of the current tree covers the outcome's check class
  (compile/test classes: every full acceptance measurement; parity: a parity run
  covering its scenarios). Otherwise it awaits revalidation. M4 measures combined
  behaviour on the final artifact; there is no replay after every edit.
- Account (`outcome_lifecycle.progress_account`):
  `active = baseline + additions − replaced/removed = accepted + unfinished`;
  accepted splits into `proof_applicable` and `awaiting_revalidation`.
  Already-satisfied obligations sit in a separate satisfaction account.
  Unresolved responsibilities and milestones are listed beside it, never inside
  it.

### 5.1 Source requirements (plan semantics v1)

When the run decides `loop.plan_semantics: v1`, `initial_plan_from_root`
passes the source requirements (`planner/source_requirements.py`) to the same
`derive_initial_graph`. The revision then carries `requirements` and
`requirement_ownership`; each owning node carries `requirements`, `recipes`,
`acceptance.requirement_checks` and, for a requirement-only outcome,
`planned_units` (a planned responsibility, not a write grant). Rules:

- An outcome owning requirements is covered (`_covers`) only by a measurement
  that records every requirement check; an empty work list never discharges
  it. `accept_commit` and `evaluate_recovered` RECOMPUTE the owner's checks on
  the committed tree (`planner/requirement_checks.py`, via
  `outcome_lifecycle.requirement_measurement`; never a caller-supplied value)
  and record the passing ones as `checks` beside `check_status`. Measured
  today: `gate:compile` (no open javac item in the requirement's files),
  `gate:package` / `gate:augmentation` / `gate:startup` (the rebuilt work
  list's runtime rows), `structure:annotation-absent:<fqn>` (dest model),
  `unit:fragment-implementation`, `unit:fragment-behaviour-bodies` and
  `structure:single-injectable-implementation` (`worklist._assess_implementations`
  over the owed implementation: existence, `implements`, no stub body, the
  concrete-only CDI exposure), `parity:<scenario>` (measured on this tree and
  discharged) and `behavior:repository-effects:<fragment>` (every planned
  read/committed-write row covered and discharged; an unresolved row is an
  owned verification debt). Not measured yet, so an owner of one is never
  accepted (fail closed): `unit:handler-validation-guards`,
  `unit:handler-parameter-sites`, `adapter:*`, `parity:*-mode:*`,
  `config:decided-keys`, `build:clean-generation`,
  `parity:request-body-positive-negative`, `coverage:unresolved`.
- A requirement-only outcome has no cluster; `issue` grants it no paths until a
  finding cluster attaches or the protected authority issues its planned unit.
  An empty work list never discharges it either (its checks above are
  required). Its planned unit is bounded like any unit (20 files, 160 sites,
  8 symbols; 16 only for a repository-architecture fragment unit, ADR-024)
  and names its owed paths (`planned_units`, `facts.owed_implementation`).
  The planner computes the grant such a unit may carry,
  `outcome_graph.planned_unit_grant(node, requirements, exists=…)`: the
  planned paths, a missing file only when a requirement's contract owes it,
  never a test or harness path, `UNIT_OVERSIZE` past the bounds,
  `NOT_REQUIREMENT_ONLY` for a finding-owned outcome. Issuing it through the
  authority's issue path (T5) is an open integration item; it is not issued
  by this revision.
- `owner_of_finding` maps a later finding to the frozen owner (obligation,
  then the requirement scope; a behaviour finding prefers the handler-level
  requirement) or returns a typed revision class: `previously-unknown-behavior`,
  `evidence-gap`, `missing-planning-rule`, `ambiguous-ownership`.
- Without the decision the revision, its digest and its briefs are unchanged.
  Enabling execution still requires the protected writer (section 8a).

## 6. M4 and M5 predicates

| Transition | Required at that point | Refuses on |
|---|---|---|
| M4 completion | valid, bound, current assessment; audit green | unbound verdict, stale candidate; REFUSE is **allowed** (assessment validity ≠ application verdict) |
| M5 PREFLIGHT | current assessment permits delivery evaluation | REFUSE/FAIL, missing or corrupt work list, open mandatory repair, unresolved ownership, stale candidate. Deferred release qualifications may remain recorded |
| M5 DEPLOY | accepted preflight for this candidate, coherent plan, build/publish authorization | anything produced only by DEPLOY or VALIDATE is **not** required |
| M5 VALIDATE | bound pipeline/image/deployment result and live-check inputs | missing binding |
| Shipping | full existing contract (parity, coverage, capability, G-1..G-4, release, live checks) | any delivery-blocking requirement; `deploy_for_validation` is never `ship` |

A delivery cycle, once executed against a candidate, stays bound to it. A later
candidate needs cycle `c2`, which is an explicit stop (`DELIVERY_CYCLE_UNSUPPORTED`)
in this release.

## 7. Continuation integration (F2)

`outcome_reconcile.py tick` is registered as a shell hook on the pinned
runtime's `on_kanban_dispatch_tick` observer. The gateway-embedded dispatcher
fires it once per tick, after it releases its lock. It also runs on
`kanban_task_completed` in the worker, as an accelerator. It is idempotent and
does nothing unless the root runs the outcome protocol with execution not
disabled. No new scheduler, daemon or polling agent. The registration lives in
the Stage 050 managed config. It is gated on the run selecting the protocol,
and the tick also recovers unresolved push effects of finished runs by
identity.

## 8. Conditions and blockers

- **F1/C2 (blocker):** no independent writer principal exists in the migration
  workspace. Gateway, dispatcher, hooks and workers share one UID and one
  container. The only non-writable surfaces are the root-owned image (static) and
  provisioner-written cluster objects (static per run). A protected writer needs a
  new principal: a sidecar with a separate UID that owns the store, or a platform
  service. Until one is qualified, `enabled` refuses and only `qualification` runs
  locally.
- C1/C6: qualified locally on the exact runtime tree `8a3bb406` (series
  0001–0012) with real dispatcher, CLI and workers
  (`hermes-runtime/tests/rhoai3_outcome_board`, fake provider). No runtime
  patch was needed.
- C3/C4/C5: implemented and tested synthetically
  (`lib/planner/outcome_board.test.py`). The M2 release continuation is also
  tested on the real dispatcher tick.
- Production hooks: the Stage 050 producer (`maas-api-key-provisioning.yaml`,
  block `outcome-board hooks`) adds `kanban_block|kanban_request_review|request_review`
  to the K2 matcher and registers `on_kanban_dispatch_tick` → the destination's
  `kernel/outcome_reconcile.py`. It does so ONLY when the destination's
  `run-defaults.json` selects `outcome-board/v1`, so it registers nothing today
  (`gitops/.../devspaces/outcome-board-hooks.test.py`). The real-worker tests run
  with exactly that configuration and the producer's 5 s hook timeout. It
  reaches a workspace only through the normal Stage 050 publication.
- `k4_graph.py publish --plan-file` exists for the runtime qualification.
  It is honoured in `qualification` mode only, which no factory run can
  enter.
- Found while qualifying (not changed here): the golden `decisions.yaml`
  parses with the harness's `yamlite`, but PyYAML rejects it. `load_yaml`
  prefers PyYAML when importable, so a `python3` with PyYAML on its path
  refuses the file.

## 8a. F1: the protected writer the platform must supply (design; not built)

The authority's validation code is complete. What is missing is a principal
the worker cannot replace. The smallest design that fits the existing
workspace:

| Element | What the platform provides | Why |
|---|---|---|
| Authority sidecar | a second container in the migration workspace pod (devfile component, the same ws-080 image, command `python3 /opt/rhoai3/outcome_authority.py serve`) with `securityContext.runAsUser` = a DIFFERENT UID inside the namespace range (restricted SCC permits a per-container UID in range) | a principal the worker UID cannot impersonate |
| State volume | an `emptyDir` (or dedicated PVC) mounted read-write ONLY in the sidecar; mounted `readOnly: true` (or not at all) in the worker container | the kernel enforces the read-only mount; fsGroup group-write does not help the worker across a read-only mount |
| Code | `.hermes/lib/planner/outcome_*.py` and the kernel entry points baked into the image under `/opt/rhoai3` (root-owned), never read from the worker-writable `/projects/modernized/.hermes` | the checker cannot be rewritten by the worker |
| Interface | a unix socket in a shared `emptyDir` (`/run/outcome-authority/sock`); `outcome_gate.py`, the K2 hook and the reconciler become clients that send transition REQUESTS (issue, verdict, amend, stage completion, effect admission); the sidecar recomputes every decision itself | the writer validates transitions; it never signs worker-supplied PASS/scope/budget data |
| Inputs the sidecar reads | the destination tree and `kanban.db` mounted read-only; the Git remote with its own read credential; for M5, `oc get` with its own read-only ServiceAccount token (not the worker's) | decisions re-derived from sources the worker cannot forge through the authority |
| Hook placement | `pre_tool_call.sh` and the reconciler from `/etc/hermes` (root-owned image path), `HERMES_MANAGED_DIR` baked into the image/unit | the rule in `.agents/rules/managed-scope-enforcement.md` |

What stays cooperative even then, and must be stated with any claim:
`kanban.db` is native lifecycle data and remains worker-writable. The worker
still runs the heavy measurements (Maven build/test, parity, MTA), and their
receipts remain worker-produced unless the sidecar re-runs them. The protected
claim covers authorization, scope, baseline, budget and effect admission. It
does not cover measurement authenticity.

`authority_protected()` becomes true only when the sidecar answers on the
socket, its store path is not writable by the calling UID, and its owner is
another UID. Until the platform qualifies this layout, including DWO
container overrides for `runAsUser` on the chosen Dev Spaces version,
`enabled` keeps refusing `AUTHORITY_UNPROTECTED`.

## 9. Rollback

Before any publication: remove the modules and the `pre_tool_call.sh` branch.
Nothing else changes. After a publication, which requires `qualification`
today: leave the store and board, hold execution (`disabled`), and abandon the run
explicitly. Never bulk-complete, archive unresolved parents or reset budgets.
