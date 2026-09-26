# Outcome board — implementation contract (disabled by default)

Status: implementation contract for the approved native outcome-board design
(architect decision "APPROVE WITH CONDITIONS", 2026-09-25, findings F1–F5).
Applies to **new runs only**. Every existing run, board, deadline and evidence
record keeps the serial loop protocol. Execution stays **disabled** until the
conditions in section 8 are demonstrated.

Code: `.hermes/lib/planner/outcome_{protocol,graph,store,lifecycle,authority}.py`,
`.hermes/kernel/{k4_graph,outcome_gate,outcome_reconcile,outcome_authority}.py`,
and a guarded branch at the top of `.hermes/kernel/pre_tool_call.sh`. Paths below are
relative to the destination root unless they start with `.hermes/`.

## 1. Selection and gating

One rule, `outcome_protocol.select_protocol`, is used by every reader: the K2
hook, K4 (`k4_mint.py` / `k4_graph.py`), the reconciler, the Stage 050 hook
producer, `autostart-migration.sh` and `run-preflight.sh`
(`outcome_protocol.launch_gaps`).

| Question | Answer | Where |
|---|---|---|
| Who requests a protocol? | The run, once, at creation: the app-migration template parameter `boardProtocol` (default `outcome-board/v1` since 2026-09-26) stamped as `board_protocol` into the factory's `run-budget.json` in the destination's INITIAL commit. It is read from that commit only, never from the working tree | template.yaml, skeleton `run-budget.json`, `run_control.declared` |
| Who selects it? | The platform: the migration-run provisioner reads `board_protocol` from `run-budget.json` AT the validated scaffolding commit (content-addressed) and writes `board_protocol`, and for `outcome-board/v1` `outcome_board.execution` (a Task parameter, default `disabled`; never a template or event value; `qualification` refused) and the optional `outcome_board.measurement_trust`, into the read-only `contract.json` | `task-provision-migration-run.yaml` |
| Which protocol does a governed run use? | The request and the selection must agree. Nothing requested and nothing selected keeps `serial-loop/v1` (every run created before the request existed: v12–v17) | `outcome_protocol._governed` |
| Disagreement | `PROTOCOL_UNBOUND` (outcome requested, nothing selected or no platform record: v17's live shape), `PROTOCOL_DOWNGRADED` (outcome requested, serial selected), `PROTOCOL_UNREQUESTED` (outcome selected or its execution set without a request; or the shared `run-defaults.json` naming a protocol), `PROTOCOL_UNKNOWN`. Each routes to the outcome paths, which refuse; the serial loop is never started instead | same; K2, K4, launch checks |
| Legacy / local run (no run control) | `run-defaults.json` `configuration.board_protocol` and `.hermes/pins.json` `pins.planner.outcome_board.execution`, as before | same |
| Is execution allowed? | `outcome_board.execution` ∈ `disabled` (default), `qualification`, `enabled` | `outcome_protocol.execution_gate` |
| `qualification` | Honoured only without a factory declaration and run control: a disposable local fixture. Such a fixture may name a local authority socket (`authority_socket`) to exercise the service path | same |
| `enabled` | Requires the protected authority service (section 3) — `authority_protected()` true — AND the platform's measurement-trust decision (`MEASUREMENT_TRUST_UNDECIDED` otherwise, section 8b) | same |
| Mixed state | Outcome protocol with serial-loop records, serial protocol with an outcome store, or a cooperative in-tree store beside the service, refuses `PROTOCOL_MIXED` on every path | `outcome_protocol.mixed_state` |
| Launch | `autostart-migration.sh` and `run-preflight.sh` refuse any selection refusal, a mixed state, or a closed outcome execution gate (`python3 -m planner.outcome_protocol --root R launch-check`) | `outcome_protocol.launch_gaps` |

The golden ships no `board_protocol`; the template defaults to `outcome-board/v1`
(user decision 2026-09-26: a new run never launches on the serial fallback). A
default run therefore refuses at launch until the platform enables execution
for it; `serial-loop/v1` stays available only as an explicit choice, and runs
created before the parameter keep the serial loop. The template default must
not be published before the image that carries the authority code (activation
plan P4): a default run renders the authority sidecar.

## 2. Records and storage

One SQLite database holds every deciding record: in qualification mode
`verification/outcome-board/authority.sqlite3` in the tree; under the
protected authority `<store-dir>/authority.sqlite3` in the service's own volume
(`/var/lib/outcome-authority/store`), bound once at service start with no
environment or file override, and never inside the destination tree. The brief
files the attachments are made from sit beside the store. `account.json` is a
derived observer view written into the tree by the caller; nothing reads it
back as authority.

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

**Concrete writer.** The authority service (`planner/outcome_authority.py`,
entry `kernel/outcome_authority.py serve`). Its only mutation surface is the
set of `@transition` functions in `outcome_lifecycle.py`; each validates the
request against the current records and the native board and refuses anything
else. Under `enabled` execution every worker-side entry point (`outcome_gate.py`,
the K2 hook branch, `k4_graph.py publish/readback`, `outcome_reconcile.py`,
`_outcome_bridge.py`, `m5_delivery` via `m4_closure`) sends a REQUEST over the
socket; the service runs the same function in its own principal, against its
own store, and REPLACES every value it can measure itself:

| Value | The service's own source |
|---|---|
| candidate tree, attempt key | its product-tree digest of the tree (`safe_tree`: a product symlink leaving the tree refuses `TREE_UNSAFE`) |
| scope at accept-begin | the changed product paths since the issued baseline, compared in Python against the baseline's raw blob ids (git never reads a worktree file, so no repository-configured filter, fsmonitor or diff driver can run) ⊂ the issue's allowed paths (amendments included): else `ACCEPT_OUT_OF_SCOPE` |
| scope and ancestry at accept-commit | HEAD is the named commit (`ACCEPT_COMMIT_MISMATCH`), its first parent is the issued baseline (`ACCEPT_BASELINE_ANCESTRY`), `diff-tree` baseline..commit ⊂ allowed paths |
| writer process group | the native board's `worker_pid` and the caller's process snapshot |
| recovered commit trees | `ls-tree` + `cat-file` raw blobs (no checkout, no archive conversion) |
| issue scope, plan revision, baseline, cumulative budget, acceptance, grants, effects | its own hash-chained store |

**Principal and storage.** A sidecar container of the workspace pod (skeleton
`devfile.yaml`, rendered only for a run that requested `outcome-board/v1`):
`container-overrides.securityContext.runAsUser` = a uid inside the namespace's
SCC range and different from the worker's (1001040001 for wksp-ai-developer's
measured range 1001040000/10000), privilege escalation off, capabilities
dropped; code from the image's root-owned `/opt/rhoai3/outcome-authority`. The
store volume is mounted ONLY in the sidecar. The worker container has no mount
of it at all, so no path, uid, group or user namespace reaches it from there.
(The worker can edit `/etc/subuid` and use `newuidmap`; a different owner uid
alone would not be a boundary.) The socket volume is shared; the worker mounts
it READ-ONLY (it can connect, it cannot remove, replace or plant a socket).

