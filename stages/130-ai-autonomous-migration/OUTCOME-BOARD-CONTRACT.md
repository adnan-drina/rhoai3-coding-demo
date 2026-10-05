# Outcome board — implementation contract

Two control models share the outcome board: the plan's known outcomes become
tasks after M2, a rejected attempt stays on its outcome, and M4/M5 follow the
outcomes. They differ in who owns the lifecycle.

| Protocol | Control model | Status |
|---|---|---|
| `outcome-board/v2` | **Native cooperative control.** Hermes Kanban owns task identity, runs, dependencies, review and rework, dispatch and crash recovery; a small domain adapter guards the native actions. | **Default for new runs** (architect review 2026-09-27, user confirmation). Part A. |
| `outcome-board/v1` | Protected-authority control (F1): a sidecar service in a second principal owns every deciding record. | Retired for new runs: the template no longer offers it and the skeleton renders no sidecar. The code stays for runs that selected it (v18, check-only). Part B. |
| `serial-loop/v1` | One card per step, minted by K4. | Explicit compatibility only; v12–v17. |

Paths are relative to the destination root unless they start with `.hermes/`.

---

# Part A — outcome-board/v2: native cooperative control

The architect review of 2026-09-27 is retained in this contract. Code:
`.hermes/lib/planner/{native_control,native_publish}.py`,
`.hermes/kernel/native_gate.py` (worker CLI), the v2 branches of
`outcome_hook.py`, `pre_tool_call.sh`, `_outcome_bridge.py`, `k4_mint.py`,
`m5_delivery.py`. The pure domain predicates are shared with v1 in
`.hermes/lib/planner/outcome_checks.py`.

## A1. Requirement change (F1 amended for v2)

The protected-writer requirement (F1: control records unreachable by worker
code) is **not** a prerequisite of a v2 run. Native Kanban uses a cooperative
local-user model: code running as the worker can alter `kanban.db`, its
attachments and the domain records. No tamper resistance against worker code
is claimed; `claimed_control` stays false. Measurement trust stays
`cooperative-receipts` (8b below). The migration acceptance criteria are
unchanged. Platform identity, credential and cross-run isolation protections
are unchanged.

## A2. Selection and gating

The same selection chain as v1 (section 1), with the value
`outcome-board/v2`: the template's `boardProtocol` (default `outcome-board/v2`)
is stamped into the initial commit's `run-budget.json`; the provisioner copies
it into the read-only run control with `outcome_board.execution` (Task
parameter, default `enabled` since 2026-09-27) and
`outcome_board.measurement_trust` (default `cooperative-receipts`).
Request and selection must name the same version (`PROTOCOL_MISMATCH`
otherwise). `enabled` needs `measurement_trust: cooperative-receipts`
(`MEASUREMENT_TRUST_UNDECIDED` otherwise) and nothing else: there is no
authority service to answer. A v1 authority store or serial-loop records in a
v2 run refuse `PROTOCOL_MIXED`. The launch (`autostart-migration.sh`,
`run-preflight.sh`) refuses every gap; `run-preflight.sh` also requires the
producer's v2 hook registration and refuses a registered reconciler.

## A3. Where the state lives

Everything is on the native board. There is no store, no service, no intent
table and no reconciler.

| Fact | Native carrier | Written by |
|---|---|---|
| Task identity, status, runs, claims, dependencies, review/rework history | `tasks`, `task_runs`, `task_links`, `task_events` | Hermes (dispatcher, worker tools) |
| The plan revision | attachment `plan.r<N>.json` on the task that triggered it (M2 for r1): the plan and the digest of every contract it introduces | `native_publish` |
| A task's contract (brief, membership, checks, budget family, repair paths) | attachment `contract.json` on the task | `native_publish` |
| Domain records (issue, reject, pending, accept-begin, accept-commit, amend, owner-hold, restore-held, park, restore-parked, cause-report, assessment, m4-repair, push) | keyed comments `[native-control] {json}` on the task (a key is recorded once; a replay finds it) | `native_gate.py`, `advance.py` through `_outcome_bridge` |
| A held or parked candidate, an M4 assessment | attachments `held.<id>.json`, `parked.<run>.<sha>.json`, `assessment.<run>.<sha>.json`, named by their record with a sha256 | same |
| Progress | derived view (`native_gate.py account`), never read back | — |

