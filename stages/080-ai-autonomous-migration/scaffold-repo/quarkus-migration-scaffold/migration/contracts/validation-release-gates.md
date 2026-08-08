# Validation and release gates

**Status:** binding for migration workspace · mirrors **AD-H §18**  
**Sources:** Architect plan / AD-H §18 (Operator ACK pending on ledger)  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

Cross-refs: W2 G-1…G-4 (`domain-gates`), AD-H §16 validator/acks, AGENTS
factory bar, `.hermes/phase-dispatch.yaml` M4/M5.

**Defaults:** no per-task full G-4; no wave-wide wipe of prior ACCEPT stories;
G-4 primary external-API oracle; data via Flyway + IT + G-4 on inventoried data
endpoints — not a DB snapshot gate.

## Gates after each stage

| Stage | Compile | Unit/IT/contract | Static analysis | MTA | Security | Deploy smoke | Domain fidelity |
|-------|---------|------------------|-----------------|-----|----------|--------------|-----------------|
| M1 ANALYZE | derive compile optional | — | — | **Initial** analyze | — | — | profile completeness |
| M2 PLAN/SPEC | — | — | SDD readiness / §S.6 | — | — | — | — |
| M3 IMPLEMENT | **Yes** (sensor / verify_on_stop) | Task-scoped in `files_in_scope` | In-loop Sonar if available; else M4 | — | — | — | G-2 when HARVEST packet claims it |
| M4 VERIFY | **Yes** `mvn clean verify` | Full unit + IT + contract/characterization | **Sonar** | — | Sonar security rules | **Boot** `/q/health` | **G-1** (+ G-2 if harvest in story) |
| M5 CLOSE | Preflight | Regression suite green | Sonar | **Re-scan → G-3** | Pipeline security | Acceptance endpoints live | **G-4** (both-modes) |
| Factory (`main`) | Yes | Yes | Yes | Optional refresh | Yes | Yes | **Must not contradict M5 ACCEPT** — **required oracle** (Lead:implement). Steerer preflight is stopgap only until the check refuses factory without coherent M5 ACCEPT |

## Behavioural regression (Spring → Quarkus)

| Check | Boundary |
|-------|----------|
| **G-4 runtime parity** | External HTTP API |
| **G-1 characterization** | Internal logic |
| **G-2 harvest-fidelity** | Mechanical port |
| Contract/IT + wiring-check | API + DI wiring |
| Flyway + data ITs / G-4 on inventoried data endpoints | Data |
| Non-HTTP observable-effect parity (inventory-marked) | Side effects (§11.1) |

G-1 is necessary, not sufficient. G-4 closes external behaviour. INCONCLUSIVE
never ships.

## Failure routing

| Class | Triggers | Action |
|-------|----------|--------|
| **Auto fix / retry** | REFUSE (typed fixable) on M3–M4 | Fix session / re-queue; prior green stories untouched |
| **Human review queue** | INCONCLUSIVE; open `Q-*`; identity break; repeated `timed_out`; human waiver; Reviewer block | Kanban `blocked`; no story advance |
| **Automatic rollback** | Failed task's last bad tip | Revert to last green task commit on that story line only |
| **Block migration wave** | Missing acks; wave-level G-3 reopen; `main`/factory red with no fix; critical Sonar/security; Operator stop | Stop **new** stories; in-flight finish or park |

Completion requires **ACCEPT**, not "not REFUSE."

## Enforcement (Lead)

| Piece | Path |
|-------|------|
| Phase `required_checks` matrix | `.hermes/phase-dispatch.yaml` (M3/M4/M5/factory) |
| Matrix lint + checklist print | `.hermes/skills/validation-release-gates/scripts/check-phase-matrix.py` |
| Verdict routing (INCONCLUSIVE never ships) | `.hermes/skills/validation-release-gates/scripts/check-verdict-routing.py` |
| Wired into | `harness-validate`; M4/M5 `skills[]` |

```bash
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py .
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py . --print M5
python3 .hermes/skills/validation-release-gates/scripts/check-verdict-routing.py .
```

Non-blocking vs open Review / deferred items. Does not replace G-1…G-4 oracles.
