# paved-road-m3 fixtures

Each fixture is an official kanban log (`official.log`) plus the loop record
(`verification/loop/steps.json`) the audit grades against.

- `green-m3` — skill_view, brief, patches, run-verify, advance → `OK: ACCEPTED`; the record names the card as an accepted step → PASS.
- `reverted-m3` — advance `[exit 1]` with `REVERTED`; the record names the card in `rejected` → PASS (a reverted attempt is a complete, recorded outcome).
- `silent-no-advance` — the worker never ran advance.py → REFUSE (silence).
- `refused-no-verdict` — advance `[exit 1]` was a refusal (`LOOP_WRONG_CARD`); the record does not name the card → REFUSE (a refused advance is not a verdict, whatever the prose says).
- `no-skill-view` — everything ran but the index skill was never viewed → REFUSE (path mention is not follow).
