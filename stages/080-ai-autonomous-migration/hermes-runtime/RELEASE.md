# Stage 080 Hermes runtime — release record

The runtime is a qualified local fork of Hermes: the upstream base below plus
the ordered patch series in [patches/](patches/). This record names what was
published, how it was qualified, and which image each run uses. A pin edit
alone does not prove an image was built or deployed.

## Current release (2026-09-28)

| Item | Identity |
|---|---|
| Base | `NousResearch/hermes-agent` `fcbd1076a93841fa88855acce810e342a5b78101` (tag `v2026.8.19`, 0.20.5) |
| Series | 0001–0014, applied in filename order with `git apply --index` |
| Patched tree | `498e2faf0d481049111646eeb04e6cde20dcae1b` |
| Image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:2ea8ebd6860519c450730f72550201b191beda7374275a79c79ec811689c93b7` (tag `080-runtime-498e2faf`) |
| Image stamp | `/opt/rhoai3/080.pins`: `hermes.patched_tree=498e2faf…`, `outcome_authority.code_sha256=c974f26d…` (authority from commit `bb66b50e`, unchanged) |
| Build | `tmp/080-operator/build-080-runtime-image.sh <tree>`: verifies the series from a fresh base checkout, stages the patches and authority, sets the Dockerfile's expected tree and patch count, builds, reads the stamp back |
| Pins | golden `.hermes/pins.json` `hermes_agent.patched_tree` and `workspace_overlay.ws_080.digest`; app-migration skeleton devfile (both ws-080 components). `run_control.runtime_gaps` compares the image stamp with the pin at launch |

### Qualification on the built image

- `qualify_cards.py` (real `hermes` CLI, `kanban_db`, K2): 27/27.
- The independent review's probes (`tmp/hermes-runtime-review-2026-09-28/reproduce.py`, run
  against `/opt/hermes-agent` in the image): no halt on 14 distinct negative searches or
  14 distinct boilerplate files; the stop request is neither read nor acted on by a child
  execution and is scrubbed from child environments; two exhausted provider-429 turns exit 75
  and are reaped as `rate_limited`, card `ready`, 0 failures, cooldown held.
- `native_m3_recovery` and `native_board` under the worker's `python3` (3.9).
- Runtime tests in the scratch clone: focused 256 passed; `tests/agent` + `tests/hermes_cli`
  11670 passed, 10 failed — the same 10 fail on the previous tree (provider/auxiliary-client and
  review-surface tests). Evidence: `tmp/v21-fixes/qualification-498e`, `tmp/v21-fixes/hermes-runtime-fixes-report.md`.

Not established here: a live model-driven run on this image (see "Runs" below).

### Review disposition (tmp/hermes-runtime-review-2026-09-28/REVIEW.md)

| Finding | Disposition |
|---|---|
| F1 (0006) exhausted 429 booked as a task failure | fixed: exit 75 → native neutral `rate_limited` requeue with the pinned base's cooldown; auth/config errors still fail (upstream `be9d4369` closes the same gap; cited, not copied) |
| F2 (0014) near-duplicate halt stopped legitimate work | fixed: operands preserved (a new query or file is progress); the live loop shapes still halt |
| F3 (0011) stop request reached child executions | fixed: owned-worker context only; `HERMES_KANBAN_STOP_REQUEST` scrubbed for children; upstream isolation test passes |
| F4 README out of date | this record, and the README rows for the series and tree |

## Superseded

| Image | Tree | Why superseded |
|---|---|---|
| `sha256:7490502c71993c86be593956702b1070fb63590e32ebdd8d037ff97fb61dcec2` | `ccb6a5ee…` (0001–0014) | 0014 false halts, 0006 and 0011 defects (review F1–F3); never ran a card |
| `sha256:6a8a69a38aa2973973039cb3492b08083bc98da2698cb7ba1ca088b4d6e5f291` | `8a3bb406…` (0001–0012) | no review-handoff stop-guard fix (0013), no near-duplicate loop halt |

## Runs

| Run | Image | Note |
|---|---|---|
| v21 (`spring-petclinic-rest-legacy-v21`) | adopted mid-run by recorded Operator interventions 14 (`7490502c`) and 15 (`2ea8ebd6`); see `tmp/v21-run/v21-validation.md` | created on `6a8a69a3` |
