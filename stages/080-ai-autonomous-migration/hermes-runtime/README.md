# Stage 080 Hermes runtime patch: B11 tool-loop halt

This directory holds a small patch series for the pinned Hermes runtime in the Stage 080 workspace image, together with its qualification tests and evidence. The series fixes one problem. A worker that repeats the same successful tool call is never stopped by the pinned runtime. The fix is design item B11 in `tmp/v12-run-20260924/architect-durable-fixes-design.md`.

| | |
|---|---|
| Base runtime | `NousResearch/hermes-agent` tag `v2026.8.19`, commit `fcbd1076a93841fa88855acce810e342a5b78101`, version 0.20.5 |
| Patched runtime identity | git tree `a09b3b45fe2fb0f98665cc2bb3bbf874ca2b4d48` (run `git write-tree` after applying the series to a clean checkout of the base) |
| Files touched | `agent/tool_guardrails.py`, `run_agent.py`, `agent/tool_executor.py`, `agent/turn_finalizer.py`, `tests/agent/test_tool_guardrails.py` |
| Upstream source | `76648a7faf7822cdd6c0e147c35857e15780c1af` ("identical-call streaks hard-stop any tool on unattended platforms"), which is an ancestor of `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` |

## The problem at the pin

The pinned runtime never stops this loop. In the live v12 run, one worker repeated `find src/main/java -name PetDto.java` more than 78 times, and another ran `cat <file>` 50 times. Both workers had `tool_loop_guardrails.hard_stop_enabled: true`. The runtime has three gaps:

- **Exempt tool.** `terminal` is in `MUTATING_TOOL_NAMES`, so the `idempotent_no_progress` block in `before_call` never applies to it.
- **Failures only.** The exact-failure and same-tool-failure stops count failing calls only.
- **Notice without a stop.** `observe_call` tracks identical calls, but only to add a notice and replace repeated results with a stub. The runtime reads its guard decision from `after_call` before `observe_call` runs. Backporting only the upstream detector would therefore record a halt that nothing acts on.

## What the series does

Apply the four patches in order. Patch 0001 is the upstream backport. Patches 0002 to 0004 are small local additions that the B11 design requires.

| Patch | Origin | Functions changed | Effect |
|---|---|---|---|
| `0001-fix-guardrails-identical-call-streaks-hard-stop-any-.patch` | Upstream `76648a7faf`, backported. Only the controller hunk, the runtime hunk and their tests are taken. | `ToolCallGuardrailController.observe_call`, `AIAgent._append_guardrail_observation` | When hard stops are on, the consecutive identical-call streak (same tool, same full canonical arguments, same result) halts **any** tool at `hard_stop_after.idempotent_no_progress`, which defaults to 5. The halt uses the code `identical_call_streak_halt`. The runtime then sets this halt as the turn's halt decision. The existing `guardrail_halt` branch in `agent/conversation_loop.py` ends the turn after the tool batch and before any further model request. Pollers in `STALL_GUARD_REPEATABLE_TOOLS` (`process`) and tools ending in `*_get_result` or `*_poll` remain exempt. One test is adapted: at this pin the poller is named `process`, not `process_manage`. The upstream `non_interactive_hard_stop_enabled` default and docs hunk are left out because nothing at this pin reads that key, and our config sets `hard_stop_enabled: true` explicitly. |
| `0002-fix-guardrails-terminal-transport-metadata-cannot-hi.patch` | Local | `observe_call`, new `_streak_identity_hash`, `_TERMINAL_TRANSPORT_KEYS` | Streak identity ignores known per-call transport keys of the `terminal` envelope. `full_output_path` (the spill file is named per call, `out-<time>-<pid>-<id>.log`) and `truncation_note` (which embeds that path) are emitted at this pin. The timing keys (`duration`, `duration_ms`, `duration_seconds`, `elapsed`, `elapsed_ms`, `elapsed_seconds`) are not emitted by the pinned terminal tool; they are stripped in case a result-transform hook adds them. The `output`, `exit_code`, `error` and all other fields still count toward identity. Reference stubs still require the full result to be byte-identical. |
| `0003-fix-guardrails-never-emit-a-result-reference-stub-wh.patch` | Local | `AIAgent._append_guardrail_observation` (new `messages=` parameter), new `AIAgent._result_reference_retrievable`, controller `result_reference_call_id`, `persisted_result_path`, `rebase_result_reference`, and both call sites in `agent/tool_executor.py` | A stub is emitted only while its referenced payload is still in the outgoing `messages`, or when a persisted spill path was recorded for it. Otherwise the fresh content is returned once, and this call becomes the new reference. The streak count is not reset, so rehydrating content is not progress. |
| `0004-fix-kanban-a-guardrail-halted-worker-records-a-faile.patch` | Local. Mirrors the pinned `_record_kanban_budget_exhausted`. | New `_record_kanban_guardrail_halt` and `_kanban_failure_limit` in `agent/turn_finalizer.py`; `finalize_turn` | When a turn ends with `guardrail_halt` inside a kanban worker, the worker records a failed run through the native `_record_task_failure`. See the next section. |

