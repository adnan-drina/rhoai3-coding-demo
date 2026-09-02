# Hermes taxonomy (v2 / AD-019)

**Rule:** classify first; kind determines home. Do not add top-level
`scripts/` or `.hermes/home/scripts/` for new procedures. Creating a
parallel home is a defect.

| Kind | Home |
|------|------|
| Standing convention | `AGENTS.md` (this file is identity + taxonomy only) |
| Identity | dest-user: authored `.hermes/SOUL.md`; dest loads base `$HERMES_HOME/SOUL.md`. Workers: `.hermes/config/profiles/{orchestrator,implementer,reviewer}.SOUL.md` → `profiles/<name>/SOUL.md` (sha256 at dest-init; standing stop-and-block for implementer lives in implementer.SOUL.md, not as SKILL.md copies). Official: one SOUL.md per profile home. |
| Seat pins | `.hermes/pins.json` |
| Seat pin oracle | Runtime: dest-init `hermes --version` vs `.hermes/pins.json`. Build: `workspace-images/scripts/assert-hermes-source-pin.py`. Dest `.hermes/checks/` retired. |
| Config templates | `.hermes/config/` — no secrets; dest Managed Scope owns the live pin. Worker profiles: `.hermes/config/profiles/{orchestrator,implementer,reviewer}.yaml.template` plus sibling `{name}.SOUL.md` (Operator GO `231808Z`; dest GitOps applies via `hermes profile create --no-alias`, never `--clone`). Reviewer: kanban + terminal + skills; write toolsets disabled. |
| Product guidance | `.hermes/skills/<category>/<name>/` |
| Dashboard launcher | `.hermes/dashboard/start-dashboard.sh` — defaults `HERMES_WEB_DIST` to overlay bake. Observability, not capability. Dest `web_dist/` / `install-web-dist.sh` / `PIN` retired. |
| Harness dest-init | `.hermes/skills/harness/` (`dispatch-phase` / `autostart-migration.sh` only) |
| Analysis | `.hermes/skills/analysis/` (MTA, inventory) |
| Migration | `.hermes/skills/migration/` (Boot3 / Quarkus / persistence) |
| SDD | `.hermes/skills/sdd/` (Spec Kit provision + story oracles) |
| M4 oracles | `.hermes/skills/gates/` (`compose-m4-verdict`, `check-domain-parity`, `check-release-readiness`, `assert-pinned-gates-ran`, `assert-retrievable-tree`, `assert-no-fence-evasion`) |
| Shared Python | `.hermes/lib/` — **not a skill** (generated_sources, specimen splits, paved_road). Identity is `.hermes-lib` marker, not a member module. |
| Paved-road | `.hermes/skills/paved-road/` — kind index (`paved-road-m1`, `paved-road-m2`); `steps.json` generates `audit.json`. Capability folder has no M-code. Not M3/M4 this land. |
| Dest-init M1+M2 mint | `.hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh` — M1 ANALYZE + M2 PLAN only (`--idempotency-key`); one `--skill` per card (`paved-road-m1` / `paved-road-m2`); writes `.hermes/AUTOSTART-STATUS`. Not T0 dispatch-phase. Not M3/M4. RHDH `autoStartMigration` defaults true; off is inspect-before-agents. |
| Retired `_park/` | Deleted (Operator GO `155455Z`). Dest omit + chaos re-add tripwire stay in `scripts/bootstrap-migration-scaffold-v2.sh`. Do not mkdir empty `_park/` or dump requeue into kernel. Rebuild wall/crash/chaos later only on dest GO. |
| K2 REHOST | `.hermes/kernel/pre_tool_call.sh` — **one** shell `pre_tool_call` module (`fail_closed: true`). Dest terminal allow-root is dest tree **and** `/projects/legacy` (`K2_ALLOW_ROOT` pathsep; Architect `214325ZA`). **Opaque** construction **deny**; transparent pathless + cwd inside a grant **allow** (Architect AMEND of `214743ZA`; Operator `085036ZO`). Write sandbox stays `HERMES_WRITE_SAFE_ROOT` dest tree only. **Not claimed control**. Do not mkdir empty `kernel/`. |
| K1 body schema | `.hermes/kernel/k1_schema.py` + `k1_load.py` + `k1_validate.py` — typed pre-execution body. Not a skill. KEEP `check-kanban-body.py` imports the validator for the AD-019 minimum. Digest proves consistency among copies, not authorization. `claimed_control` stays false. |
| K3 graph snapshot | `.hermes/kernel/k3_schema.py` + `k3_verify.py` — leftover dest-5 factory graphs still validate; new mints have **no** dest factory cards. Native unfinished parents hold M3. Not dest live-PID reclaim. Not claimed refuse-as-control. OBJECT `kanban daemon --force` / human `ack_gate`. |
| K4 converter | `.hermes/kernel/k4_schema.py` + `k4_convert.py` — typed partition → `kanban_create` payloads (inline K1 body). Copies `files_writable` from the partition row. When harvest `database.needed` is true and no story `PROVISION_DATABASE` exists, injects that M3 story (`k8s/postgres.yaml` + `k8s/app.yaml`; skill `form-entity-persistence`) after input validation so HTTP `dest_file` checks do not apply. After the M3 stories, appends harvest card `STAMP_DESTINATION_TREE` (skill `commit-destination-tree`; parents = every M3 story; write-set = union of product paths minus OBJECT `evidence/` / `.hermes/` / `.specify/` / `target/` / `.env`). `K4_T0_3_SERVICE` refuses the same `*Service.java` on two or more stories' `files_writable` (write-set legality; one story MAY own a shared facade). Wrong reading is methods in shared `ClinicService` on multiple stories. Split-one-class-per-aggregate is petclinic architecture, not this mint refuse. Does not mint. Does not import `create_task`. Does not scrape `tasks.md` (`PATH_TOKEN` OBJECT). Manifest `created_cards` is the exact logical-id list. Does not consume type-inventory `reached_from`. Dest GitOps still copies **only** `pre_tool_call.sh`. `claimed_control` stays false. |
| K4 mint | `.hermes/kernel/k4_mint.py` — named, tested translation of those payloads into serial CLI `hermes kanban create` (inline `--body`, `--max-retries 1` on M3 stories, `--assignee implementer`, `--parent` t_* including `HERMES_KANBAN_TASK`). After the M3 creates succeed, the same `--exec` pass emits one `M4 VERIFY` terminator (`--idempotency-key m4-verify`, skills `compose-m4-verdict` + `check-release-readiness` + `check-domain-parity`, parents = those M3 `t_*`). Convert stays M3-only. Body has no verdict token (`assert-m4-complete-around-red` owns the verdict). Refuses a card whose pinned skills contain no producer for its primary artifact (`k4_producers.py`; dest-8 six cards are the fixture: REFUSE M2+M4, pass M1/T001/T002/STAMP). Dest mint-writer / mint-verifier cards are **not** emitted. OBJECT `create_task` import, `kanban swarm`, `kanban decompose`, `kanban daemon --force`. Default is dry-run argv; `--exec` needs a seat with terminal (dest orchestrator disables it). Model `kanban_create` cannot pass `max_retries`. `claimed_control` stays false. |
| Kanban attach | `.hermes/kernel/kanban_attach.py` — dual-write M1 KEEP evidence onto the card (`hermes kanban attach`, 25 MB/file): findings-handoff, entry-point-inventory, **type-inventory**, required-extensions, mta-findings. Not `derived/legacy-at-3.json` (dest-13 attached that instead of the type graph). PVC paths stay. Skip oversize rather than silent-drop the handoff. Idle when `HERMES_KANBAN_TASK` unset. Not dest-4 mid-run. |
| Run data | `evidence/` |
| Spec Kit workspace | `.specify/` + `specs/` — gitignored in golden; never commit `.specify/` |
| Task state | Hermes Kanban (native). No parallel CSV / `created-cards-*.json` |

