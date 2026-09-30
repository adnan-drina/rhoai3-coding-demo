# Stage 080 Hermes runtime — release record

The runtime is a qualified local fork of Hermes: the upstream base below plus
the ordered patch series in [patches/](patches/). This record names what was
published, how it was qualified, and which image each run uses. A pin edit
alone does not prove an image was built or deployed.

## Current release (2026-09-29, v26)

| Item | Identity |
|---|---|
| Base | `NousResearch/hermes-agent` `fcbd1076a93841fa88855acce810e342a5b78101` (tag `v2026.8.19`, 0.20.5) |
| Series | 0001–0016, applied in filename order with `git apply --index` |
| Patched tree | `37b147baef0c2678507c52e59e3b9231ab6ab64f` (verified from a fresh base; equals the tested checkout) |
| Image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:9147834b1ba45f6431bf2da6b33b62d47801b33de66e23cce18efcb007f4b1e1` (tag `080-runtime-37b147ba`; digest read back from the registry) |
| Image stamp | `/opt/rhoai3/080.pins`: `hermes.patched_tree=37b147ba…`, 16 patch checksums, `outcome_authority.code_sha256=c974f26d…` (authority from commit `bb66b50e`, unchanged) |
| Build | [build-recipe/build-080-runtime-image.sh](build-recipe/build-080-runtime-image.sh) `<tree> --push`, from the versioned [build-recipe/](build-recipe/): syncs the recipe into the build context and refuses a difference, verifies the series from a fresh base, requires the recipe to pin the tree and patch count, reads back tree, patch count and authority stamp, records the context identity |
| Build context | identity `ea91e39fa4b19bc5750471213df88a3656d8ca7fe1b9f17f8047fb2a2add7261` over 765 files (recipe, patches, authority tree, dashboard assets, MTA CLI archive) |
| Pins | golden `.hermes/pins.json` `hermes_agent.patched_tree` and `workspace_overlay.ws_080.digest`; app-migration skeleton devfile (both ws-080 components). `run_control.runtime_gaps` compares the image stamp with the pin at launch |

### Qualification on the built image

Evidence: `tmp/v26-release-review/qualification-37b1/`, `tmp/v26-release-review/probes-in-image-37b1.txt`.

- `qualify_cards.py` (real `hermes` CLI, `kanban_db`, K2), against the v26 scaffold: 27/27.
- F1 probe against the installed guard: 25 distinct artifact pages and 40 one-new-diagnostic
  pages do not halt; a result whose only change is a runtime notice still halts
  (`near_duplicate_loop_halt`); identical reads halt by the fifth call.
- F2 probe with the installed native finalizer, the golden K2 hook and audit:
  - A partial preload is recorded `partial`: the hook blocks work with `PRELOAD_INCOMPLETE`,
    and the audit does not credit the missing skill.
  - A full preload is recorded `loaded` and credited.
  - Over initial (full), retry (partial) and rework (full) runs of one card, the retry is
    blocked and not credited from the earlier run.
- `native_board`, `native_m3_recovery`, `family_budget`, `v24_sequence` and the K2 selftest
  under the worker's `python3` (3.9.25).
- Runtime tests in the scratch clone: near-duplicate, tool_guardrails and repetition 45
  passed; the preload receipt tests 6 passed; skill_commands 29 and oneshot_skills 7 pass
  as on the base. `test_cli_preloaded_skills` and `test_stall_guards` did not run in that
  environment (missing runtime dependencies), identically with and without the series.

Not established here: a live model-driven run on this image.

### Review disposition (tmp/v26-release-review/DECISIONS.md)

| Finding | Disposition |
|---|---|
| F1 (0015) printed digests were masked as incidental; 25 artifact pages halted on page 13 | fixed: only the runtime's own appended notices are excluded; tool output keeps identifiers, digests and timestamps |
| F2 requested `--skills` were credited as loaded | fixed: 0016 records the native loader's actual result per run; the golden hook and audit consume only that record |
| Unversioned build recipe | fixed: [build-recipe/](build-recipe/) is the canonical recipe; the build context identity is recorded |

## Next build (not built, not published)

The recipe now also stages the **typed repair executor** (V26-1): step 2b of
`build-080-runtime-image.sh` builds `.hermes/skills/migration/fix-until-green/typed-repair`
from the golden's pinned sources (Maven, output outside `.hermes`, its OpenRewrite
recipe tests included), checks every shipped dependency's POM license
(`scripts/license-inventory.py --check`), refuses a jar whose sha256 is not
`pins.json` `typed_repair.executor.jar_sha256`, and copies it to
`/opt/rhoai3/typed-repair/typed-repair.jar` (root-owned, read-only, ~17.7 MB;
`080.pins` gains `typed_repair.jar_sha256`). The same sources, dependency jars and
JDK 21.0.5 reproduce the digest; another JDK gives another digest, which is re-pinned
deliberately in `pins.json` and the Dockerfile `ARG` together. Until an image carrying
it is built and pinned, `typed-repair.py` reports the executor as not installed and the
unit continues with its bounded agent procedure.

## Superseded

| Image | Tree | Why superseded |
|---|---|---|
| `sha256:2ea8ebd6860519c450730f72550201b191beda7374275a79c79ec811689c93b7` | `498e2faf…` (0001–0014) | 0014 false halts on new diagnostic facts; no record of the actual preload (v26 review F1/F2); ran v25 |
| `sha256:7490502c71993c86be593956702b1070fb63590e32ebdd8d037ff97fb61dcec2` | `ccb6a5ee…` (0001–0014) | 0014 false halts, 0006 and 0011 defects (review F1–F3); never ran a card |
| `sha256:6a8a69a38aa2973973039cb3492b08083bc98da2698cb7ba1ca088b4d6e5f291` | `8a3bb406…` (0001–0012) | no review-handoff stop-guard fix (0013), no near-duplicate loop halt |

## Runs

| Run | Image | Note |
|---|---|---|
| v21 (`spring-petclinic-rest-legacy-v21`) | adopted mid-run by recorded Operator interventions 14 (`7490502c`) and 15 (`2ea8ebd6`); see `tmp/v21-run/v21-validation.md` | created on `6a8a69a3` |