Stable keys: `outcome:v2:<run>:<outcome>`, `assess:v2:<run>:<outcome>`,
`deliver:v2:<run>:<outcome>`. Every v2 task body is the node description plus
one procedure line for its role (`native_control.PROCEDURE`).

Resolved context (V26-3). Each `brief.py` run of an issued M3 card also writes
`verification/loop/context-<cluster>.json` (`rhoai3.resolved-context/v1`,
`planner/resolved_context.py`) and adds one index line to the digest; the
context is never injected into the brief. The canonical `.json` is a single
line, so the same document is also written indented with sorted keys to
`context-<cluster>.txt`. That copy carries no authority and nothing hashes it.
The index line names the `.txt` file and lists each top-level key with its
line range and size. It separates FROZEN source facts (the
plan node's requirement rows, the evidence bundle's structural model,
`decisions.yaml` build profiles) from DESTINATION facts of the current product
tree (generated versus handwritten placement by file location, the build's
generators, the measured obligations on the granted paths), and carries the
owned recipes with their prerequisites and refusals, the immediate and deferred
checks from the node's `check_plan`, and named unknowns. Every assertion has a
`<file>#<selector>` provenance and a kind (`fact` or a labelled `inference`).
A destination fact bound to another tree is withdrawn into the unknowns
(`resolved_context.fresh`/`staleness`). It is descriptive: it grants no scope
and judges nothing.

## A4. Lifecycle

| # | Step | Native operation | Domain check (fail-closed hook or CLI) |
|---|---|---|---|
| N1 | M2 publishes the plan | `hermes kanban create` (parents at creation), `attach`; serialized by `verification/native-board/publish.lock` | a key match alone is never a reuse (`PUBLICATION_MISMATCH`); two live tasks (`PUBLICATION_DUPLICATE`) or an archived identity (`PUBLICATION_ARCHIVED`) stop; a crash resumes with the same command |
| N2 | M2 review / completion | `request_review`, reviewer `complete` | read-back of the whole graph empty (`M2_READBACK`); reviewer audit green |
| N3 | Release | native promotion of M3 roots when M2 is done | — |
| N4 | M3 run start | dispatcher claim | `native_gate.py issue`: this native run, the contract, parents done, budget, no unexplained edits (`ISSUE_BASELINE_DRIFT`), one open cluster / planned unit / owner-repair unit / rework unit; `issued.json` projection |
| N5 | Attempt rejected | none; the run continues | `reject` record (budget +1); advance re-issues on the same card |
| N6 | Attempt accepted | none | `accept-begin` before the commit (scope measured from git), `accept-commit` after it with the outcome decision (owned obligations absent, check class covered, requirement checks recomputed, owner-repair evidence) |
| N7 | Hand to review | `kanban_request_review` reviewer=reviewer | outcome accepted **on the current tree**; implementer `kanban_complete` refused (`NATIVE_TERMINATOR`) |
| N8 | Review | reviewer `kanban_complete` or `kanban_request_changes` | complete: audit green and N7's check again; `request_changes` = another run of the same task, budget +1 |
| N9 | Owner defect | worker publishes one repair task and `link repair -> dependent` (+ `-> open M4`), then `kanban_block kind=dependency` | classifier + validation as §5.2; candidate held as an attachment, no attempt spent; resumed by native promotion; `restore-held` on the repaired baseline |
| N10 | M4 | `request_review`; reviewer `complete` | **M4 = verification ACCEPTED**: an ACCEPT / PROVISIONAL_ACCEPT verdict bound to this task and the current candidate, audit green |
| N11 | M4 REFUSE | the M4 worker publishes repairs, links `repair -> M4`, `kanban_block kind=dependency` | `native_gate.py m4-repair` (`refuse_revision`, successor=False): same M4 task, no successor; `ASSESSMENT_BOUND` at 4 refusals; `DELIVERY_CYCLE_UNSUPPORTED` once a stage ran |
| N12 | M5 stages | native parents: PREFLIGHT <- M4, DEPLOY <- PREFLIGHT, VALIDATE <- DEPLOY | `issue` refuses while M4 is not accepted or the tree drifted from the accepted candidate (`ISSUE_STALE_CANDIDATE`); reviewer completion on the stage's bound receipts |
| N13 | Push | `native_gate.py push` | reads the remote back FIRST: a landed push is recorded, never repeated; `sent` / `landed` / `failed` / `uncertain` records |