Every change is gated on `tool_loop_guardrails.hard_stop_enabled` (and `agent.stall_guards`, which defaults to true). Interactive sessions that only warn behave as before.

## How a halted worker ends

The deployed dispatcher launches each worker as `hermes -p implementer --cli --accept-hooks chat -q "work kanban task <id>"`, without `-Q`. This was checked end to end with a fake provider, both before and after the patch, in `test_halt_ends_process_without_false_completion`.

| | Unpatched `fcbd1076` | Patched (tree `a09b3b45`) |
|---|---|---|
| When the worker stops | It never stops on the loop. It runs until the iteration budget (`agent.max_turns`). With `max_turns: 12`, one worker process made 28 tool-enabled model requests (33 in total, counting summary and title requests). It hit the budget at 12/12 and recorded `timed_out`, then got another turn from the budget summary and continuation path. It hit the budget again at 16/16, which tripped the breaker (`gave_up`, blocked). | After the 5th identical successful call. It made exactly 5 agent model requests and no request after the halting tool result. |
| Process exit code | 0 | **0.** The non-quiet `chat -q` path always exits 0 here, so the board is where the outcome is recorded. |
| Board record | Iteration budget → `timed_out` | The worker closes its own run through `_record_task_failure(outcome="crashed", release_claim=True, end_run=True)` with the error `STOP WORKER_TOOL_LOOP: tool terminal, guardrail identical_call_streak_halt, count 5, args_sha256 <16 hex> — the worker was halted before another model request; this run did not complete the task`. Only a hash of the arguments is recorded, never the raw argv. `last_failure_error` is set to the same text. |
| Counts toward `max_retries` / `kanban.failure_limit` | Yes, as `timed_out` | **Yes.** `consecutive_failures` goes up by 1. The limit is the card's `max_retries` if set, then `kanban.failure_limit` from the worker's config, then `DEFAULT_FAILURE_LIMIT = 2`. The deployed value is also 2. |
| Respawn | Yes, until the breaker trips | **Yes, native.** The claim is released and the task returns to `ready`, or to `review` for review claims. The next `dispatch_once` respawns it. When the limit is reached, the task goes to `blocked` with a `gave_up` event (`trigger_outcome: crashed`, and `guardrail` metadata carrying the code, count and args hash), and the dispatcher does not spawn it again. The test shows two halts leading to `blocked`. |
| Protocol violation? | n/a | **No.** The dispatcher tick finds the task no longer `running`, so `detect_crashed_workers` returns `[]` and nothing is counted twice. |
| The halted turn can be re-opened by `kanban_stop` | n/a | No. The stop nudge only fires on a text-response exit, and `guardrail_halt` exits the loop directly. |

