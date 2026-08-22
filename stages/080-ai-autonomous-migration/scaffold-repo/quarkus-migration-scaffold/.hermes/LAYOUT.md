# Hermes taxonomy (v2 / AD-019)

**Rule:** classify first; kind determines home. Do not add top-level
`scripts/` or `.hermes/home/scripts/` for new procedures. Creating a
parallel home is a defect.

| Kind | Home |
|------|------|
| Standing convention | `AGENTS.md` (this file is identity + taxonomy only) |
| Identity | authored `.hermes/SOUL.md`; dest loads `$HERMES_HOME/SOUL.md` |
| Seat pins | `.hermes/pins.json` |
| Config templates | `.hermes/config/` — no secrets; dest Managed Scope owns the live pin |
| Product guidance | `.hermes/skills/<category>/<name>/` |
| Analysis | `.hermes/skills/analysis/` (MTA, inventory) |
| Migration | `.hermes/skills/migration/` (Boot3 / Quarkus / persistence) |
| SDD | `.hermes/skills/sdd/` (Spec Kit provision + story oracles) |
| M4 oracles | `.hermes/skills/gates/` (`check-domain-parity`, `check-release-readiness`) |
| Shared Python | `.hermes/lib/` — **not a skill** (type_graph, generated_sources, specimen splits) |
| Parked mint/requeue | `.hermes/_park/` — **not a skill**; **authoring-only**. Dest clones via `scripts/bootstrap-migration-scaffold-v2.sh` omit it. Chaos never dest. Do not mkdir `kernel/` here. |
| Run data | `evidence/` |
| Spec Kit workspace | `.specify/` + `specs/` — gitignored in golden; never commit `.specify/` |
| Task state | Hermes Kanban (native). No parallel CSV / `created-cards-*.json` |

**Out of day-one (deleted, do not port):** `.hermes/skills/harness/`,
`.hermes/home/scripts/`, `.hermes/phase-dispatch.yaml`, human `ack_gate`,
`handover-mint.py`, `dispatch-phase`, write-fence plugins, dashboard
`web_dist` autostart. Slim kernel K1–K4 lands only after Gate P-kernel.

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
Day-one **registers nothing fail-closed**. Do not add `hooks.<event>`
entries until K2 (Gate P-kernel). Template: `.hermes/config/config.yaml.template`.
