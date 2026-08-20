# Hermes-invoked M3 mint (binding)

**Status:** binding · **Authority:** Architect `E-20260817T165300Z` /
`E-20260817T170800Z` / `E-20260817T173800Z` (ack_gate AMEND) /
`E-20260817T173950Z` / `E-20260817T181020Z` (2.4). **OBJECT** Cursor or
demo-user `mint-m3-wave.sh` / `handover-mint.py --parent` as the create
path.

The **wave-holder worker** (Hermes session on the M3 holder card) mints.
Lint is `handover-mint.py --write`. Pre-create is
`run-pre-create-gates.py` (one OK/REFUSE line). Card markdown is
`compose-m3-card-markdown.py`. Create is native `kanban_create`. Bare
`kanban create` (zero skills) is still forbidden. Do **not** `python3 -c`,
`execute_code`, or `kanban show --json` unfiltered. Do **not** `json.load`
a body in the worker.

Do not grow `handover-mint.py` (parser halt `061824Z`). Run it as **lint
only** (`--write`, **no** `--parent`, **no** `--ensure-wave-holder`).

## Fail-closed kind map (Architect `E-20260818T094316Z` / `094840Z`)

Copy this table into the **holder card body**. Dest-forbidden rewrite and
A-8 planning refuse are **not** parent waits.

| Refusal class | `hermes kanban block --kind` | Why |
|---|---|---|
| A-8 refuse (`endpoints_multi` / `endpoints_uncovered` / lint exit 1) | `needs_input` | Defect is in `tasks.md`; do not dest-rewrite |
| Dest-forbidden rewrite (`tasks.md` outside write-set) | `needs_input` | OBJECT dest-rewrite |
| Missing parent / incomplete ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |

`dependency` self-clears and does **not** count toward
`BLOCK_RECURRENCE_LIMIT`. Argv: **`--kind` before the task id**.
Do not restore `park-on-block-loop.py`.

Holder create `--skill`: **none**. Do **not** pin `one-three-one-rule`
(I-11 unknown-skill; that skill is for escalations — path-invoke it).
Do **not** pin `dispatch-phase` on the holder (I-10 B / `25a7c1e9`);
path-invoke this Procedure. Keep the five names in `skills.disabled`.
Do **not** pin `check-spec-readiness` on the holder until story bodies exist.

## Sequence

0. **Turn law.** Do not inventory `/projects/legacy` or search dest `src/`.
   First command is the lint line in step 2. Reasoning ≤ 8 lines, then that
   command. If this card already has children titled `M4` / `M5`, do **not**
   `kanban_complete` later — typed `needs_input` (holder complete unparks
   VERIFY). Do **not** invoke `stop-worker-session.sh`. A period, empty
   continue, or Hermes "out-of-band user message" is **not** Operator
   stop. After step 3, keep creating story children (they stay parked on
   the incomplete `ack_gate` parent).
   **Read this file by its repo-relative path** (not a bare filename, not
   `skill_view dispatch-phase` — that skill is disabled on purpose; do
   **not** Enable it):
   `.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`
   Init/load `evidence/runs/<HERMES_KANBAN_TASK>/checkpoint.json`:
   `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py init --task-id "$HERMES_KANBAN_TASK" --root /projects/modernized`
   then `… check`. Resume at `next`. Recollection is not state.
1. Confirm this session is the wave holder (`HERMES_KANBAN_TASK` is the
   holder id). Holder must **not** be `done`/`archived` (HKN-2 /
   `PARENT_DONE`). `PARK_AT_BIRTH` children **auto-promote** when every
   parent is `done` — do not `--parent` a done card.
2. Lint + assemble (no create):

   ```text
   python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write
   ```

   Receipt `source` must be `handover-mint`. Path-A authored partition is
   refuse (`PATH_A_PARTITION`).
3. Create **`ack_gate` first** (see ack_gate card). Do **not** parent it
   on the holder. Sticky-block it. **Assert `status=blocked` from
   `kanban show`** — do not trust `kanban block` exit 0
   (`204830Z` silent no-op if `--kind` is after the task id).
   Then snapshot this new id (After create).