**Pre-use check.** `authority_protected()` is true only when the socket answers
with the service schema for this root, the service's uid differs from the
caller's, the caller can neither stat nor open the reported store path, no
cooperative store sits in the tree, and the service's code identity equals the
image stamp `/opt/rhoai3/080.pins` `outcome_authority.code_sha256` (and the
harness pin `pins.outcome_authority.code_sha256` when present). Peer
credentials are never consulted: they are forgeable from a user namespace.

**What the service never trusts or runs.** A worker-supplied PASS, scope,
budget, candidate or store path; the worker's Hermes home (the pinned CLI runs
with a PRIVATE, empty `HERMES_HOME` and only `HERMES_KANBAN_DB` and
`HERMES_KANBAN_ATTACHMENTS_ROOT` shared); repository configuration (git runs
with command-scope protected configuration: no fsmonitor, hooks path, external
diff, submodule recursion, file/ssh/ext transports; and only object-reading
commands — no `status`, no `archive`, no worktree diff).

**Serialization.** SQLite's database lock (`BEGIN IMMEDIATE`) in the service's
store is the one cross-process exclusion mechanism for revision commit,
writer-grant ownership and external-effect admission.

**Qualification mode** (local fixtures) runs the same transitions in-process
against an in-tree store (cooperative). A consistent same-uid rewrite of that
store is undetectable, which is why `enabled` never runs on it.

