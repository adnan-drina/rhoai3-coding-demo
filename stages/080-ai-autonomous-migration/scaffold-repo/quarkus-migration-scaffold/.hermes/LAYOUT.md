# Hermes taxonomy (v2 / AD-019)

**Rule:** classify first; kind determines home. Do not add top-level
`scripts/` or `.hermes/home/scripts/` for new procedures. Creating a
parallel home is a defect.

| Kind | Home |
|------|------|
| Standing convention | `AGENTS.md` (this file is identity + taxonomy only) |
| Identity | authored `.hermes/SOUL.md`; dest loads `$HERMES_HOME/SOUL.md` |
| Seat pins | `.hermes/pins.json` |
| Seat pin oracle | Runtime: dest-init `hermes --version` vs `.hermes/pins.json`. Build: `workspace-images/scripts/assert-hermes-source-pin.py`. Dest `.hermes/checks/` retired. |
| Config templates | `.hermes/config/` — no secrets; dest Managed Scope owns the live pin. Worker profiles: `.hermes/config/profiles/{orchestrator,implementer}.yaml.template` (Operator GO `231808Z`; dest GitOps applies via `hermes profile create --no-alias`, never `--clone`) |
| Product guidance | `.hermes/skills/<category>/<name>/` |
| Dashboard launcher | `.hermes/dashboard/start-dashboard.sh` — defaults `HERMES_WEB_DIST` to overlay bake. Observability, not capability. Dest `web_dist/` / `install-web-dist.sh` / `PIN` retired. |
| Analysis | `.hermes/skills/analysis/` (MTA, inventory) |
| Migration | `.hermes/skills/migration/` (Boot3 / Quarkus / persistence) |
| SDD | `.hermes/skills/sdd/` (Spec Kit provision + story oracles) |
| M4 oracles | `.hermes/skills/gates/` (`check-domain-parity`, `check-release-readiness`, `assert-pinned-gates-ran`, `assert-retrievable-tree`) |
| Shared Python | `.hermes/lib/` — **not a skill** (generated_sources, specimen splits). Identity is `.hermes-lib` marker, not a member module. |
| Retired `_park/` | Deleted (Operator GO `155455Z`). Dest omit + chaos re-add tripwire stay in `scripts/bootstrap-migration-scaffold-v2.sh`. Do not mkdir empty `_park/` or dump requeue into kernel. Rebuild wall/crash/chaos later only on dest GO. |
| K2 REHOST | `.hermes/kernel/pre_tool_call.sh` — **one** shell `pre_tool_call` module (`fail_closed: true`). Same measured file as K2 instrumentation (`879fa292`); this sitting classifies it as the kernel home, not a new fence. Dest GitOps copies **this file only** when present. **Not claimed control** (write-escape MEASURED; container limb waived `131318Z`). Do not mkdir empty `kernel/`. |
| K1 body schema | `.hermes/kernel/k1_schema.py` + `k1_load.py` + `k1_validate.py` — typed pre-execution body. Not a skill. KEEP `check-kanban-body.py` imports the validator for the AD-019 minimum. Digest proves consistency among copies, not authorization. `claimed_control` stays false. |
| K3 mint-verifier | `.hermes/kernel/k3_schema.py` + `k3_verify.py` — graph-snapshot procedure. Native unfinished parents hold M3; ACCEPT is `kanban_complete` on the verifier; REFUSE is sticky `kanban_block`. Not dest live-PID reclaim. Not claimed refuse-as-control. OBJECT `kanban daemon --force` / human `ack_gate` / `kanban_request_review` on the verifier. |
| K4 converter | `.hermes/kernel/k4_schema.py` + `k4_convert.py` — typed partition → `kanban_create` payloads (inline K1 body). Copies `files_writable` from the partition row. `K4_T0_3_SERVICE` refuses the same `*Service.java` on two or more stories (class-per-aggregate; wrong reading is methods in shared `ClinicService`). Does not mint. Does not import `create_task`. Does not scrape `tasks.md` (`PATH_TOKEN` OBJECT). Manifest `created_cards` is the exact logical-id list. Does not consume type-inventory `reached_from`. Dest GitOps still copies **only** `pre_tool_call.sh`. `claimed_control` stays false. |
| Run data | `evidence/` |
| Spec Kit workspace | `.specify/` + `specs/` — gitignored in golden; never commit `.specify/` |
| Task state | Hermes Kanban (native). No parallel CSV / `created-cards-*.json` |

**Out of day-one (deleted, do not port):** `.hermes/skills/harness/`,
`.hermes/home/scripts/`, `.hermes/phase-dispatch.yaml`, human `ack_gate`,
`handover-mint.py`, `dispatch-phase`, write-fence plugins. Slim kernel
K1–K4 live in `.hermes/kernel/`. K4 emits payloads; the worker still calls
`kanban_create` (pin CLI has no `--body-file`). Do not dest-apply K4.
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
(`kanban_complete` / `kanban_request_review` / `kanban_block`). Mint
complete requires `created_cards`. Do not wrap these in home scripts.

## Product skill index

| Leaf | Kind | Purpose |
|------|------|---------|
| `scan-with-mta` | analysis | `mta-cli` / kantra analyze + findings normalize |
| `inventory-legacy-surface` | analysis | Entry-point + type-graph inventory |
| `derive-legacy-boot3` | migration | Boot 2→3 derivation |
| `spring-to-quarkus-patterns` | migration | IMPLEMENT mapping cards |
| `manage-quarkus-extensions` | migration | Extension add/rm (RH BOM) |
| `author-destination-pom` | migration | Destination Quarkus POM |
| `reference-rh-quarkus-pom` | migration | RH Quarkus POM structure |
| `form-entity-persistence` | migration | Entity / persistence form |
| `configure-quarkus-profiles` | migration | Quarkus config / profiles |
| `init-spec-workspace` | sdd | Spec Kit 0.16.1 provision wrapper |
| `check-spec-readiness` | sdd | Domain lints + 1:N partition coverage |
| `derive-story-oracles` | sdd | Story-class exit derivation |
| `check-domain-parity` | gates | G-1..G-4 measurement oracles |
| `check-release-readiness` | gates | M4/M5 verdict routing (no phase-dispatch matrix) |
| `assert-retrievable-tree` | gates | M4 refuse unless `src/` and `pom.xml` committed vs HEAD |
| `assert-pinned-gates-ran` | gates | M4 refuse unless each pinned gate has a verdict or `ran: false` refusal |

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
