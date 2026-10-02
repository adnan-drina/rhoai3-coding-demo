# Stage 080 Hermes runtime — release record

The runtime is a qualified local fork of Hermes: the upstream base below plus
the ordered patch series in [patches/](patches/). This record names what was
published, how it was qualified, and which image each run uses. A pin edit
alone does not prove an image was built or deployed.

## Pending (not built): patches 0018 and 0019

Series 0001–0019 gives patched tree `94550e2ebbae08058c5ddbd4f09cbdf747a4f342` (verified from a fresh base);
the recipe pins that tree and 19 patches. No image is built, pushed or pinned: the current release below and
every run pin are unchanged. 0018 adds the same-result and same-call escalation triggers and the restart bound
(`same_result_count` 3, `same_call_count` 5, `max_starts_per_signature` 2 on `qwen3-8-27b-int4` only; v32
t_2f2509aa and t_449a35e4). 0019 makes a foreground `terminal` call cut at the 420 s foreground limit say that
the process was killed, the requested and applied limits, and the background + wait route. The Stage 050
profile carries the 0018 keys; a 0017 image ignores them (identical-call trigger only).

## Current release (2026-10-02, patch 0017: Qwen 3.8 loop escalation; v32 A/B package)

| Item | Identity |
|---|---|
| Source | release branch after `84534194` (patch 0017 `2f298e01`, configuration `08b92df9`, qwen3-8 compression kept at v30 `84534194`) |
| Base | `NousResearch/hermes-agent` `fcbd1076a93841fa88855acce810e342a5b78101` (tag `v2026.8.19`, 0.20.5) |
| Series | 0001–0017 (0017 = loop escalation to a thinking profile after the third identical-call note; configured only for `qwen3-8-27b-int4`) |
| Patched tree | `eaa713b9017a86ee217ed9d623f339da82603acc` (series re-verified from a fresh base by the recipe) |
| Typed repair executor | unchanged, sha256 `768ba69f…` |
| Image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:adda0aa36091b7cd15ce72eb735e875a3f630329843caf830ecc254d801acd5b` (tag `080-runtime-eaa713b9`; digest from `podman push --digestfile`) |
| Image stamp | `/opt/rhoai3/080.pins`: `hermes.patched_tree=eaa713b9…`, 17 patch checksums, `outcome_authority.code_sha256=c974f26d…` (unchanged), `typed_repair.jar_sha256=768ba69f…` |
| Pins | golden `.hermes/pins.json` (`hermes_agent.patched_tree`, `workspace_overlay.ws_080.digest`), `run-defaults.json`, scaffold `devfile.yaml`, app-migration skeleton devfile (both ws-080 components) |

Verification (evidence `tmp/next-migration-release/build/build-0017.log`): recipe steps 0–6 rc=0 and pushed; pulled by
registry digest: tree `eaa713b9`, 17 checksums including 0017, `agent/loop_escalation.py` present, authority and
executor stamps unchanged. Patch 0017: 24 new Hermes tests pass (escalated body only after the third-call note,
reasoning_effort xhigh inside chat_template_kwargs, edit / verification / turn-cap end conditions, guard still halts on
the fifth identical call, reasoning echoed to the next turn with model.reasoning_echo); existing guardrail and stop
modules pass. Not established here: a live model-driven escalation (the v32 A/B trial measures it).

## Previous release (2026-10-01, after-v30 package: typed repair executor H-6)

| Item | Identity |
|---|---|
| Source | main `8a332f91` (after-v30 package landed at `065949a7`, 143/143 non-container suites; executor re-pin `8a332f91`) |
| Base | `NousResearch/hermes-agent` `fcbd1076a93841fa88855acce810e342a5b78101` (tag `v2026.8.19`, 0.20.5) |
| Series | 0001–0016, unchanged |
| Patched tree | `37b147baef0c2678507c52e59e3b9231ab6ab64f` (re-verified from a fresh base by the recipe) |
| Typed repair executor | `/opt/rhoai3/typed-repair/typed-repair.jar`, sha256 `768ba69f22b77de314b62cadaeee8620862f0616f2bf8f4ce284d58a9368a765`, 17,685,168 bytes: the selected/owed fragment target (H-5/H-6); built twice with JDK 21.0.5, identical; equal to `pins.json` `typed_repair.executor.jar_sha256` |
| Image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:792fff3d6663bcc65c62d0efd10640c54837f54a14aebd03653986419604e4a8` (tag `080-runtime-37b147ba`, moved from `8b1fe34a`; digest from `podman push --digestfile`, read back by digest from the registry) |
| Image stamp | `/opt/rhoai3/080.pins`: `hermes.patched_tree=37b147ba…`, 16 patch checksums, `outcome_authority.code_sha256=c974f26d…` (unchanged), `typed_repair.jar_sha256=768ba69f…` |
| Build context | identity `ed4c2ccbe8e632dff57ce5c095bacdc28a88e76ccea34768cfc8809cd99fcb03` over 766 files |
| Pins | golden `.hermes/pins.json` `workspace_overlay.ws_080.digest`, `run-defaults.json`, scaffold `devfile.yaml`, app-migration skeleton devfile (both ws-080 components) |

