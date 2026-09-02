# v9 M2 — spec-kit invoked and failed, tasks.md hand-authored

Official Hermes task log for `t_af875a24` (v9 `M2 PLAN`), captured live
2026-08-26 before the workspace was recycled.

**Why this exists.** It is the negative-half control for
`assert-card-performed` (GATE-VALIDATION-DESIGN.md §3). It is the only
artefact showing the failure mode the gate must catch:

- `specify workflow run speckit` — **12 invocations**
- `Unknown skill(s): speckit-specify` — **2 failures**
- `create-new-feature.sh` then a hand-authored `tasks.md`
- `assert-m2-speckit-conformance.py` — **exit 1, then OK** after the
  worker created the missing artefact by hand
- the card then `kanban_complete`d

`assert-card-performed` MUST REFUSE this log. A version that passes it has
not implemented the check.

**Provenance:** `$HERMES_HOME/kanban/logs/t_af875a24.log` on
`gs-rest-service-v9`, golden `96d6e790`, harness `533af7a0`. Same-uid as the
worker — provenance, not proof.
