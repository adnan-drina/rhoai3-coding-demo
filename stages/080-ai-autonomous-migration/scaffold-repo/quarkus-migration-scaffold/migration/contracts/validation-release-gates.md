# Validation and release gates

**Status:** binding for migration workspace · mirrors **AD-H §18**  
**Sources:** Architect plan / AD-H §18 (Operator ACK pending on ledger)  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

Cross-refs: W2 G-1…G-4 (`domain-gates`), AD-H §16 validator/acks, AGENTS
factory bar, `.hermes/phase-dispatch.yaml` M4/M5.

**Defaults:** no per-task full G-4; no wave-wide wipe of prior **full** ACCEPT
stories; G-4 primary external-API oracle; data via Flyway + IT + G-4 on
inventoried data endpoints — not a DB snapshot gate.

## Composition vs phase matrix (AD-H §18.0)

M4 story ACCEPT is **PROVISIONAL** (G-1 volume+substance; kill-ratio not PASS
until threshold pinned). **G-4 at M5** closes G-1 residue for **full ACCEPT**.
If M5 G-4 REFUSE/INCONCLUSIVE → **re-open that story** (not wave wipe).
`harness-validate` fixture green ≠ live specimen prove.

## Gates after each stage

| Stage | Compile | Unit/IT/contract | Static analysis | MTA | Security | Deploy smoke | Domain fidelity |
|-------|---------|------------------|-----------------|-----|----------|--------------|-----------------|
| M1 ANALYZE | derive compile optional | — | — | **Initial** analyze | — | — | profile completeness |
| M2 PLAN/SPEC | — | — | SDD readiness / §S.6 | — | — | — | — |
| M3 IMPLEMENT | **Yes** (sensor / verify_on_stop) | Task-scoped in `files_in_scope` | In-loop Sonar if available; else M4 | — | — | — | G-2 when HARVEST packet claims it |
| M4 VERIFY | **Yes** `mvn clean verify` | Full unit + IT + contract/characterization | **Sonar** | — | Sonar security rules | **Boot** `/q/health` | **G-1 volume+substance** (**provisional** ACCEPT) + G-2 if harvest |
| M5 CLOSE | Preflight | Regression suite green | Sonar | **Re-scan → G-3** | Pipeline security | Acceptance endpoints live | **G-4** (both-modes) — **full ACCEPT** |
| Factory (`main`) | Yes | Yes | Yes | Optional refresh | Yes | Yes | **Must not contradict M5 ACCEPT** — **required oracle** |

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
| **Story re-open** | M5 G-4 REFUSE/INCONCLUSIVE after M4 provisional | Re-open **that** story; clear provisional ACCEPT |
| **Block migration wave** | Missing acks; wave-level G-3 reopen; `main`/factory red with no fix; critical Sonar/security; Operator stop | Stop **new** stories; in-flight finish or park |

**Full** completion requires **M5 ACCEPT** (incl. G-4), not M4 provisional.

## Enforcement (Lead)

| Piece | Path |
|-------|------|
| Phase `required_checks` matrix | `.hermes/phase-dispatch.yaml` (M3/M4/M5/factory) |
| Matrix lint + checklist print | `.hermes/skills/validation-release-gates/scripts/check-phase-matrix.py` |
| Verdict routing + §18.0 composition | `.hermes/skills/validation-release-gates/scripts/check-verdict-routing.py` |
| Factory ↔ M5 **full** ACCEPT oracle | `.hermes/skills/validation-release-gates/scripts/check-factory-m5.py` |
| Verdict field schema | `migration/schemas/verdict.md` |
| Wired into | `harness-validate`; M4/M5 `skills[]` |

```bash
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py .
python3 .hermes/skills/validation-release-gates/scripts/check-phase-matrix.py . --print M5
python3 .hermes/skills/validation-release-gates/scripts/check-verdict-routing.py .
python3 .hermes/skills/validation-release-gates/scripts/check-factory-m5.py .
```

`must_not_contradict_m5_accept` is a **required oracle**, not an aspirational
label. Does not replace G-1…G-4 oracles.