**Out of day-one (deleted, do not port):** `.hermes/home/scripts/`, `.hermes/phase-dispatch.yaml`, human `ack_gate`,
`handover-mint.py`, write-fence plugins. `stamp-harness-rev.py` stays retired.
Exception: `autostart-migration.sh` at the GitOps-named path (Architect `195231ZA`)
is the dest-init M1+M2 consumer — not a restored T0 dispatcher.
K1–K4 live in `.hermes/kernel/`. K4 emits story payloads; `k4_mint.py` is the
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
| `scan-with-mta` | analysis | `mta-cli` / kantra analyze + findings normalize |
| `inventory-legacy-surface` | analysis | Entry-point + type-graph inventory |
| `derive-legacy-boot3` | migration | Boot 2→3 derivation |
| `spring-to-quarkus-patterns` | migration | IMPLEMENT mapping cards |
| `manage-quarkus-extensions` | migration | Extension add/rm (RH BOM) |
| `author-destination-pom` | migration | Destination Quarkus POM |
| `commit-destination-tree` | migration | M3 harvest: one-shot `git -c` commit of dest product writes (not M4; not dest-push) |
| `reference-rh-quarkus-pom` | migration | RH Quarkus POM structure |
| `form-entity-persistence` | migration | Entity / persistence form |
| `configure-quarkus-profiles` | migration | Quarkus config / profiles |
| `init-spec-workspace` | sdd | Spec Kit 0.16.1 provision wrapper |
| `plan-migration-partition` | sdd | M2 PLAN producer: speckit → partition.json → K4 convert/mint |
| `check-spec-readiness` | sdd | Domain lints + 1:N partition coverage |
| `derive-story-oracles` | sdd | Story-class exit derivation |
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