M3 cards and recovery (after v20, 2026-09-27):

- **Titles.** Every repair card is titled `M3 <ACTION> — <subject>`
  (BUILD, CONFIGURE, COMPILE, RUNTIME, BEHAVIOR; REPAIR for an owner repair,
  FOLLOW-UP for an M4 follow-up). No two cards share a title: equal subjects
  become `(part i of n)`. A published title is never rewritten.
- **Card text (card/v2, H-11).** With `decisions.loop.card_presentation: v2`
  (pinned at run creation, `CARD_PRESENTATION_REPINNED`) titles, bodies and
  review handoffs are rendered by `planner.card_text` from the plan's facts:
  the goal; scope (files, endpoints); done when (findings by kind -- compiler
  errors, MTA findings, planned changes -- and each check judged here); the
  checks judged LATER and where, which approving the card does not
  discharge; and, for a follow-up, which card found what failing after which
  accepted card. A node's body is stored on it (`card_body`) when it is first
  published and never re-rendered; a plan without the key publishes the v1
  text unchanged. The handoff reports the decision, each execution stage's
  state and each check's result (pass / fail / unknown / blocked); a check is
  never reported passing from its class or from `done`. Text is presentation:
  no decision reads it.
- **Runtime checks gate M4.** A requirement check that needs the running
  application (`parity:`, `behavior:`, `gate:package|augmentation|startup`) on
  an outcome whose class cannot measure it is moved to the M4 node's
  `acceptance.deferred_requirement_checks` at publication. M4 refuses
  `ASSESS_DEFERRED_CHECKS` while one is unmet; `m4-repair` turns each into a
  follow-up of its owning outcome (class behavior, the owner's budget).
- **Satisfied elsewhere.** A repair outcome with no open scope whose owned
  obligations another outcome's accepted commit already discharged (v21: a
  package unit fixed the type-level outcomes inside it) is accepted by
  `issue` itself: an `accept-commit` record on HEAD with `satisfied_by`,
  measured on this tree with the classes another acceptance recorded on it.
  `issue` answers `next: SATISFIED …` (handoff, then review; no loop), or
  `NOTHING ISSUED …` with its reasons (block needs_input). The M3 audit
  grades that record for such a card.