Verification (evidence `tmp/next-migration-release/build/build-h6.log`, `registry-readback-h6.txt`,
`in-image-executor-h6.log`): recipe steps 0–6 rc=0 and pushed; pulled by registry digest, the same stamps, 16 patches
and jar bytes `768ba69f…`; the executor runs in the image on the worker PATH (JDK 21.0.12, network off, worker UID) and
a second run changes nothing. Not established here: a live model-driven run on this image.

## Previous release (2026-09-30, consolidated migration package)

| Item | Identity |
|---|---|
| Source | platform release `e772e344` (code qualified at `5280670b`, tree `038da64c`; reliability package, v29 corrections through `c9ab129d`, architect release prerequisites `ee7bc6d6`) |
| Base | `NousResearch/hermes-agent` `fcbd1076a93841fa88855acce810e342a5b78101` (tag `v2026.8.19`, 0.20.5) |
| Series | 0001–0016, unchanged from v26 |
| Patched tree | `37b147baef0c2678507c52e59e3b9231ab6ab64f` (re-verified from a fresh base by the recipe) |
| Typed repair executor | `/opt/rhoai3/typed-repair/typed-repair.jar`, sha256 `66d1b6f4c507dbf50e38dcf44bd2673267f5fef0d598618bc2c0fb8a9d6506ad`, 17,684,782 bytes, built by recipe step 2b from the golden's pinned sources (JDK 21.0.5) and equal to `pins.json` `typed_repair.executor.jar_sha256` |
| Image | `quay.io/rhoai3-coding-demo/rhoai3-ws-080@sha256:8b1fe34a9e8467010ac78a4dc36fa851a145c534142e2ebfdabe6ebc87be4ffd` (tag `080-runtime-37b147ba`, moved from the v26 image; config `sha256:85b3d0e0…`; digest from `podman push --digestfile` and read back from the registry) |
| Image stamp | `/opt/rhoai3/080.pins`: `hermes.patched_tree=37b147ba…`, 16 patch checksums, `outcome_authority.code_sha256=c974f26d…` (unchanged), `typed_repair.jar_sha256=66d1b6f4…` |
| Build context | identity `4f315cdecbe34f96873d8ee170b041495502e35ae64352efe2b7d369a8c220db` over 766 files (recipe, patches, authority tree, dashboard assets, MTA CLI archive `988db13d…`, typed repair jar) |
| Pins | golden `.hermes/pins.json` `workspace_overlay.ws_080.digest`, `run-defaults.json` `configuration.workspace_overlay.digest`, scaffold `devfile.yaml`, app-migration skeleton devfile (both ws-080 components); `validate.sh` requires them equal |

### Verification of the built image

Evidence: `tmp/next-migration-release/build/`.

- Recipe steps 0–6 rc=0: series re-verified, jar digest equal to the pin, stamps read back.
- Pulled by registry digest: the same stamps, 16 patch checksums, jar bytes `66d1b6f4…`.
- The typed repair executor runs in the image (`typed-repair.test.py RealExecutor`, network
  off, worker UID): the pinned jar translates a bounded handler fixture and a second run
  reports `already-in-required-form` with the file unchanged.
- The executor calls `java` from `PATH`. The workspace Hermes gateway runs with
  `${JAVA_HOME_21}/bin` first (observed in a live workspace), which gives 21.0.12; the image's
  bare default `PATH` resolves Java 17, on which the jar refuses to load (class file 65).
  The check therefore uses the gateway's `PATH`; a process started without it cannot run
  the executor.

Not established here: a live model-driven run on this image.

## Previous release (2026-09-29, v26)

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

## Superseded

| Image | Tree | Why superseded |
|---|---|---|
| `sha256:9147834b1ba45f6431bf2da6b33b62d47801b33de66e23cce18efcb007f4b1e1` | `37b147ba…` (0001–0016) | no typed repair executor; the consolidated package needs it |
| `sha256:2ea8ebd6860519c450730f72550201b191beda7374275a79c79ec811689c93b7` | `498e2faf…` (0001–0014) | 0014 false halts on new diagnostic facts; no record of the actual preload (v26 review F1/F2); ran v25 |
| `sha256:7490502c71993c86be593956702b1070fb63590e32ebdd8d037ff97fb61dcec2` | `ccb6a5ee…` (0001–0014) | 0014 false halts, 0006 and 0011 defects (review F1–F3); never ran a card |
| `sha256:6a8a69a38aa2973973039cb3492b08083bc98da2698cb7ba1ca088b4d6e5f291` | `8a3bb406…` (0001–0012) | no review-handoff stop-guard fix (0013), no near-duplicate loop halt |

## Runs

| Run | Image | Note |
|---|---|---|
| v21 (`spring-petclinic-rest-legacy-v21`) | adopted mid-run by recorded Operator interventions 14 (`7490502c`) and 15 (`2ea8ebd6`); see `tmp/v21-run/v21-validation.md` | created on `6a8a69a3` |