**What stays cooperative (stated with every claim).** Native lifecycle data
(`kanban.db`) is worker-writable; it never grants anything the store does not
also record. The heavy measurements (Maven build/test, parity, MTA, the M4
verdict, the M5 stage receipts and the rebuilt work list) are worker-produced;
an acceptance records its check classes as `classes_asserted_by:
worker-receipts` (section 8b). The hook's profile and audit-green facts and a
push's observed result are the caller's report; the service admits the push,
it holds no push credential. No claim is made against a compromised
administrator, the kernel, or processes of the service's own uid.
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
  owned verification debt), `unit:handler-validation-guards` /
  `unit:handler-parameter-sites` / `unit:location-null-arguments`
  (`worklist._assess_handler_parameters` on the handler site, guards and
  Location arguments against the FROZEN source; no frozen source = unknown),
  `adapter:<contract>` (`response_adapters.verify` against the rows rendered
  from the source policy), `parity:<adapter>-mode:<mode>` (that mode's
  receipt, bound to this tree, records the consumers PASS),
  `config:decided-keys` (datasource: `check-datasource-decision.check`;
  build profiles: the decided list in application.properties and
  .mvn/maven.config; security: the decided switch key and value),
  `build:clean-generation` (the compiler producer recorded every generated
  root with files; no generated-source or unresolvable-build error) and
  `parity:request-body-positive-negative` (the static generated-body
  condition no longer holds and every captured case passes). Only missing
  SOURCE coverage stays unknown: a body case no capture sends, and
  `coverage:unresolved`.