- **Planned units are judged by their requirements.** A planned unit's
  issued card carries the `planned-unit` gate: a step is accepted when the
  measure does not get worse and no mandatory obligation appears; the
  outcome's requirement checks, recomputed by `accept-commit`, decide the
  outcome (v21: fragment implementations were refused "measure did not
  decrease" by the compile tuple they cannot move). A rejection a harness
  defect caused is taken out of the budget by the Operator's
  `native_gate.py void-rejects` (a `reject-voided` record; nothing deleted).
- **One verdict per unit.** advance.py answers "ACCEPTED already" only for
  the issued unit's idempotency key, so the next unit issued on the same card
  is judged.
- **Named reasons.** `accept-commit` returns `not_accepted_because`: each
  open obligation, unmet check (status and detail) and unmeasured class.
- **Park before block.** A block on a repair card whose issued run leaves
  product edits in the tree refuses `BLOCK_LEAVES_CANDIDATE`;
  `native_gate.py park` holds the candidate as `parked.<run>.<sha>.json`
  and restores HEAD, so the next card starts clean. When the card resumes,
  `issue` reports `parked_candidate` and `restore-parked` puts it back to be
  re-verified.
- **A failing scheduled check goes to the owners of its evidence** (H-13,
  architect decision 2026-10-01). A `behavior:repository-effects:` check
  measured at an earlier card (`schedule_at_issue`) carries structured
  witnesses (`requirement_checks.effect_witnesses`: status/body/server-error
  findings on its scenarios, comparison FAILs no finding explains, unknown
  scenarios). An owner must be EXECUTABLE: a native task that exists and is
  not done or archived. A finding resolves by `outcome_graph.owner_of_finding`;
  a record-only FAIL resolves to the executable outcome whose immediate checks
  judge that scenario now (`judged_now`: parity, Location coverage, effects
  verification) -- that outcome's own repair, never a follow-up behind it.
  Every failing witness owned: the row stays FAIL and owed with its
  `repair_owners`, no follow-up is minted (v30: the Owner card waited on a
  follow-up whose acceptance needed the Owner card's own finding). Unowned
  evidence (e.g. a regression of an accepted card's scenario): the owner's
  follow-up (its budget); it waits on the contributing owners, every open
  outcome judging its scenarios waits on it, and a revision whose acceptance
  dependencies close a cycle refuses `ACCEPTANCE_CYCLE` before publication.
  Ambiguous ownership is a typed unresolved result: nothing is published.
  An unmeasured scenario is verification debt (`verification_owed`), never a
  repair and never PASS. Raw verdicts never change; M4 measures it again.
- **A plain scenario comparison follows the same rule** (H-16, v31
  `t_a7c6ab1a`). A failing `parity:sc:` row whose owner is done, and whose
  scenario an OTHER open outcome judges now (`open_judges`), is that
  outcome's repair: the row stays FAIL and owed, no follow-up of the done
  owner is minted (v31: a generator follow-up scoped to `pom.xml` and a
  template was handed a persistence exception and a list order, while the
  Pet behaviour card that judged both scenarios waited on it). A schedule
  follow-up minted before this rule carries such a comparison to its judges
  at acceptance (`carried_to_judges` on the record): never PASS, still owed by
  the judges and by M4. A planned outcome keeps every check M2 gave it.
- **A stopped card's leftovers belong to that card, whoever issues next** (H-15,
  v31 `t_0ad06b42`). `park_abandoned` proves ownership against every card of
  the run (the edits lie in what its most recent ended run was issued, were
  written inside that run's window, and the issuing run started after it) and
  sets them aside onto the single proven owner; none or two owners stay the
  `ISSUE_BASELINE_DRIFT` refusal.
- **A stopped card's leftovers are its own next run's candidate** (D-1,
  post-v32 qualification; fix-until-green B11). When the issuing run's card is
  the proven owner (the same proof), HEAD is still the baseline the stopped run
  was issued at, and every leftover path lies in this issue's write set, the
  issue keeps them on the tree (`candidate_kept`, measured against HEAD's tree,
  never blessed as the baseline) and the brief hands them over as
  `candidate_on_tree`. A moved HEAD, a parked candidate of the card, or a write
  set that no longer covers them sets them aside as before.
- **A parked or set-aside candidate takes its reports with it** (H-19). Restoring
  the tree to HEAD also restores the accepted tool reports and parity comparison
  (`restore_reports`, as a revert does), so a later checkpoint never snapshots a
  comparison of a tree HEAD never held into the accepted baseline.
- **Every application-wide source component is planned at M2** (H-20). A source
  type the cross-cutting catalog classifies (exception advice, filter, web or
  security configuration ...) must be owned by an outcome or requirement, retired
  by a decision, or handled by the bootstrap -- else admission refuses
  `UNPLANNED_SOURCE_COMPONENT`. The source's exception advice is its own
  requirement (`exception-advice`): its file, the destination registration
  (Quarkus scans only `@RestControllerAdvice`), and every scenario whose SOURCE
  response has the advice's shape, derived from the model's error type.
- **An exception-advice error is compared by its keys** (D-2, extending ADR-025
  to every advice response). The destination keeps the status and the advice's
  body keys with present, non-empty values of the source's JSON types; the values
  are each platform's own diagnostics. No key set is assumed: the shapes come
  from the source model (`planner.exception_advice`).
- **Scheduled results settle before handoff** (architect decision 2,
  2026-10-01). Every acceptance exit (accept-commit, unchanged rework,
  recovered) measures and routes the rows scheduled at the card; the
  `schedule-measure` key carries the phase and the result, so a fresh
  same-tree measurement is its own record and a replay is idempotent; a
  `schedule-settled` record follows the routing. The review/complete gate
  refuses a positive acceptance whose schedule is not settled, and
  `evaluate_recovered` settles one interrupted between the two.
- **A large objective is issued in parts** (`split-large-objectives/v1`,
  `compatibility_objectives.split_large_objectives`). An objective whose final
  write set holds more than 40 KiB, measured on the tree at M2
  (`objective_inputs` `file_sizes`), is published as ordered parts of at most
  40 KiB each, one card per part: v31/v32 on Qwen 3.6 crashed or stalled on the
  8-file, 42.8 KB request-boundary card that v30 on Qwen 3.8 finished, a
  capacity limit. The bound is bytes only, never a file count: v32 finished
  the 15-file, 18.5 KB Profile unit in one checkpoint. A
  part owns the obligations in its files and the requirements whose files it
  holds (a requirement's files and linked requirements stay together), and its
  issue grants only its files; its checkpoint judges its own identities and the
  members in its files. Parts run leaf-first, each after the one before. The
  last part keeps the objective's id and clusters, waits on every earlier part
  and is issued every identity of the objective: its checkpoint judges the whole
  objective again (the existing objective completion). Every node that waited on
  the objective waits on every part; parts share the objective's descriptor,
  class checks and budget family; the progress account counts the objective
  once (its last part). At or below 40 KiB the plan is byte-identical. A part
  that must change a type another part's file uses is refused
  `INTRODUCED_COMPILE_DIAGNOSTIC` unless the constituent's sealed symbols explain
  the diagnostic: the brief tells the part to keep shared members stable.
- **Repeated refusal.** The third identical `native_gate.py` refusal in one
  run parks that run's candidate and answers `REPEATED_REFUSAL`. K2 then
  refuses every tool except `kanban_block` for that run.

Semantic repair budget: rejected attempts plus `changes_requested` runs across
every task of one budget family (an owner, its follow-ups and its owner
repairs share one key). Crashes, timeouts, quota requeues and dependency
waits spend nothing. At the limit `issue` refuses `ISSUE_BUDGET_EXHAUSTED`
and the worker blocks `needs_input`.

Crash recovery: a stale run's writes and completion refuse (`RUN_STALE`; the
native `expected_run_id`); an `accept-begin` without its record is recovered
from git (one commit on the baseline carrying the candidate: recorded, never
committed again; none: the candidate is retained).

Hooks: the producer extends the K2 matcher with the review/block terminators
and the `kanban_comment` / `kanban_attach` / `kanban_create` / `kanban_link`
tools and registers no reconciler. K2 refuses worker graph mutation, a
hand-written `[native-control]` record and attaching or removing a reserved
artifact. The pinned `pre_tool_call` shell hook fails closed; lifecycle
observers are never acceptance gates.

## A5. Evidence

| Evidence | Scope |
|---|---|
| `.hermes/lib/planner/native_board.test.py` (22) | synthetic board with the pinned review/dependency semantics, real git, the real classifier, the real K2 hook |
| `.hermes/lib/planner/native_m3_recovery.test.py` (11) | the M3 recovery rules above on the same synthetic board; also passes under the worker's `python3` (3.9) in the ws-080 image |
| `.hermes/lib/planner/objective_split.test.py` | the split of an 8-file objective and its renamed twin: partition, requirement placement, dependencies, counted once, bytes only (no file-count split), byte-identical below the bound; each part issued and judged on the same synthetic board |
| `.hermes/lib/planner/resolved_context.test.py` | the resolved context on the migration specimen and its renamed twin: inactive profile, generated DTO, wrong-tree rejection, explicit unknowns |
| Historical `test_native_control.py` (36 checks; retired suite in Git history) | the ws-080 image: real `kanban_db` lifecycle, real `hermes kanban` CLI, the golden's `native_gate.py` under the worker's `python3` (3.9), the real K2 hook. No model, no dispatcher loop, no cluster |
| `outcome-board-hooks.test.py`, `app-migration-template.test.py`, pipeline `provision-migration-run.test.py` | platform side |

The stage-local provisioning and preflight suites were also part of the recorded
qualification; those helpers have since been retired and remain in Git history.

Not established here: a model-driven worker on a live workspace, the
dispatcher's own loop and pacing on a v2 board, a fresh MTA replay. The first
controlled run measures completion, elapsed time, tokens, Operator
interventions and explained plan revisions.

## A6. Rollback and stopping

Stop the DevWorkspace (`spec.started=false`), or `hermes pause` to stop new
dispatch while in-flight work finishes (verify against the configured
gateway first). A new-run default change affects only runs provisioned after
it. Never bulk-complete, archive unresolved parents or reset budgets.

---

# Part B — outcome-board/v1: protected-authority control (retired for new runs)

The sections below are the v1 contract as implemented and locally qualified
through 2026-09-27. They govern only a run that selected `outcome-board/v1`
(none executes today). New runs use Part A.

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

(Superseded 2026-09-27: the template now defaults to `outcome-board/v2` and
renders no sidecar; Part A.) The golden ships no `board_protocol`; the template defaulted to `outcome-board/v1`
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

**What stays cooperative (stated with every claim).** See the trust-boundary
table in section 8b: heavy measurements and the work list, process-liveness
snapshots, reviewer audit assertions, push-result reports and native lifecycle
data. For the first controlled run: worker-produced build/test/parity evidence remains trusted subject to binding and consistency checks; this does NOT establish independently verified results or protection against fabricated evidence. No claim is made against a
compromised administrator, the kernel, or processes of the service's own uid.
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
classifier) and historical `test_owner_recovery_service.py` (retired suite
in Git history; exact runtime, through the service, the service crashed after the revision
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
  - Historical local qualification (retired two-UID helper in Git history,
    podman, the ws-080 image, two uids): the store path does not exist in the worker
    container (`ENOENT`), the socket cannot be unlinked, renamed or planted
    beside (`EROFS`/`EACCES`), a request crosses the uid boundary,
    `authority_protected()` is true, the gate needs the trust decision; same-uid
    and store-mounted-in-worker controls fail closed.
  - Synthetic (`lib/planner/outcome_authority.test.py`, one uid, separate
    service process): forged candidates and replayed attempt keys spend budget;
    out-of-scope and non-child commits refuse; a planted consistent store
    refuses everything; manual M5 claim, unaccepted parent and stale run grant
    nothing; repository config runs nothing in the service.
  - Historical exact-runtime qualification (`test_outcome_authority_service.py`
    in Git history, tree 8a3bb406): the service publishes the graph with the real CLI under a
    private home; attachments land where the worker reads them; read-back green.
  - Supporting evidence only (NOT qualification): the per-run worker
    ServiceAccount's declared RBAC (no pod create) and a server-side dry-run that admitted the sidecar DevWorkspace
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
- **Measurement trust (section 8b):** decided for the first controlled run (cooperative-receipts); the run control must carry it.
- C1/C6: qualified locally on the exact runtime tree `8a3bb406` (series
  0001–0012) with real dispatcher, CLI and workers
  and a fake provider (retired qualification suite in Git history). No
  runtime patch was needed.
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

## 8a. Protected-authority sidecar

The sidecar uid, store and socket checks belonged to `outcome-board/v1`. The template does not offer that
protocol, and `outcome-board/v2` has no authority service. v2 launch depends on
the run control and on `measurement_trust` (8b), not on a sidecar uid or socket.
The current image still packages the authority tree and stamps
`outcome_authority.code_sha256`, because the image build stages that tree; the
stamp is not a v2 launch gate.

## 8b. Measurement trust — DECIDED for the first controlled run

**Decision (user, 2026-09-26):** `measurement_trust: cooperative-receipts` is
accepted for the FIRST controlled run: worker-produced build/test/parity evidence remains trusted subject to binding and consistency checks; this does NOT establish independently verified results or protection against fabricated evidence.

The service measures tree identity, changed-path scope and baseline ancestry
itself. It does not re-run heavy measurements: a compile or test run in the
sidecar would execute worker-controlled build logic (Maven plugins, annotation
processors, the worker-writable `~/.m2`) in the authority's principal, and no
independent measurement service is part of this release. A worker that forges
receipts for an in-scope, correctly committed candidate obtains an acceptance,
recorded as `classes_asserted_by: worker-receipts`
(`outcome_authority.test.py test_forged_heavy_receipts_are_the_declared_cooperative_limit`).

The trust boundary covers every cooperative input, not only heavy measurements:

| Cooperative input (worker-produced or worker-reported) | Where the authority uses it | What the authority checks |
|---|---|---|
| Build, test, parity, MTA receipts; the rebuilt work list; the M4 verdict; M5 stage receipts; the live and baseline scenario records (owner recovery) | acceptance classes, open obligations, requirement checks, stage evidence, runtime-cause classification | binding to the tree it measured itself, consistency (bound candidate, verdict/stack agreement), path scope and ancestry; recorded `classes_asserted_by: worker-receipts` |
| Process-liveness / quiescence snapshots (the caller's `/proc` view) | writer transfer (`quiescent`), dead-effect recovery | none beyond the native worker pid; a false "dead" can transfer the writer early |
| Reviewer audit assertions: the paved-road audit, its receipts and its execution ledger (worker-writable process evidence) | `check_complete` `audit_green` for M2, M4 and M5 stages | none; the audit's own bindings only |
| Push-result reports (`sent`/`landed`/`failed`, `ls-remote` from the worker's remote config) | effect records | the state machine refuses regressions; admission itself is protected |
| Native lifecycle data (`kanban.db`) | claims, run ids, parents | cross-checked against the store; never grants what the store does not record |

**Cooperative evidence is not code.** Trusting worker-produced EVIDENCE does
not permit executing worker-supplied CODE in the authority's principal. The
structural requirement checks run the JDK model tool (`dest_model`); in the
service that tool is compiled from the source baked beside the authority code
into the service's private store (`<store>/analyzer`, 0700, bound once at start
by `dest_model.bind_private_work`, refused if symlinked, open or inside the
tree), and it runs, caches and extracts only there. The destination tree is an
input (its sources, classpath list and generated roots, compiled under
`-proc:none`); its `verification/build/.dest-model` cache is never executed,
read or written by the service. Architect reproduction 2026-09-27: before this,
a planted `DestModel.class` with the expected stamp executed inside
`requirement_measurement` (`analyzer_isolation.test.py`, before/after).

Setting for the first run (documentation only; no live state is changed
here): the migration-run provisioner writes it into that run's contract when
the Task parameters are `outcome-board-execution: enabled` and
`outcome-board-measurement-trust: cooperative-receipts` for that one
provisioning (PipelineRun params, or the Task defaults changed through GitOps
for the first run only). The resulting contract reads
`"outcome_board": {"execution": "enabled", "measurement_trust": "cooperative-receipts"}`.

## 9. Rollback and stopping a run

- **New-run defaults.** The template's `boardProtocol` default is
  `outcome-board/v1` (660c1c03); the provisioner's
  `outcome-board-execution` default is `enabled` with
  `outcome-board-measurement-trust: cooperative-receipts` since 2026-09-27
  (v20 needed a manual per-run enable; setting `disabled` holds new runs).
  Changing either affects only runs provisioned AFTER the change.
- **Existing runs.** The provisioner writes each run's control record ONCE;
  a later Task-default change does not touch it. What governs an existing run
  is its own immutable contract. The supported stop is stopping the
  DevWorkspace (`spec.started=false`), which is how v12–v17 were frozen. A
  rewrite of an existing run's contract is an explicit assisted Operator
  intervention, never a default change.
- **Workspace shutdown.** Stopping the workspace stops the worker, gateway,
  dispatcher and the authority sidecar together; the authority store persists
  on its volume, the board and the destination repository persist. Restarting
  resumes under the same contract.
- **Code rollback.** Before any publication: remove the modules and the
  `pre_tool_call.sh` branch. After a publication, leave the store and board,
  stop the workspace, and abandon the run explicitly. Never bulk-complete,
  archive unresolved parents or reset budgets.
