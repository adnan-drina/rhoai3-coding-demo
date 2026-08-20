# Task authority contract (Hermes orchestration)

**Status:** binding for migration workspace · mirrors **AD-H §16**
**Basis:** plan / AD-H §16; role persona layer retired (Architect
E-20260813T144117Z / Operator E-20260813T143534Z)
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

AD-H / AD-S / SOUL stand. Human checkpoints are **ack artifacts** or Kanban
`blocked` — never mid-run Hermes interactive approval prompts (AD-H §6.1).

**Rule:** one Kanban task ⇒ one task type. Dispatch `skills[]` is the
**declared preload / intended skill set** (Hermes ordered multi-skill load) —
**not** Hermes hard RBAC. **Enforcement:** SOUL + `HERMES_WRITE_SAFE_ROOT` +
**§16.4 proving-min write fence** (`.hermes/skills/harness/enforce-authority-boundary/references/write-fence.md`) + ack
gates + authority-boundary refuse lints.

## Task-type obligations

| Task type | Phase | May | Must not |
|-----------|-------|-----|----------|
| **Examining** | M1 (+ pre-M1 derive) | `scan-with-mta`, inventory, `derive-legacy-boot3`; write `evidence/` analysis + findings | Edit modernized app source; invent findings; waive without `mta-exception`; edit legacy/derived; `/speckit-implement` |
| **Planning** | M2 | Stories/briefs; roadmap deps per §S.6; re-plan graph under same identity | Destination app code; silent identity change; IMPLEMENT; author constitution/`AGENTS.md` |
| **Spec-writing** | M2 | `/speckit-specify\|plan\|tasks\|analyze`; Non-Goals; `tasks.md` (orchestrator mints Kanban) | `/speckit-implement`; expand scope/AC/Non-Goals without escalate; app source outside SDD paths |
| **Implementing** | M3 | Edit `files_in_scope` only; task-id commits; stop → `blocked` | Re-plan; legacy/derived; `.hermes/skills/**`, `SOUL.md`, Managed Scope; invent units; weaken gates/tests |
| **Checking** | M4–M5 / between / `blocked` | Read artifacts + gates; request rework; typed block reasons; record verdicts | Silent code fixes (review); greenwash; drop thresholds; ACCEPT without oracle; override REFUSE |

**All task types:** no write to `/projects/legacy` or frozen `legacy-at-3`; no
`.hermes.md`/`HERMES.md`; no memory; no `auto_decompose`; no parallel authority
for the same fact.

## Least privilege (summary)

**Obligations, not Hermes RBAC.** Mechanical fence = `HERMES_WRITE_SAFE_ROOT` +
§16.4 deny-list OS fence + `files_in_scope` refuse + acks/lints — not this
table alone. `HERMES_WRITE_SAFE_ROOT` alone is insufficient (ACKs live inside
the safe root).

| Surface | Who writes |
|---------|------------|
| `/projects/legacy`, frozen `legacy-at-3` | **nobody** (derive once then freeze) |
| Modernized app tree | **Implementing** tasks only, `files_in_scope` |
| `evidence/` analysis / briefs | Examining / Planning (their fields) |
| `evidence/` verdicts / delta | Checking |
| `.specify/` / `specs/` | Spec-writing |
| `.hermes/skills/**`, Managed Scope, `.env` | **nobody** (steering humans via PR) |

Environment: Dev Spaces workspace; MaaS via NetworkPolicy; no cluster-admin
GitOps mutate. `HERMES_WRITE_SAFE_ROOT=$PROJECT_DIR` is the write fence.

## Human checkpoints

Record under `evidence/acks/` (or Kanban metadata):

| Decision | Before | Human? |
|----------|--------|--------|
| Accept findings | M1 → M2 | **No** — `evidence/acks/m1-findings.ack.yaml` is a 5.1 **gate-record** when findings-handoff rc=0 (`gate:check-findings-handoff`). Human GO only on rc≠0. |
| Approve brief/spec identity | → first IMPLEMENT for story | **No** — `evidence/acks/m3-brief-identity.ack.yaml` is a 5.1 **gate-record** when `check-body-digest-match.py` all-PASS (`gate:check-body-digest-match`). Human GO only on rc≠0. |
| Modify code in-scope | IMPLEMENT | **No** per edit (packet + sensors) |
| Expand scope / edit skills/SOUL/AGENTS / amend identity | anytime | **Yes** |
| Task commit / open change | — | **No** if packet rules met; no force-push |
| Push/merge `main` | factory | **Demo:** agent may push when M4/M5 + preflight green. **Enterprise:** protected branch → human merge |

## Enforcement

| Piece | Home |
|-------|------|
| Phase `skills[]` + `requires_acks` | `.hermes/phase-dispatch.yaml` |
| Ack schema | `.hermes/skills/harness/enforce-authority-boundary/references/ack-authority.md` + `evidence/acks/` |
| Ack presence before phase advance | skill `enforce-authority-boundary` → `check-acks.sh` |
| Scope + deny-path write refuse | `write-fence.md` → `check-write-fence.py --body` (`files_in_scope`) + `write-set-hook.py` (EX-3 `pre_tool_call`) |
| §16.4 proving-min fence | `write-fence.md` → `apply-write-fence.sh` / `probe-write-fence.py` / `check-write-fence.py` |
| §16.8 AR-1.4 / AR-1.6 | retired EX-3 (uninvoked; not in golden scaffold) |
| §16.8 AR-1.5 slim packet | `slim-packet.md` + `check-phase-attach-matrix.py` |

```bash
bash .hermes/skills/harness/enforce-authority-boundary/scripts/check-acks.sh M2
bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh lock
python3 .hermes/skills/harness/enforce-authority-boundary/scripts/probe-write-fence.py .
python3 .hermes/skills/harness/enforce-authority-boundary/scripts/check-write-fence.py . \
  --body evidence/bodies/S-010.json
```

Full Kanban dispatch wiring rides phase schema. Non-blocking vs human ACK
on §16.
