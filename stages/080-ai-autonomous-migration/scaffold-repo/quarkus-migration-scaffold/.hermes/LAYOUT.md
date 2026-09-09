# Hermes taxonomy (v2 / AD-019)

**Rule:** classify first; kind determines home. Do not add top-level
`scripts/` or `.hermes/home/scripts/` for new procedures. Creating a
parallel home is a defect.

| Kind | Home |
|------|------|
| Standing convention | `AGENTS.md` (this file is identity + taxonomy only) |
| Identity | dest-user: authored `.hermes/SOUL.md`; dest loads base `$HERMES_HOME/SOUL.md`. Workers: `.hermes/config/profiles/{orchestrator,implementer,reviewer}.SOUL.md` → `profiles/<name>/SOUL.md` (sha256 at dest-init; standing stop-and-block for implementer lives in implementer.SOUL.md, not as SKILL.md copies). Official: one SOUL.md per profile home. |
| Seat pins + planner activation | `.hermes/pins.json` — tool pins (`structure_extractor` = the toolchain JDK, pinned `jdk-21`; `mta_cli` pinned `8.2`; no optional producers) and `planner.activation ∈ {not-activated, pilot, activated}` with the run-scoped `planner.pilot` seal (`run_id`, `authorized_by`, `evidence_bundle_sha256`). Read by the activation gate, admission, and K4 independently. A worker never edits it. |
| Seat pin oracle | Runtime: dest-init `hermes --version` vs `.hermes/pins.json`. Dest `.hermes/checks/` retired. Overlay rebuild is out of tree. |
| Config templates | `.hermes/config/` — no secrets; dest Managed Scope owns the live pin. Worker profiles: `.hermes/config/profiles/{orchestrator,implementer,reviewer}.yaml.template` plus sibling `{name}.SOUL.md` (Operator GO `231808Z`; dest GitOps applies via `hermes profile create --no-alias`, never `--clone`). Reviewer: kanban + terminal + skills; write toolsets disabled. |
| Product guidance | `.hermes/skills/<category>/<name>/` |
| Dashboard launcher | `.hermes/dashboard/start-dashboard.sh` — defaults `HERMES_WEB_DIST` to overlay bake. Observability, not capability. Dest `web_dist/` / `install-web-dist.sh` / `PIN` retired. |
| Harness dest-init | `.hermes/skills/harness/` (`dispatch-phase` / `autostart-migration.sh` only) |
| Analysis | `.hermes/skills/analysis/` (freeze, build, JDK-model inventory, MTA, bundle) |
| Migration | `.hermes/skills/migration/` (`bootstrap-destination`, `fix-until-green` = the loop's common procedure, plus the Quarkus/persistence/pom domain skills) |
| Planning contracts | `.hermes/planning/` (JSON schemas for the evidence bundle, the work list, the admission receipt and `decisions.yaml`; catalogs incl. `compat-mapping.json`; MTA rules incl. `rhoai3-canary`; `decisions.example.yaml`). Planner code is `.hermes/lib/planner/` (`worklist`, `cards`, `admission`, `evidence`, `live_board`, `pins`, `decisions`). The only human input is `decisions.yaml` at the project root (platform, attempt threshold, ADR-retired items). |
| Planning skills | `.hermes/skills/planning/` (`build-worklist`, `admit-migration-plan`, `verify-live-kanban-loop`) |
| SDD | `.hermes/skills/sdd/` (`derive-story-oracles` reference only; Spec Kit removed, no compatibility path) |
| M4 oracles | `.hermes/skills/gates/` (`compose-m4-verdict`, `check-domain-parity`, `check-release-readiness`, `assert-pinned-gates-ran`, `assert-retrievable-tree`, `assert-no-fence-evasion`) |
| Shared Python | `.hermes/lib/` — **not a skill** (`planner/` package: canonical digests, yamlite, schema_lite, evidence, worklist, cards, admission, live_board, pins, decisions; plus generated_sources, specimen splits, paved_road, check-external-dirs). Identity is `.hermes-lib` marker, not a member module. |
| Paved-road | `.hermes/skills/paved-road/` — kind index (`paved-road-m1`: freeze → build → JDK-model inventory → scan → bundle → attach; `paved-road-m2`: activation gate → bootstrap-destination → build-worklist → admit-migration-plan → K4 mint → K3 verify); `steps.json` generates `audit.json`. M3 loop cards pin `fix-until-green` + the kind's domain skills from `planner.cards.CARD_SKILLS`; M4 pins `capture-source-oracles` + gates. |
| Dest-init mint | `.hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh` — M1 ANALYZE (`--idempotency-key m1-analyze`, `--skill paved-road-m1`); M2 PLAN as child of M1 (`m2-plan`, `--skill paved-road-m2`) **only** when `.hermes/pins.json` `pins.planner.activation` is `activated`; writes `.hermes/AUTOSTART-STATUS`. Not T0 dispatch-phase. Never M3/M4. RHDH `autoStartMigration` defaults true; off is inspect-before-agents. |
| Retired `_park/` | Deleted (Operator GO `155455Z`). Dest omit + chaos re-add tripwire stay in `scripts/bootstrap-scaffold-repos.sh`. Do not mkdir empty `_park/` or dump requeue into kernel. Rebuild wall/crash/chaos later only on dest GO. |
| K2 REHOST | `.hermes/kernel/pre_tool_call.sh` — **one** shell `pre_tool_call` module (`fail_closed: true`). Vetoes worker graph mutation (`kanban_create`/`link`/`swarm`/`decompose`, direct `hermes kanban create|link`, `daemon --force`); cards come from K4 only. Dest terminal allow-root is dest tree **and** `/projects/legacy` (`K2_ALLOW_ROOT` pathsep; Architect `214325ZA`). **Opaque** construction **deny**; transparent pathless + cwd inside a grant **allow** (Architect AMEND of `214743ZA`; Operator `085036ZO`). Write sandbox stays `HERMES_WRITE_SAFE_ROOT` dest tree only. **Not claimed control**. Do not mkdir empty `kernel/`. |
| K1 body schema | `.hermes/kernel/k1_schema.py` + `k1_load.py` + `k1_validate.py` — typed pre-execution body. Not a skill. KEEP `check-kanban-body.py` imports the validator for the AD-019 minimum. Digest proves consistency among copies, not authorization. `claimed_control` stays false. |
| K3 graph snapshot + live comparator | `.hermes/kernel/k3_schema.py` + `k3_verify.py` (snapshot) and `k3_live.py` (live `hermes kanban list/show --json` vs the loop's expected cards: every accepted step's card + the one open head card, receipt-bound keys, parent chain; a card is matched only by its native idempotency key or by K4's mint receipts `evidence/receipts/k4/mints.json` — never by title/body; exempting the M2 card exempts its M1 ancestor; foreign, keyless or duplicate cards refuse; receipt `evidence/receipts/k3/live-board.json`). Not dest live-PID reclaim. Not claimed refuse-as-control. |
| K4 converter | `.hermes/kernel/k4_schema.py` + `k4_convert.py` — sealed `worklist.json` + ADMITTED `admission-receipt.json` (+ `verification/loop/steps.json`) → exactly **one** `kanban_create` payload: the head cluster as `M3 <cluster>` (kind build/config/compile/incident/test/parity) or `M4 VERIFY` when the list is empty and nothing is deferred. Typed K1 body carries `receipt_sha256`, `worklist_sha256`, cluster id/kind/attempt, `write_set`, `item_ids`, artifact digests. Idempotency key `k4:<cluster>:<attempt>:<receipt16>`. Zero payloads unless ADMITTED and every seal re-verifies; K4 re-derives activation/pilot and tool pins from `pins.json`. Refuses a card whose pinned skills contain no producer for its primary artifact (`k4_producers.py`). Does not mint. Does not import `create_task`. `claimed_control` stays false. |
| K4 mint | `.hermes/kernel/k4_mint.py --root . [--exec] [--verify-board]` — re-verifies the receipt, then one serial CLI `hermes kanban create` (inline `--body`, `--max-retries 1`, `--assignee implementer`, `--workspace`, `--skill` per kind, `--parent` = previous accepted card + `HERMES_KANBAN_TASK`), captures the `t_*`, appends `evidence/receipts/k4/mints.json` (task id → key provenance for K3). `--verify-board` runs the K3 live comparator after mint. `advance.py` calls it after every accepted / deferred step. OBJECT `create_task` import, `kanban swarm`, `kanban decompose`, `kanban link`, `kanban daemon --force`. Default is dry-run argv. `claimed_control` stays false. |
| Kanban attach | `.hermes/kernel/kanban_attach.py` — dual-write M1 KEEP evidence onto the card (`hermes kanban attach`, 25 MB/file): **evidence-bundle**, findings-handoff, entry-point-inventory, type-inventory, required-extensions, mta-findings. Not a derived Boot 3 manifest. PVC paths stay. Skip oversize rather than silent-drop. Idle when `HERMES_KANBAN_TASK` unset. |
| Run data | `evidence/` |
| Verification | `verification/` — the loop's protected journal (`loop/steps.json` accepted steps + attempts, `loop/issued.json` the one issued card, `loop/cards.json` registered control cards, `loop/deferred.json`, `loop/state.json` with the candidate tree identity, `loop/accepted/` snapshot of the accepted state's reports; `build/run.json` per-tool outcomes, `build/diagnostics.json`, `build/surefire.json`, `mta-rescan/`, `parity/`, `source-oracles/`); the sealed work list is rebuilt from them, never edited. Spec Kit (`.specify/`) is removed: no provisioning, no shim. |
| Task state | Hermes Kanban (native). No parallel CSV / `created-cards-*.json` |

**Out of day-one (deleted, do not port):** `.hermes/home/scripts/`, `.hermes/phase-dispatch.yaml`, human `ack_gate`,
`handover-mint.py`, write-fence plugins. `stamp-harness-rev.py` stays retired.
Exception: `autostart-migration.sh` at the GitOps-named path (Architect `195231ZA`)
is the dest-init M1 consumer — not a restored T0 dispatcher.
K1–K4 live in `.hermes/kernel/`. K4 emits one loop-card payload per step; `k4_mint.py` is the
CLI translator (`hermes kanban create`, pin CLI has no `--body-file`).
Do not dest-apply K4. Do not emit dest factory LLM cards.
K3 `k3_verify.py` is a graph-snapshot procedure (Architect `145017Z`); not dest
PID reclaim and not claimed refuse-as-control. Dashboard UI is overlay
`HERMES_WEB_DIST` (`/usr/local/share/hermes/web_dist`); destfile launches
`start-dashboard.sh` fail-soft. Do not ship dest `web_dist/` / `PIN` /
`install-web-dist.sh`. Do not ship dest `.hermes/checks/`.

## How to invoke

Prefer skill paths (Hermes sets `HERMES_SKILL_DIR` when a skill is loaded):

```bash
bash "${HERMES_SKILL_DIR}/scripts/<script>"
python3 "${HERMES_SKILL_DIR}/scripts/<script>.py"
```

Kanban workers use the official CLI / tools — one terminator
(`kanban_complete` / `kanban_request_review` / `kanban_block`).
Implementer happy path is `kanban_request_review`. Mint proof is
`created_cards` on that terminator's metadata (or KEEP + official log).
Mint-writer `kanban_complete` still requires `created_cards` (K3). Do
not wrap these in home scripts.

## Product skill index

| Leaf | Kind | Purpose |
|------|------|---------|
| `paved-road-m1` | paved-road | M1 ANALYZE index; pin only this; `skill_view` subskills |
| `paved-road-m2` | paved-road | M2 PLAN index; pin only this; `skill_view` subskills |
| `freeze-migration-input` | analysis | Freeze the original legacy source: source manifest + byte-identical analysis copy with verified digest |
| `capture-build-evidence` | analysis | Repository build wrapper (Maven/Gradle) → build receipt; failed build → planning-only |
| `inventory-legacy-surface` | analysis | JDK compiler-API extractor (`javax.lang.model` via `JavacTask`, no third-party dependency; full with a classpath, partial without) → `structure.json`, entry-point + type inventories |
| `scan-with-mta` | analysis | MTA CLI 8.2 pin + provenance receipt + canary; kantra fallback provisional / non-admissible; never `--source` |
| `assemble-evidence-bundle` | analysis | Seals source manifest, structure, entry points, MTA obligations into `evidence-bundle.json` (environment-independent) |
| `bootstrap-destination` | migration | Deterministic compat-path baseline: import frozen source, pom/properties/main-class from `compat-mapping.json` + pins (stdlib only) |
| `build-worklist` | planning | The only plan: JDK diagnostics + surefire + MTA rescan → clustered, ordered work list; records the baseline step |
| `admit-migration-plan` | planning | Admission receipt v2 (ADMITTED / INCONCLUSIVE / COMPAT_FAIL) + `assert-planner-activated.py` gate |
| `verify-live-kanban-loop` | planning | K3 live comparator wrapper (expected = accepted steps + open head card) |
| `fix-until-green` | migration | M3 loop procedure: brief → edit write set → run-verify → advance (accept commits / revert / defer; mints next) |
| `capture-source-oracles` | gates | M4 source-side oracle capture, runtime parity, receipt-bound parity receipt |
| `derive-legacy-boot3` | migration | Optional execution-side Boot 2→3 derivation (never an M1 input) |
| `spring-to-quarkus-patterns` | migration | IMPLEMENT mapping cards |
| `manage-quarkus-extensions` | migration | Extension add/rm (RH BOM) |
| `author-destination-pom` | migration | Destination Quarkus POM |
| `commit-destination-tree` | migration | M3 harvest: one-shot `git -c` commit of dest product writes (not M4; not dest-push) |
| `reference-rh-quarkus-pom` | migration | RH Quarkus POM structure |
| `form-entity-persistence` | migration | Entity / persistence form |
| `configure-quarkus-profiles` | migration | Quarkus config / profiles |
| `derive-story-oracles` | sdd | Concern/oracle reference table (story-body linting retired with Spec Kit) |
| `check-domain-parity` | gates | G-1..G-4 measurement oracles |
| `compose-m4-verdict` | gates | M4 VERIFY producer: `evidence/verdicts/m4-verdict.json` + `failed_floors` |
| `check-release-readiness` | gates | M4/M5 verdict routing (no phase-dispatch matrix) |
| `assert-retrievable-tree` | gates | Stamp `--check-only` + M4 refuse unless `src/` and `pom.xml` committed vs HEAD |
| `assert-pinned-gates-ran` | gates | M4 refuse unless each pinned gate has a verdict or `ran: false` refusal |
| `assert-no-fence-evasion` | gates | Observe encode-then-execute after a refusal (AD-020 detector, not a boundary) |

## Domain gate vocabulary (binding)

| ID | Directory / script stem | Meaning |
|----|-------------------------|---------|
| G-1 | `g1-characterization` | characterization substance / mutation |
| G-2 | `g2-harvest-fidelity` | obligation conservation vs harvest |
| G-3 | `g3-findings-delta` | MTA findings closure |
| G-4 | `g4-runtime-parity` | observed runtime parity |

Admission fixture trees: `.hermes/skills/gates/check-domain-parity/fixtures/admission/` only.

## Hooks consent hatch (N3)

Headless seats that *declare* shell hooks need one of `--accept-hooks`,
`HERMES_ACCEPT_HOOKS=1`, or `hooks_auto_accept: true` (hermes-hooks).
The dest GitOps managed config already sets `hooks_auto_accept: true` and
registers fail-closed `pre_tool_call` when `.hermes/kernel/pre_tool_call.sh`
exists. The seat template still has `hooks_auto_accept: false` and no
`hooks.<event>` entries — dest Managed Scope owns the live hook. Template:
`.hermes/config/config.yaml.template`.
