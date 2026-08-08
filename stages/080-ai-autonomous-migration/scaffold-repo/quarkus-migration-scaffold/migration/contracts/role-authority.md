# Role authority contract (Hermes orchestration)

**Status:** binding for migration workspace · mirrors **AD-H §16**  
**Sources:** Architect plan / AD-H §16 (Operator ACK `E-20260808T072759Z`)  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

AD-H / AD-S / SOUL stand. Human checkpoints are **ack artifacts** or Kanban
`blocked` — never mid-run Hermes interactive approval prompts (AD-H §6.1).

**Rule:** one Kanban task ⇒ one role. Dispatch `skills[]` is the **declared
preload / intended skill set** (Hermes ordered multi-skill load) — **not**
Hermes hard RBAC. **Enforcement:** SOUL + `HERMES_WRITE_SAFE_ROOT` + ack gates
+ Lead refuse lints (Research `E-20260808T074430Z`).

## Roles and prohibitions

| Role | Phase | May | Prohibited |
|------|-------|-----|------------|
| **Evidence analyst** | M1 (+ pre-M1 derive) | `mta-analysis`, inventory, `derive-legacy-boot3`; write `migration/` analysis + findings | Edit modernized app source; invent findings; waive without `mta-exception`; edit legacy/derived; `/speckit.implement` |
| **Planner** | M2 | Stories/briefs; roadmap deps per §S.6; re-plan graph under same identity | Destination app code; silent identity change; IMPLEMENT; author constitution/`AGENTS.md` |
| **Spec author** | M2→M3 | `/speckit.specify\|plan\|tasks\|analyze`; Non-Goals; `tasks.md` → `kanban_create()` | `/speckit.implement`; expand scope/AC/Non-Goals without escalate; app source outside SDD paths |
| **Implementer** | M3 | Edit `files_in_scope` only; task-id commits; stop → `blocked` | Re-plan; legacy/derived; `.hermes/skills/**`, `SOUL.md`, Managed Scope; invent units; weaken gates/tests |
| **Reviewer** | between phases / `blocked` | Read artifacts + gates; request rework; typed block reasons | Silent code fixes; override REFUSE; change identity; merge |
| **Validator** | M4–M5 | `domain-gates`, `harness-validate`, preflight/factory; record verdicts | Greenwash code; drop thresholds; ACCEPT without oracle |

**All roles:** no write to `/projects/legacy` or frozen `legacy-at-3`; no
`.hermes.md`/`HERMES.md`; no memory; no `auto_decompose`; no parallel authority
for the same fact.

## Least privilege (summary)

**Obligations, not Hermes RBAC.** Mechanical fence = `HERMES_WRITE_SAFE_ROOT` +
acks/lints — not this table alone.

| Surface | Who writes |
|---------|------------|
| `/projects/legacy`, frozen `legacy-at-3` | **nobody** (derive once then freeze) |
| Modernized app tree | **Implementer** only, `files_in_scope` |
| `migration/` analysis / briefs / specs | Analyst / Planner / Spec author (their fields) |
| `migration/` verdicts / delta | Validator |
| `.specify/` / `specs/` | Spec author |
| `.hermes/skills/**`, Managed Scope, `.env` | **nobody** (steering humans via PR) |

Environment: Dev Spaces workspace; MaaS via NetworkPolicy; no cluster-admin /
GitOps mutate. `HERMES_WRITE_SAFE_ROOT=$PROJECT_DIR` is the write fence.

## Human checkpoints

Record under `migration/acks/` (or Kanban metadata):

| Decision | Before | Human? |
|----------|--------|--------|
| Accept findings | M1 → M2 | **Yes** — `migration/acks/m1-findings.ack` |
| Approve brief/spec identity | → first IMPLEMENT for story | **Yes** — identity ACK; readiness lint necessary not sufficient |
| Modify code in-scope | IMPLEMENT | **No** per edit (packet + sensors) |
| Expand scope / edit skills/SOUL/AGENTS / amend identity | anytime | **Yes** |
| Task commit / open change | — | **No** if packet rules met; no force-push |
| Push/merge `main` | factory | **Demo:** agent may push when M4/M5 + preflight green. **Enterprise:** protected branch → human merge |

## Enforcement (Lead)

| Piece | Home |
|-------|------|
| Phase `role` + `skills[]` + `requires_acks` | `.hermes/phase-dispatch.yaml` |
| Ack schema | `migration/schemas/ack.md` + `migration/acks/` |
| Ack presence before phase advance | skill `role-authority` → `check-acks.sh` |
| Cross-role write refuse | skill `role-authority` → `check-role-writes.py` |

```bash
bash .hermes/skills/role-authority/scripts/check-acks.sh M2
python3 .hermes/skills/role-authority/scripts/check-role-writes.py .
```

Full Kanban dispatch wiring rides phase schema. Non-blocking vs Operator ACK
on §16.