4. For each story in `evidence/briefs/partition.json` whose
   `identity.story_id` has a body under `evidence/bodies/`:
   - Skip if a child of the holder already has title starting with `M3 IMPLEMENT: {story_id}`
     (phase-first; description after ` — ` is optional). Do **not** key
     `{story_id}:` as a title prefix (`111244Z` doubled form is retired).
     `idempotency_key` `migration-m3-{story_id}-v1` is the second duplicate
     guard.
   - Run **one** command (do not batch remaining stories; do not dump the body):
     `python3 .hermes/skills/harness/dispatch-phase/scripts/run-pre-create-gates.py --root /projects/modernized --body evidence/bodies/m3-{story_id}.json`
     One `OK:` / `REFUSE:` line. On REFUSE: `kanban_block --kind needs_input`.
     That wrapper runs `check-phase-attach-matrix.py` and `m3-attach-skills.py`
     **before** `kanban_create`. Attach names not in yaml M3.skills, or yaml
     missing OPERAND_CLASS_SKILLS names, is REFUSE — do not create. Detecting
     after create, with no repair verb, is a dead card (`50c3e13c`).
     Then title then markdown (two commands, this story only):
     `python3 .hermes/skills/harness/dispatch-phase/scripts/compose-m3-card-markdown.py --root /projects/modernized --body evidence/bodies/m3-{story_id}.json --print-title`
     `python3 .hermes/skills/harness/dispatch-phase/scripts/compose-m3-card-markdown.py --root /projects/modernized --body evidence/bodies/m3-{story_id}.json`
   -      `kanban_create` with skills, `initial_status=todo` /
     `--initial-status todo` (**not** the park protection — Architect
     `113650Z` / V35-CREATE-STATUS; the unfinished `ack_gate` parent is), `idempotency_key`,
     `workspace_kind=dir`,
     `workspace_path`, `max_runtime_seconds` **and** `max_retries` (native
     `kanban_create --max-runtime` / `--max-retries`; read both from
     `read-phase-dispatch.py`), `assignee=default`,
     `created-by` / `created_by` = holder id, `--parent REQUIRED` for
     holder + ack_gate **plus** each resolved `identity.parents` task id
     from `created-story-cards.json` (V35-SERIAL; create order is already
     setup → foundational → US*). Resolve with:
     `python3 .hermes/skills/harness/dispatch-phase/scripts/resolve-story-parent-ids.py --root /projects/modernized --body evidence/bodies/m3-{story_id}.json`
     REFUSE create if that script exits non-zero (parent story not minted
     yet). Parents **`[holder, ack_gate, …identity.parents]`** (gate is a
     parent, not a holder-child). Snapshot this new id (After create).
     Immediately:
     `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-story-parked.py /projects/modernized --task-id <id> --ack-gate <ack_gate_id>`
     plus `--expect-parent <id>` once per resolved identity parent.
     plus `--expect-max-runtime 2700 --expect-max-retries 2` (M3
     `phase-dispatch.yaml`; generous backstop, well above 26m; never a
     tight pacing kill).
     One `OK:` / `REFUSE:` line. Refuse unless `status=todo` (not
     `ready`/`running`) **and** `parents` include the unfinished `ack_gate`
     and those identity parents.
     OBJECT requiring story `status==blocked`. Do **not** `kanban show --json`.
     Then:
     `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py /projects/modernized --task-id <id> --body evidence/bodies/m3-{story_id}.json`
     Empty skills / mismatch vs attach stdout ⇒ typed `needs_input`; do
     not create the next story. Stamp the holder checkpoint
     (`holder-checkpoint.py stamp --next create:<next_story_id> --story-id … --child-id … --skills …`).
     Do **not** add this assert to `handover-mint.py` (1088 freeze).
     **Do NOT dispatch here.**