- A requirement-only outcome has no cluster; `issue` grants it no paths until a
  finding cluster attaches or the protected authority issues its planned unit.
  An empty work list never discharges it either (its checks above are
  required). Its planned unit is bounded like any unit (20 files, 160 sites,
  8 symbols; 16 only for a repository-architecture fragment unit, ADR-024)
  and names its owed paths (`planned_units`, `facts.owed_implementation`).
  The planner computes the grant such a unit may carry,
  `outcome_graph.planned_unit_grant(node, requirements, exists=…,
  cluster_open=…)`: the planned paths (or, for an outcome that owns finding
  clusters AND requirements whose clusters are all closed while a check
  still fails, its owned requirements' paths), a missing file only when a
  requirement's contract owes it, never a test or harness path,
  `UNIT_OVERSIZE` past the bounds, `NOT_REQUIREMENT_ONLY` while a cluster is
  open. The authority's issue path (T5, `outcome_lifecycle.issue`) grants
  it: when no open finding cluster grants an outcome that has planned units
  or owns requirements, `planned_unit_grant(..., cluster_open=False)` paths
  under cluster `planned:<outcome_id>:1` when its refusal is empty, nothing
  otherwise (the refusal is reported in the issue result), under the same
  writer generation, budget, parent, baseline and amendment rules as a
  cluster; `outcome_gate.py issue` writes the `issued.json` projection for it
  (`outcome_board.test.py PlannedUnitIssue`; `planned_units_e2e.test.py` now
  runs on this production path, its seam removed).
- `owner_of_finding` maps a later finding to the frozen owner (obligation,
  then the requirement scope; a behaviour finding prefers the handler-level
  requirement) or returns a typed revision class: `previously-unknown-behavior`,
  `evidence-gap`, `missing-planning-rule`, `ambiguous-ownership`. The REFUSE
  revision (`plan_after_refuse`) uses it: a later finding with a frozen owner
  goes to that owner (a follow-up with its budget when it is accepted);
  `ambiguous-ownership` / `evidence-gap` become unresolved rows (a
  REFUSE with nothing else repairable stops naming them); the other classes
  fall through to the bounded follow-up rules.
- M4 (`record_assessment`) records the requirement checks of every owner
  node, recomputed on the assessed tree (`requirement_measurement`), with the
  measurement.
- Without the decision the revision, its digest and its briefs are unchanged.
  Enabling execution still requires the protected writer (section 8a).

### 5.2 Automatic owner recovery

A rejected attempt (`record_verdict REVERTED`) that reports runtime failures
is first classified by `planner.runtime_cause.classify(root, issued, cur,
steps, baseline)` (pure). The AUTHORITY builds its inputs
(`outcome_lifecycle.cause_inputs`):

| Input | Source | Trust |
|---|---|---|
| `issued` | its own issue (cluster, allowed paths) + the issued cluster's items from the work list | issue: protected; items: worker receipt |
| `cur.changed` | changed product paths since the issued baseline, measured by the authority | protected |
| `cur.failures` | the work list's parity/runtime items for the cluster, each with the server error of its LIVE scenario record (`runtime_cause.failures_of`) | worker receipts |
| `steps` | every committed acceptance in its own ledger, with the paths that commit changed (`diff-tree commit^1..commit`) | protected |
| `baseline.tree` | the issue's baseline tree digest | protected |
| `baseline.records` | the ACCEPTED parity snapshot's scenario records (`verification/loop/accepted/parity`) | worker receipts |

The runtime failures and the baseline records are worker-produced parity
receipts: the classification is exactly as authentic as the declared
measurement trust (`cooperative-receipts`, section 8b) and no more. The serial
loop's `advance.inputs_from_root` shares the parsing, not the trust. Only
`pre-existing-owner-defect` acts, and only after the authority validates it:
the owner (the classifier's owner step's `outcome_id`, from the authority's own
steps) is another ACCEPTED repair outcome, the evidence carries a baseline
record AND a baseline failure bound to the issued baseline tree, a failing
scenario is named, the owner's budget is not exhausted, and no repair was
scheduled for this (owner, dependent) pair before. Then, in one transaction and without spending the dependent's
attempt: the dependent's candidate is HELD in the store (its changed paths,
all inside its issue) and a durable `owner-repair` intent is written. The
reconciler publishes ONE repair outcome `repair:<owner>:for:<dependent>`
(lineage to the owner and the evidence, the owner's budget key, the owner's
recorded write set plus the throwing file, issued as unit
`planned:<repair>:1`) as a PARENT of the dependent and of every open assessment — the
dependent waits on the repair (`kanban_block kind=dependency`), never the
reverse. Every step is keyed and recorded; interruption replays lookups, not
effects. The dependent's old issue goes stale with the revision; its next issue
requires the repair accepted (`OWNER_REPAIR_PENDING` until then; K2 refuses
`kanban_complete` naming `kanban_block kind=dependency`, and advance's reissue
prints the same terminator), and `outcome_gate.py restore-held` returns the
held candidate for re-verification on the repaired baseline. The repair's
acceptance is tied to the classifier's evidence: every failing scenario must
PASS in a live scenario record bound to the repair's own tree
(`repair_evidence_gaps`), besides its check class.
Evidence: `outcome_board.test.py OwnerRecovery` (synthetic board, real
classifier) and `hermes-runtime/tests/rhoai3_outcome_board/test_owner_recovery_service.py`
(exact runtime, through the service, the service crashed after the revision
and after the publication: one repair card).
`candidate-regression` is the ordinary rejection; `ambiguous` (and any claim
the authority cannot validate, or a second claim for the same pair) is an
ordinary rejection with a visible report and no blame transfer or scope grant.
`owner-debts.json` is diagnostic only. No second scheduler.

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
disabled. Under `enabled` execution the hook only forwards the tick to the
authority service, which reconciles in its own principal (native operations
through its private-home CLI). No new scheduler, daemon or polling agent. The
registration lives in the Stage 050 managed config; the producer registers it
from the SAME effective selection (`select_protocol`: the governed request
agreed by the read-only run control), never from a mutable file alone, and
prints the refusal when the selection is inconsistent. The tick also recovers
unresolved push effects of finished runs by identity.

## 8. Conditions and blockers

- **F1/C2:** the protected writer is BUILT and locally qualified, not yet live.
  - Built: the authority service, its clients, the store binding, the pre-use
    check, the sidecar layout in the skeleton devfile (rendered only for an
    outcome-board request), the protocol selection chain and launch refusals.
  - Qualified locally (`outcome-authority-two-uid.qualify.py`, podman, the
    ws-080 image, two uids): the store path does not exist in the worker
    container (`ENOENT`), the socket cannot be unlinked, renamed or planted
    beside (`EROFS`/`EACCES`), a request crosses the uid boundary,
    `authority_protected()` is true, the gate needs the trust decision; same-uid
    and store-mounted-in-worker controls fail closed.
  - Synthetic (`lib/planner/outcome_authority.test.py`, one uid, separate
    service process): forged candidates and replayed attempt keys spend budget;
    out-of-scope and non-child commits refuse; a planted consistent store
    refuses everything; manual M5 claim, unaccepted parent and stale run grant
    nothing; repository config runs nothing in the service.
  - Exact runtime (`hermes-runtime/tests/rhoai3_outcome_board/test_outcome_authority_service.py`,
    tree 8a3bb406): the service publishes the graph with the real CLI under a
    private home; attachments land where the worker reads them; read-back green.
  - Supporting evidence only (NOT qualification): the per-run worker
    ServiceAccount's declared RBAC (`WORKER-IDENTITY-REPAIR.md`, no pod
    create) and a server-side dry-run that admitted the sidecar DevWorkspace
    on DWO 0.43.0 (2026-09-26).
  - NOT established — an explicit release prerequisite (live Dev Spaces
    qualification, section 8a): the DWO
    controller applying `container-overrides.securityContext.runAsUser` to the
    pod; SCC
    `container-build` admitting the second in-range uid; the per-workspace PVC
    subPath and fsGroup behaviour for the store and the socket; the run-control
    ConfigMap automount reaching the sidecar; the sidecar reading and writing
    `kanban.db` (group ownership, WAL/shm files) and the attachments root; the
    image carrying `/opt/rhoai3/outcome-authority` and the stamp.