**With patches 0001 and 0002 only (without 0004)**, the halt fires correctly but the worker exits 0 while the task is still `running`. The dispatcher then records a `protocol_violation` (`outcome: crashed`, `protocol_violation: true`). That path does **not** increment `consecutive_failures`. It is bounded by a separate, hard-coded violation streak of 3 (`_PROTOCOL_VIOLATION_FAILURE_LIMIT`, overridden by the card's `max_retries`). Its retry guidance tells the next worker: "If the prior run already did the work, verify it and report the result via kanban_complete". That guidance invites a false completion. This was observed in a run and is why patch 0004 exists.

For in-process callers, the turn result has `turn_exit_reason == "guardrail_halt"` and `result["guardrail"]` set to the decision. `result["completed"]` stays `True` at this pin and upstream, because it only means a final response was produced. `failed` stays `False`. Kanban board state does not depend on either flag.

## Apply and test

```bash
# 1. A clean base checkout
git clone https://github.com/NousResearch/hermes-agent.git hermes-agent
cd hermes-agent
git checkout --detach fcbd1076a93841fa88855acce810e342a5b78101

# 2. Apply the series and check the patched identity
for p in <repo>/stages/080-ai-autonomous-migration/hermes-runtime/patches/0*.patch; do
  git apply --index "$p"
done
test "$(git write-tree)" = a09b3b45fe2fb0f98665cc2bb3bbf874ca2b4d48

# 3. Test environment (Python 3.11, the same as the image)
python3.11 -m venv ../hermes-venv
../hermes-venv/bin/pip install -e ".[dev]"

# 4. Qualification tests (fake provider only; no model or network)
cp -R <repo>/stages/080-ai-autonomous-migration/hermes-runtime/tests/rhoai3_b11 tests/rhoai3_b11
../hermes-venv/bin/python -m pytest -p no:cacheprovider -v tests/rhoai3_b11

# 5. Existing related upstream tests
../hermes-venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/run_agent/test_tool_call_guardrail_runtime.py tests/run_agent/test_agent_guardrails.py \
  tests/agent/test_tool_guardrails.py tests/agent/test_stall_guards.py \
  tests/run_agent/test_turn_completion_explainer.py tests/run_agent/test_sequential_tool_timeout.py \
  tests/run_agent/test_start_order_gate.py tests/run_agent/test_tool_activity_heartbeat.py \
  tests/agent/test_turn_finalizer_*.py \
  tests/hermes_cli/test_kanban_core_functionality.py tests/hermes_cli/test_kanban_blocked_sticky.py
```

To reproduce the failing baseline, skip step 2 and run step 4. `test_halt_ends_process_without_false_completion` starts the real worker through `kanban_db.dispatch_once`, and the worker imports the tree that the venv's editable install points at. Run that test from the tree under test, or set `PYTHONPATH` to it.

## Image build

`Dockerfile.hunk.txt` is a unified diff for `workspace-images/Dockerfile`. It changes the `rhoai3-ws-080-unsigned` stage as follows:

- The operator copies `patches/*.patch` into `workspace-images/out/hermes-runtime-patches/`, which is in the build context.
- After the clone, the SHA check and `assert-hermes-source-pin.py`, the stage runs `git apply --index` on each patch.
- The build fails unless `git write-tree` equals `HERMES_PATCHED_TREE`.
- The stage records the patch checksums in `/opt/rhoai3/hermes-runtime-patches.sha256` and adds `hermes.source_sha` and `hermes.patched_tree` to `/opt/rhoai3/080.pins`.

`hermes --version` still reports 0.20.5, because the version constants are not touched. Use the tree hash in `080.pins` to tell a patched image from an unpatched one. The hunk has not been applied or built.

## What this does not cover

- **Worker recovery policy** is golden-side (commit "a halted worker gets one automatic recovery ..."): K4 mints loop cards with `max_retries` 2 (`k4_schema.LOOP_MAX_RETRIES`), so the first guard halt respawns the card once and the second blocks it with the `gave_up` guardrail metadata; `brief.py` hands the respawned run its unaccepted candidate (`candidate_on_tree`) and the one next action. The count lives in the kanban database, outside product Git. Not covered anywhere yet: a named `WORKER_RECOVERY_EXHAUSTED` code (the native `gave_up` event carries the halt metadata instead).
- **Multi-call cycles** such as A, B, A, B. Upstream detects these with a later `identical_cycle_halt`, which this series does not include. A worker that alternates two identical calls is still bounded only by the iteration budget.
- **Pollers.** `process` and `*_get_result` / `*_poll` stay exempt from the streak halt, with no per-operation deadline. They are bounded only by the turn's iteration budget, as the test shows. Polling through `terminal` is not exempt.
- **Persisted-path existence.** The stub fix trusts a recorded persisted path and does not check that the file still exists.
- **Live compressor summary.** The compression regression uses the pinned compressor's deterministic prune pass (`ContextCompressor._prune_old_tool_results`). It does not use the LLM summary path.
- **Upstream threshold config.** `idempotent_tools` and `mutating_tools` are still not read from YAML at this pin, as noted in the design.
- **Sampling.** B4's `presence_penalty` and `repetition_penalty` request check is not part of this series.
- **Where it was run.** Everything was checked on macOS with Python 3.11 against a local clone, with a scripted fake provider on loopback. Nothing was checked against a live cluster, an image build, or a real model.

## Evidence

`qualification-log.txt` in this directory holds the before and after output of the qualification tests and of the existing upstream tests.