5. After all stories exist (or were skipped), **`kanban_complete` this
   holder** only if **no** child title starts with `M4` or `M5` **and**
   `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py /projects/modernized --holder-id "$HERMES_KANBAN_TASK"`
   exits 0 (every story child has skills, AR-4.3 digest, exit_criteria).
   DAG-shaped is not mint-complete. Parenting
   VERIFY/CLOSE on the holder is OBJECT (mint-complete would start M4 on
   empty dest). If those children exist: `--kind needs_input` and stop.
   The gate must stay `blocked` (sticky event). Story children stay parked
   because `ack_gate` is incomplete. `dispatch --dry-run` must select
   **none, including the gate**.
6. Do **not** `kanban_list` / `kanban_unblock` from this worker (those
   tools are orchestrator-mode at v0.20.2). Idempotency + skip-by-title
   replace list-then-skip. Unpark is **completing** the blocked gate, not
   unblock.

## ack_gate card

Create **before** story cards. Do **not** set `parents: [holder]`.
Holder complete must not `recompute_ready` the gate (`173800Z`) until
the issuer has written the gate-record **and** this card is `done`.

- title: `M3 ACK GATE: brief-identity`
- assignee: `default` (required; tasks without assignee never dispatch)
- create as `todo` or `ready` (not create-time `blocked` — block-on-already-blocked is refused `194210Z`)
- **no holder parent**
- then sticky-block with argv order **`--kind` before task id** so stories
  stay parked during mint:

  ```text
  hermes kanban block --kind needs_input <ack_gate_id> "mint-in-progress"
  ```

  Wrong order (`block <id> --kind …`) prints top-level usage, **exits 0**,
  and does **not** block (`204830Z`). After the command, `kanban show`
  **must** report `status=blocked`. If not, REFUSE the mint — do not
  continue to story creates.
- `idempotency_key`: `migration-m3-ack-gate-v1`
- skills: `check-spec-readiness` (non-empty; bare create OBJECT)
- body: do not implement dest code. After all story children exist, run
  `python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py /projects/modernized --task-id <ack_gate_id>`
  PASS → `kanban_complete` this gate. FAIL → keep blocked; the issuer names
  the mismatching body. Do **not** wait for Operator `kanban_complete`.

Story children parents: **`[holder, ack_gate, …identity.parents]`**.
Create-time `blocked` is not sticky and is **forbidden** on story cards
(V35-CREATE-STATUS). The incomplete gate parent holds them until the
gate-record is issued and this card is `done`; `identity.parents` holds
them until those stories are `done`. Sticky-block is **only** for the
gate (OBJECT Option B on story cards).

Unpark = issuer PASS then `kanban_complete` on the **blocked** gate
(accepted at v0.20.2; `204830Z`). The yaml is the verification record;
complete is the DAG switch.

## Pre-create gates (moved from create-m3-implementer; do not drop)

Holder invokes **only** `run-pre-create-gates.py` (this list is the
wrapper sequence — do not run these from the worker). Fail-closed.
`identity.story_id required`.
Paths are repo-relative from `/projects/modernized` (Operator `173010Z` C1).
Bare filenames resolve under the wrong skill tree and become typed BLOCK
(`exit 2` = missing script — do not invent paths).

1. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-create-path-tip-sync.py /projects/modernized`
2. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-phase-body-script-refs.py /projects/modernized`
   3. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/relocate-descendant-import-writesets.py --write`
      Dest Java whose imports need descendant-owned types moves onto polish
      before dependencies are stamped.
3b. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-body-dependencies.py --body <body> --write`
      Unowned dest twins reachable by inheritance from this story's owned
      types are assigned onto the story's partition frame (V34-5), then
      closed onto the body. `DEPENDENCY_HOLE` still names true orphans.
      `WRITESET_NOT_SUBSET` still refuses extras that are not inheritance
      (entity/ beside a model/ declaration). Do **not** dest-rewrite
      `tasks.md`.
4. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-interface-closure.py --body <body>`
5. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/stamp-destination-inventory.py --body <body> --write`
6. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py --write-receipt evidence/receipts/partition-coverage/latest.json`
   (`writeset_not_subset` / `writeset_extra` is INVALID — body.files_writable
   as written must be ⊆ partition.stories[id] declared frame. Do **not**
   treat endpoint coverage as write-set coverage. Repair the body, re-run
   stamps 3–6, **do not** stamp digest until green.)
6b. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-partition-topological-order.py`
    Coverage is not topological order. Descendant/sibling imports REFUSE.
7. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-quarantine-tombstones.py`
8. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-constraints-complete.py --body <body> --inject` then without `--inject`
9. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py --body <body> --snapshot-before`
10. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py --body <body>`
11. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-kanban-body.py --body <body>`
12. `python3 .hermes/skills/harness/dispatch-phase/scripts/check-phase-attach-matrix.py /projects/modernized`
    (yaml M3.skills and the m3-implementer bundle must cover
    OPERAND_CLASS_SKILLS plus check-spec-readiness — one source, not a
    second five-name list.)
13. `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-bundle-skills-exist.py /projects/modernized --bundle m3-implementer`
14. `python3 .hermes/skills/harness/record-run-evidence/scripts/stamp-body-digest.py` (AR-4.3 first stamp only). If the sidecar already exists, that script REFUSES unless `--allow-sidecar-only` (pre-create repair). After the card exists, body repair MUST use `restamp-card-and-sidecar.py --root . --body <body> --task-id <id>` — sidecar-only restamp is refuse.
15. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-surgical-scopes.py` + `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-semantic-exits.py` + `python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py --wall-fit`
16. `python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-mint-oracles.py --body <body> --skip-task-id`
17. `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-skills-not-disabled.py /projects/modernized` with `--skill` once per line of `m3-attach-skills.py` stdout (B3 / `25a7c1e9`). Intersection with `skills.disabled` ⇒ refuse. Do **not** grow `handover-mint.py`.