- **Measurement trust (section 8b):** open architect decision.
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
  `kernel/outcome_reconcile.py`, ONLY for a clean `outcome-board/v1` selection
  (`gitops/.../devspaces/outcome-board-hooks.test.py`, governed cases
  included). The real-worker tests run with that configuration and the
  producer's 5 s hook timeout (a copy of the producer's registration, not the
  producer's output).
- `k4_graph.py publish --plan-file` exists for the runtime qualification.
  It is honoured in `qualification` mode only, which no factory run can
  enter.
- Resolved 2026-09-26: the golden `decisions.yaml` parses with the harness's
  `yamlite` but PyYAML rejects it, and `load_yaml` used to prefer PyYAML when
  importable, so the same frozen file admitted in the workspace (no PyYAML)
  and refused on any python that had it. `load_yaml` now always uses the
  subset parser: the parser is a planning input and may not depend on the
  environment (`yamlite.test.py`).

## 8a. The live qualification the platform still owes

| Element | What must be observed on a disposable started workspace |
|---|---|
| Sidecar uid | the admitted pod's `outcome-authority` container runs as 1001040001 (`oc get pod -o jsonpath` on `securityContext`), the worker as its range start; `openshift.io/scc: container-build` |
| Store unreachable | from the worker container: `stat /var/lib/outcome-authority` → no such file; no volumeMount of `outcome-authority-store` in the worker container spec |
| Socket read-only | from the worker container: `rm /run/outcome-authority/authority.sock` → read-only file system; `outcome_authority.py hello` answers |
| Pre-use check | `python3 -c 'from planner.outcome_protocol import authority_protected; print(authority_protected("/projects/modernized"))'` → `(True, ...)` with the image stamp |
| Board access | the sidecar's private-home CLI creates and attaches on `kanban.db` (group-writable under the pod fsGroup) and the worker reads the attachment |
| Run control | `/etc/rhoai3/run-control/contract.json` mounted in the sidecar |

The commands are in `tmp/v17-run-20260926/kanban-review/implementation/activation-plan.md`.
Until they pass, `enabled` is not set by the platform, and a run that requested
the outcome board refuses at launch.

## 8b. Measurement trust (open architect decision)

The service measures tree identity, scope and baseline ancestry itself. It does
not re-run the heavy measurements: a compile or test run in the sidecar would
execute worker-controlled build logic (Maven plugins, annotation processors,
the worker-writable `~/.m2`) in the authority's principal, and is not bounded in
time. So an acceptance's check classes and the rebuilt work list are the
worker's receipts; a worker that forges them for an in-scope, correctly
committed candidate obtains an acceptance, which the ledger marks
`classes_asserted_by: worker-receipts`
(`outcome_authority.test.py test_forged_heavy_receipts_are_the_declared_cooperative_limit`).
`enabled` execution therefore also requires the platform to declare
`outcome_board.measurement_trust: cooperative-receipts` in the run control —
the architect's explicit acceptance of this limit — or to fund an independent
measurement (a separate build principal with its own dependency cache).

## 9. Rollback

Before any publication: remove the modules and the `pre_tool_call.sh` branch.
Nothing else changes. After a publication, which requires `qualification`
today: leave the store and board, hold execution (`disabled`), and abandon the run
explicitly. Never bulk-complete, archive unresolved parents or reset budgets.