Attach skills from `python3 .hermes/skills/harness/dispatch-phase/scripts/m3-attach-skills.py <body>` (B-16).
skills = full m3-attach-skills.py stdout
(`kanban_create` skills: every line of that stdout, order-stable).
do not subset attach stdout to yaml
(yaml M3.skills is the pool that must already contain every attach name;
it is not a create filter). Pom skills attach only when pom.xml is in
files_writable (A-5; foundational must not inherit setup's pom write-set).
Dropping any name is refuse — v22 setup/foundational kept only
`check-spec-readiness` while attach printed three/four (`035010Z`).
REFUSE before kanban_create if attach names are not in yaml (attach.py
fail-closed; do not create then assert).
Max runtime **and** max retries from `python3 .hermes/skills/harness/dispatch-phase/scripts/read-phase-dispatch.py --yaml .hermes/phase-dispatch.yaml --phase M3` (`--print max_runtime_seconds` / `--print max_retries`) or body
`runtime_budget_sec`. Refuse `kanban_create` unless both native flags are on the argv. Workspace `dir:/projects/modernized`. Profile
`default` must exist (`hermes profile show default`).

Title: `M3 IMPLEMENT: {story_id} — {description}` (house `<PHASE>: <descriptor>`;
do **not** prefix `{story_id}:`).

Derive `{description}` from `evidence/briefs/partition.json`
`stories[].heading` for this `story_id`. Generic transforms only — do
**not** hardcode specimen strings and do **not** synonym-expand
(`Mgmt`→`Management` is not a transform):

1. strip a trailing `(Priority: …)` (priority is already a card field)
2. strip a leading label that merely restates `story_id` (`User Story N - `
   when `story_id` is `USN`; the bare Setup / Foundational / Polish token
   when it equals `story_id` case-insensitively)
3. strip emoji

Then trim leftover separators (`:`, `-`, `&`) and surrounding whitespace.

Instances of the rule (not literals to copy): heading
`Setup (Shared Infrastructure)` → `M3 IMPLEMENT: setup — Shared Infrastructure`;
`User Story 3 - Visit Management (Priority: P1)` →
`M3 IMPLEMENT: US3 — Visit Management`;
`Polish & Cross-Cutting Concerns` →
`M3 IMPLEMENT: polish — Cross-Cutting Concerns`.

## Card body contract (binding — `035010Z` / `224320Z`)

Phase 2.4 verified `kanban_create` *arguments* and never inventoried the
*markdown* `create-m3-implementer.sh` composed. Argument parity is not
contract parity. **Do not** grow `handover-mint.py`. **Do not** resurrect
`create-m3-implementer.sh`. Put this prose on every story card.

After `run-pre-create-gates.py` (which runs `stamp-body-digest.py`),
`compose-m3-card-markdown.py` reads `body_sha256` from the sidecar. Card
markdown **must** include all of:

1. Typed body path: `evidence/bodies/m3-{story_id}.json`
2. AR-4.3 64-hex (`body_sha256`)
3. `python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py --expect <digest> --body evidence/bodies/m3-{story_id}.json .` — mismatch ⇒ REFUSE
4. Pointer: `.hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md`
   (BANK-DEST-INV-HARDINVOKE-1 / `refs.destination_inventory`, Pre-v12 R5
   hard-invoke traps). Standing procedure stays there — do not paste it.
5. Pre-complete: `assert-complete-exit-criteria.py` (rc≠0 ⇒ REFUSE complete)
6. Constraints: workspace `dir:/projects/modernized`; do not re-plan;
   max-runtime from phase-dispatch; AD-008 (no MiniMax); AD-002E
   (`skill_view` each attached skill or typed `skills_unused`)

Template (fill; keep card markdown ≤1500 chars — **F6 card budget exceeded**
if over 1500 chars):

```text
Typed body: evidence/bodies/m3-{story_id}.json
AR-4.3 digest: {64-hex}
Verify: python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py --expect {64-hex} --body evidence/bodies/m3-{story_id}.json .
  mismatch ⇒ REFUSE
Standing: .hermes/skills/harness/dispatch-phase/references/m3-implementer-standing.md
Pre-complete: python3 .hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py . --body evidence/bodies/m3-{story_id}.json
## Exit Criteria
- {from body.exit_criteria, one line each}
## Files Writable
- {from body.files_writable, one path each}
## Constraints
- workspace: dir:/projects/modernized
- Do not re-plan. max-runtime: {seconds}. AD-008. AD-002E.
```

A four-line operands/exit/files summary **without** path + digest +
standing + `--expect` + Constraints is refuse. Do not dest-rewrite cards
after create to chase this (`192117Z`).

`idempotency_key`: `migration-m3-{story_id}-v1`.

## After create (same session)

- Immediately after each story `kanban_create`:
  `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-story-parked.py /projects/modernized --task-id <id> --ack-gate <ack_gate_id>`
  plus `--expect-parent` for each resolved `identity.parents` id.
  Refuse unless `status=todo` (not `ready`/`running`) **and**
  `parents` include the unfinished `ack_gate` and those identity parents.
  `initial_status` is **not** the protection (`113650Z` / V35-CREATE-STATUS).
  OBJECT story `status==blocked`. Do **not**
  `kanban show --json`. Do **not** grow `handover-mint.py` for this (1088 freeze).
- Immediately after each `kanban_create` (ack_gate skip write-set cache;
  every **story** id), emit dest write-set **cache** (not fence policy):

  ```text
  python3 .hermes/skills/harness/enforce-authority-boundary/scripts/emit-write-set-cache.py \
    --root . --task-id <new_id> --body evidence/bodies/m3-{story_id}.json
  ```

  File `evidence/runtime/write-sets/<t_hex>.json` must exist and be
  non-empty before the next story create (Architect 35099226). `task_id`
  in that file is Hermes `t_<hex>` hygiene. Do **not** rewrite the typed
  body `task_id` (AR-4.3 digest). Fence policy is spawn env
  `HERMES_KANBAN_FILES_WRITABLE`, not this file.
- Immediately after each `kanban_create` (ack_gate and every story id),
  fail-open once per new id:

  ```text
  bash .hermes/skills/harness/record-run-evidence/scripts/snapshot-card-boundary.sh create || true
  ```

  Hermes has no create-hook. Absence is silent (`|| true`); this text is
  the contract (`182330Z`). Do **not** run this as a pre-create gate.
- Prove each new id has parent links (holder + ack_gate + identity.parents)
  via `read-link-graph.py --expect-parent`.
- Status must be `todo` (`PARK_AT_BIRTH` / V35-CREATE-STATUS). `ready`/`running`/`blocked` is refuse.
  Sticky-block **only** the ack_gate.
- **Card-contract assert:** `hermes kanban show <id>` markdown must contain
  `evidence/bodies/m3-`, a 64-hex, `m3-implementer-standing.md`, and
  `check-body-digest-match.py --expect`. Skills on the card must include
  every write-set required skill (`filter_attach_skills_for_write_set`) —
  extras allowed; empty skills refuse. Enforced by `assert-m3-child-skills.py`
  `--task-id` (not by recollection). Any miss → typed `needs_input` BLOCK;
  do not create the next story; do not `kanban_complete` this holder.
- Assert ack_gate is still `blocked` **until** the issuer PASS + complete
  below. Do **not** leave it blocked waiting for Operator.
- Append `evidence/derived/created-story-cards.json` as
  `{"cards":[{"id":"t_<hex>","story_id":"<id>"}, ...]}` (story children only;
  not ack_gate, not this holder).
- After every story child exists, path-invoke (do **not** `--skill` pin
  `dispatch-phase`) so M4 waits on the **wave**, not this mint holder
  (R-V14.6 / `Lead:m4-parent-is-the-wave-not-the-mint`):

  ```text
  DISPATCH_PARK_CHAIN=0 DISPATCH_MAX=0 DISPATCH_START_DAEMON=0 \
    bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M4 \
      --parent <story-task-id> ...
  DISPATCH_PARK_CHAIN=0 DISPATCH_MAX=0 DISPATCH_START_DAEMON=0 \
    bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M5 \
      --parent "$(cat evidence/derived/phase-M4-task-id.txt)"
  ```

  `--parent` once per story id from `created-story-cards.json`. Not this
  holder. Not ack_gate. Refuse holder complete if M4/M5 are children of
  this holder. Refuse if `phase-M4-task-id.txt` is missing.
- Holder pre-complete: `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py /projects/modernized --holder-id "$HERMES_KANBAN_TASK"`
  then for every story child,
  `python3 .hermes/skills/harness/record-run-evidence/scripts/assert-card-body-digest-match.py . --task-id <id> --body evidence/bodies/m3-{story_id}.json`
  — card-digest == sidecar-digest == file or refuse complete (V35-DIGEST). DAG-only success is refuse.
- Issue the M3 brief-identity gate-record, then unpark:

  ```text
  python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py /projects/modernized --task-id <ack_gate_id>
  ```

  PASS → `evidence/acks/m3-brief-identity.ack.yaml` with
  `acknowledged_by: gate:check-body-digest-match`, then
  `hermes kanban complete <ack_gate_id>`. FAIL → typed `needs_input` on
  this holder; the issuer names the mismatching body. Do **not** complete
  the gate. Do **not** wait for Operator.
- Run `assert-m2b-created-cards-claim.sh` (partition set equality) after
  the wave.
- Then `kanban_complete` this holder. Worker complete-cmd (not mint):
  `assert-complete-exit-criteria.py` and
  `assert-card-body-digest-match.py` before `kanban_complete` (standing
  procedure).

## Scratch proof (Phase 2.5)

Filed `monitoring/v21/20260817-phase25-seven-card-scratch.md`. Authoring
the Procedure is not that proof.

## Retired control-plane scripts (2.4)

`mint-m3-wave.sh` and `create-m3-implementer.sh` are **deleted**. Do not
restore them. Do not invoke them from Cursor, from M2, or from the demo
user. Pre-create gates live in this Procedure; tip-sync pins target this
file.
