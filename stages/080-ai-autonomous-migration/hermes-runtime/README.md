# Stage 080 Hermes runtime patch series (B11, B3/B4, R2)

This directory holds a small patch series for the pinned Hermes runtime in the Stage 080 workspace image, together with its qualification tests and evidence. Patches 0001–0004 fix design item B11 in `tmp/v12-run-20260924/architect-durable-fixes-design.md`: a worker that repeats the same successful tool call is never stopped by the pinned runtime. Patches 0005–0006 turn incomplete model output (B4) and a persistent HTTP 429 (B3) into named failed runs; `b3-b4/README.md` documents them. Patch 0007 enforces the run's declared request allowance, item R2 in `tmp/v12-run-20260924/V13-ARCHITECT-RELEASE-REVIEW.md`, corrected per `tmp/v12-run-20260924/V13-PACER-FINAL-REVIEW.md`; see the section on the request pacer below. Patch 0008 keeps explicit per-call auxiliary values (the short micro-summary's temperature and output cap) from being overridden by a task's configured `extra_body`.

| | |
|---|---|
| Base runtime | `NousResearch/hermes-agent` tag `v2026.8.19`, commit `fcbd1076a93841fa88855acce810e342a5b78101`, version 0.20.5 |
| Patched runtime identity | git tree **`32be3bd0617936952a1ed7a4d8718accd8c4661c`** for the full series 0001–0010 (run `git write-tree` after applying the series to a clean checkout of the base). Intermediate trees: 0001–0004 `a09b3b45fe2fb0f98665cc2bb3bbf874ca2b4d48`; 0001–0006 `87a39dca63bca478e1ab93e9ce24ad757de25f8f`; 0001–0007 `6d6efd1992525da692f2f0f7f23881cf65f3999a`; 0001–0008 `101ca3d1da753267ffcb7f9b280f09258085256a` (the v15 runtime); 0001–0009 `3e219090f61deb3a2676e86c73571f502a886970`. Tree `9a00357c…` (0010 before the retention amendment) is superseded. These trees are superseded: `433f0c6f…` (0001–0007 before the final pacing review) and `374562df…` (0001–0008 before the request-ownership correction). |
| Files touched | `agent/tool_guardrails.py`, `run_agent.py`, `agent/tool_executor.py`, `agent/turn_finalizer.py`, `agent/conversation_loop.py`, `agent/agent_runtime_helpers.py`, `agent/auxiliary_client.py`, `agent/chat_completion_helpers.py`, `cli.py`, `hermes_cli/kanban_db.py`, new `agent/request_pacer.py`, `tests/agent/test_tool_guardrails.py` |
| Upstream source | `76648a7faf7822cdd6c0e147c35857e15780c1af` ("identical-call streaks hard-stop any tool on unattended platforms"), which is an ancestor of `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` |

## The problem at the pin

The pinned runtime never stops this loop. In the live v12 run, one worker repeated `find src/main/java -name PetDto.java` more than 78 times, and another ran `cat <file>` 50 times. Both workers had `tool_loop_guardrails.hard_stop_enabled: true`. The runtime has three gaps:

- **Exempt tool.** `terminal` is in `MUTATING_TOOL_NAMES`, so the `idempotent_no_progress` block in `before_call` never applies to it.
- **Failures only.** The exact-failure and same-tool-failure stops count failing calls only.
- **Notice without a stop.** `observe_call` tracks identical calls, but only to add a notice and replace repeated results with a stub. The runtime reads its guard decision from `after_call` before `observe_call` runs. Backporting only the upstream detector would therefore record a halt that nothing acts on.

## What the series does

Apply the ten patches in order. Patch 0001 is the upstream backport. Patches 0002 to 0004 are small local additions that the B11 design requires. Patches 0005 to 0008 are local additions for B3/B4 and R2. Patches 0009 and 0010 implement V15-1 (`tmp/v15-run-20260925/V15-1-DURABLE-QUOTA-DESIGN.md`): change 1 and change 2, as separate patches.

| Patch | Origin | Functions changed | Effect |
|---|---|---|---|
| `0001-fix-guardrails-identical-call-streaks-hard-stop-any-.patch` | Upstream `76648a7faf`, backported. Only the controller hunk, the runtime hunk and their tests are taken. | `ToolCallGuardrailController.observe_call`, `AIAgent._append_guardrail_observation` | When hard stops are on, the consecutive identical-call streak (same tool, same full canonical arguments, same result) halts **any** tool at `hard_stop_after.idempotent_no_progress`, which defaults to 5. The halt uses the code `identical_call_streak_halt`. The runtime then sets this halt as the turn's halt decision. The existing `guardrail_halt` branch in `agent/conversation_loop.py` ends the turn after the tool batch and before any further model request. Pollers in `STALL_GUARD_REPEATABLE_TOOLS` (`process`) and tools ending in `*_get_result` or `*_poll` remain exempt. One test is adapted: at this pin the poller is named `process`, not `process_manage`. The upstream `non_interactive_hard_stop_enabled` default and docs hunk are left out because nothing at this pin reads that key, and our config sets `hard_stop_enabled: true` explicitly. |
| `0002-fix-guardrails-terminal-transport-metadata-cannot-hi.patch` | Local | `observe_call`, new `_streak_identity_hash`, `_TERMINAL_TRANSPORT_KEYS` | Streak identity ignores known per-call transport keys of the `terminal` envelope. `full_output_path` (the spill file is named per call, `out-<time>-<pid>-<id>.log`) and `truncation_note` (which embeds that path) are emitted at this pin. The timing keys (`duration`, `duration_ms`, `duration_seconds`, `elapsed`, `elapsed_ms`, `elapsed_seconds`) are not emitted by the pinned terminal tool; they are stripped in case a result-transform hook adds them. The `output`, `exit_code`, `error` and all other fields still count toward identity. Reference stubs still require the full result to be byte-identical. |
| `0003-fix-guardrails-never-emit-a-result-reference-stub-wh.patch` | Local | `AIAgent._append_guardrail_observation` (new `messages=` parameter), new `AIAgent._result_reference_retrievable`, controller `result_reference_call_id`, `persisted_result_path`, `rebase_result_reference`, and both call sites in `agent/tool_executor.py` | A stub is emitted only while its referenced payload is still in the outgoing `messages`, or when a persisted spill path was recorded for it. Otherwise the fresh content is returned once, and this call becomes the new reference. The streak count is not reset, so rehydrating content is not progress. |
| `0004-fix-kanban-a-guardrail-halted-worker-records-a-faile.patch` | Local. Mirrors the pinned `_record_kanban_budget_exhausted`. | New `_record_kanban_guardrail_halt` and `_kanban_failure_limit` in `agent/turn_finalizer.py`; `finalize_turn` | When a turn ends with `guardrail_halt` inside a kanban worker, the worker records a failed run through the native `_record_task_failure`. See the next section. |
| `0005-fix-kanban-incomplete-model-output-ends-a-worker-run.patch` | Local | `conversation_loop.py` incomplete-output returns (new `incomplete_output` key), new `turn_finalizer._record_kanban_worker_stop` and `record_kanban_turn_stop`, `AIAgent.run_conversation` | Output still truncated after the bounded recovery ends as `STOP MODEL_OUTPUT_INCOMPLETE …`, a failed run; the partial tool call is never executed (it was not at the pin either). The shared recorder is gated on `is_dispatcher_owned_worker_context()`, so a delegated child or an in-process cron job cannot close the worker's card. This corrects 0004, which had no such gate. |
| `0006-fix-kanban-a-persistent-provider-rate-limit-ends-a-w.patch` | Local | rate-limit terminal return in `conversation_loop.py` (`api_attempts`, `retry_after`), `record_kanban_turn_stop` | After 3 attempts, a persistent HTTP 429 ends as `STOP MODEL_QUOTA …`, a failed run. The wording avoids the dispatcher's respawn-blocker pattern. The pinned retry layer is unchanged: Retry-After is honoured, backoff is otherwise jittered, and there is one retry layer. |
| `0007-feat-transport-per-run-model-request-pacer-from-a-sh.patch` | Local | new `agent/request_pacer.py`; hook attached at `agent_runtime_helpers.py` (primary client) and `auxiliary_client.py` (sync, async and Vertex aux clients); per-attempt reservation and tagging, plus exhaustion handling, in `conversation_loop.py`; own-attempt stale-watchdog exemption and cancellation binding in `chat_completion_helpers.py` (streaming); `record_kanban_turn_stop` | Per-run sliding-window request allowance, shared by every Hermes process of the run through a flock'd ledger. Each request attempt owns its reservation, deadline, cancellation and waiting status, and hands them to the transport explicitly. See below. |
| `0008-fix-auxiliary-explicit-per-call-sampling-and-output-.patch` | Local | `auxiliary_client._build_call_kwargs` | A task's configured `extra_body` supplies only what the call did not set. An explicit `temperature` wins. An explicit `max_tokens` is sent as `min(explicit, configured)`, so it never raises a configured bound. Without this, the OpenAI SDK merges `extra_body` over the top-level body. |
| `0009-fix-kanban-a-local-request-allowance-stop-is-a-neutr.patch` | Local (V15-1 change 1) | `RequestBudgetExhausted.deferral`; the budget result in `conversation_loop.py`; `turn_finalizer._record_kanban_local_deferral` and `kanban_worker_exit_code`; `cli.py` (quiet and non-quiet `chat -q` exit); `kanban_db.record_local_budget_deferral`, `detect_crashed_workers`, `check_respawn_guard` | A local allowance stop is a **neutral deferral on the pinned native temporary-rate-limit path**, not a failed run. The worker persists a structured `local_budget_deferral` bound to its run, then exits with `KANBAN_RATE_LIMIT_EXIT_CODE` (75). The reaper ends the run as `rate_limited` whatever the exit status: source-phase requeue, no `_record_task_failure`, no counter increment or reset. The respawn guard holds the same card until `retry_not_before` **and** a free slot in the shared ledger. See below. |
| `0010-feat-transport-reserved-and-settled-token-accounting.patch` | Local (V15-1 change 2) | `agent/request_pacer.py` (token mode: reservation, settlement, settlement wrapper, mode-aware capacity peek); `kanban_db._request_capacity` | Token mode: every physical HTTP attempt reserves `C`; admission is `settled_in_window + open_reservations + C <= B`; settlement to validated usage happens exactly once at the terminal response. There is **no request-count ceiling**. See below. |

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
test "$(git write-tree)" = 32be3bd0617936952a1ed7a4d8718accd8c4661c

# 3. Test environment (Python 3.11, the same as the image)
python3.11 -m venv ../hermes-venv
../hermes-venv/bin/pip install -e ".[dev]"

# 4. Qualification tests (fake provider only; no model or network)
cp -R <repo>/stages/080-ai-autonomous-migration/hermes-runtime/tests/rhoai3_b11 tests/rhoai3_b11
cp -R <repo>/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/tests/rhoai3_b3b4 tests/rhoai3_b3b4
../hermes-venv/bin/python -m pytest -p no:cacheprovider -v tests/rhoai3_b11 tests/rhoai3_b3b4

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
- The build fails unless exactly 10 patches are present and `git write-tree` equals `HERMES_PATCHED_TREE` (`32be3bd0…`). The hunk is relative to `workspace-images/Dockerfile` as it stands now, with the 8-patch hunk already applied.
- The stage records the patch checksums in `/opt/rhoai3/hermes-runtime-patches.sha256` and adds `hermes.source_sha` and `hermes.patched_tree` to `/opt/rhoai3/080.pins`.

`hermes --version` still reports 0.20.5, because the version constants are not touched. Use the tree hash in `080.pins` to tell a patched image from an unpatched one. The hunk has not been applied or built.

## Request pacer (0007, review item R2)

Configuration comes from the environment, which the platform sets for migration runs. If either variable is unset, the pacer is off and behaviour is unchanged.

| Variable | Meaning |
|---|---|
| `RHOAI3_REQUEST_BUDGET` | `<n>/<window_seconds>`; the value comes from the model profile table (`quota.max_requests_per_window`/`window_seconds`, 190/3600 at the time of writing) |
| `RHOAI3_REQUEST_LEDGER` | shared ledger file; dest-init sets `/projects/.platform/run-control-state/requests.log` (the parent directory is created on first use) |
| `RHOAI3_REQUEST_BUDGET_MAX_WAIT` | longest **total** wait for one request's slot, default 900 s |

- **One slot per HTTP request.** Every model HTTP request takes one slot. Each granted slot is one appended line, `<epoch> <pid> <label>`, written under an exclusive `flock`. The ledger is shared by concurrent processes and survives restarts; lines older than the window are ignored and never rewritten.
- **Where it is enforced.** An httpx `request` event hook is attached at the OpenAI client construction choke points. Every HTTP attempt passes through it, including SDK-internal retries (0 at this pin), Hermes 429 retries, truncation cap-boost retries and stream reconnects. Only POSTs are counted.

  | Client | Attached at (0007) |
  |---|---|
  | Main agent client | `agent/agent_runtime_helpers.py:2593`, `create_openai_client` |
  | Every sync auxiliary client (compression, micro-summary, title, vision, approval, …) | `agent/auxiliary_client.py:289`, `_create_openai_client` |
  | Async auxiliary client | `agent/auxiliary_client.py:6199` |
  | Vertex auxiliary client | `agent/auxiliary_client.py:6983` |

  Reviewer and other profiles are separate Hermes processes. They share the ledger through the environment.
- **Request ownership: one `PacedAttempt` per main-loop API attempt.**
  - `request_pacer.reserve` runs before `run_llm_execution_middleware` (`conversation_loop.py`, right before the API call). It creates the attempt and takes its slot before the stream stale timer (`chat_completion_helpers.py:3739`) starts. The attempt owns that reservation, its original monotonic deadline (creation + `RHOAI3_REQUEST_BUDGET_MAX_WAIT`), its cancellation predicate and its `waiting` status.
  - The hand-off to the transport is explicit and independent of threads. `tag_kwargs` puts the attempt id on that attempt's own request (header `X-RHOAI3-Pace-Attempt`, via the SDK's `extra_headers`). The hook reads the header and **removes it before sending**, so the provider never sees it.
  - Only a request carrying the id consumes the reservation. An untagged request (any auxiliary call) always acquires its own slot, with its own deadline. A retried attempt is a new attempt with a new reservation. A stream reconnect of the same attempt acquires a new slot within the attempt's **original** deadline.
  - The main loop closes the attempt when the call returns. An unused reservation stays counted; there is no refund logic.
  - The wait touches worker activity and does not consume the iteration budget.
- **One total wait bound.** Every wait made for an attempt is charged against its one deadline: the elapsed time on a monotonic clock, and at least the sum of the sleeps taken. This covers the reservation and any reconnect. A competing process that keeps winning the expiring slots cannot extend it, and the reviewer's contention reproduction stops at 900 s. An auxiliary thread cannot take the main request's reservation: in the reviewer's case the main request now waits 600 s, not 1,200 s. The immediate stop is kept: when the first predicted slot already lies beyond the allowance, the caller stops at once without sleeping.
- **Cancellation** is checked before a reservation is consumed and before any request is admitted, including after waiting. The main loop binds the agent's interrupt. A stream attempt binds its own cancellation (superseded attempt or interrupt) to the paced attempt. An auxiliary caller can use `request_pacer.cancel_check` for its untagged requests. A cancelled attempt raises `RequestCancelledWhileWaiting`, sends nothing and takes no slot. This was tested from another thread, and on the async hook.
- **Stale watchdog.** A stream's watchdog exempts only **its own** attempt's pre-send wait (`PacedAttempt.waiting`); it treats that as activity. A waiting auxiliary request never pauses the watchdog of an already-sent, stalled stream.
- **Auxiliary timeouts.** An auxiliary request timeout does not include the pacer wait: httpx request hooks run before the transport timers.
- **When the window stays full.** If the next slot would push the total wait past the maximum, nothing is sent and the attempt is not retried. The turn ends with `model_stop=request_budget` and a structured deferral. Since 0009 this is a **neutral deferral**, not a failed run (see below). The message is: `STOP MODEL_REQUEST_BUDGET: <n> requests in <w>s already spent by this run; next slot at <UTC>; already waited <x>s, another <s>s exceeds the <max>s total wait allowed; …`. This wording does not match the dispatcher's respawn-blocker pattern.
- **Largest output per request.** On the main path it is **32768**, provided `model.max_tokens` is 8192 as the producer sets it:
  - Base cap: 8192.
  - Truncated tool-call retries: `min(8192·2^k, max(32768, requested))` (`conversation_loop.py:3978`).
  - Text-continuation retries: the same formula (`:6670`).
  - Output-cap error recovery only lowers the cap (`:5723`).
  - The 65536 fallback for Claude, MiniMax and Qwen3 in the Anthropic output-limits table is never used while `max_tokens` is set (`agent/transports/chat_completions.py` max_tokens priority).
- **Auxiliary calls** send no `max_tokens` of their own for this provider (`auxiliary_client._build_call_kwargs`: an explicit cap is kept only for Anthropic-compatible, NVIDIA, MoA and Gemini routes). The producer therefore sets `max_tokens: 32768` (`quota.max_output_tokens`) in `auxiliary.compression.extra_body`, together with the profile's request body. The SDK merges it into the body (commit 50463fa2). Measured on the wire (`b3-b4/test_b4_wire_payload.py`):
  - The full compression summary, which sets no cap or sampling itself, carries the full row and `max_tokens: 32768`.
  - With patch 0008, the short micro-summary keeps its own `temperature: 0.1` and `max_tokens: 1500`, and still carries the row's thinking-off and other sampling keys.

  Every path in the worker is bounded by 32768. Compression is the only live auxiliary slot on the main model; title generation and background review are disabled.
- **Where the pacer settings come from.** dest-init writes them into the **managed** `.env`, `$HERMES_MANAGED_DIR/.env`. The image sets `HERMES_MANAGED_DIR=/projects/.platform/hermes` (`workspace-images/Dockerfile`, 080 stage `ENV`). Hermes applies that file with override into `os.environ` at startup of every entry point. This is from pinned source:
  - `hermes_cli/env_loader.py:585-614`: `_apply_managed_env` loads `$HERMES_MANAGED_DIR/.env` with `override=True`.
  - It is called at the end of `load_hermes_dotenv`, `env_loader.py:539`.
  - `hermes_cli/main.py:708` calls it for the `hermes …` entry, which is every dispatched worker (`hermes -p <profile> --cli … chat -q`).
  - `cli.py:233` calls it for the CLI module.
  - `gateway/run.py:2081` calls it at gateway start, and again per turn through `_reload_runtime_env_preserving_config_authority`, `gateway/run.py:2106`.

  The dispatcher also passes its own `os.environ` to each worker (`kanban_db._default_spawn`, `env = dict(os.environ)`). Auxiliary and compression calls run inside the worker process, and the pacer reads `os.environ` on every request. It was measured: in `test_budget_from_managed_env_reaches_worker` the settings exist only in a managed `.env`, never in the dispatcher's environment. The worker loaded them and put one ledger slot per request into a ledger whose parent directory did not exist beforehand (`request_pacer._open_locked` creates it). Gateway: `test_gateway_process_calls_are_paced_from_managed_env` imports `gateway.run` in a separate process whose settings exist only in the managed `.env`, then makes the dispatcher-side kind of model call (`call_llm(task="triage_specifier")`). The call took a ledger slot. That shows a gateway process pacing its own model calls. The live gateway-embedded dispatcher, with its real triggers, was not run.

## Local-budget deferral (0009, V15-1 change 1)

**What changed.** A local allowance stop is predictable from the local ledger and sent nothing, so it is no longer a failed worker run. The pinned native path already has `KANBAN_RATE_LIMIT_EXIT_CODE = 75`, a neutral `rate_limited` run outcome, source-phase requeue and a respawn cooldown that deliberately bypasses `_record_task_failure`. Patch 0009 uses that path and does not add another board or scheduler. `schedule_task` is not used, because at this pin it only parks a card for external unblock.

**Worker side:**
- The worker writes one `local_budget_deferral` event bound to (task, worker run). It carries `accounting_mode`, `retry_not_before`, the model, the allowance and the reason. It is written while the task is still `running` and **before** the process exits. `retry_not_before` is when enough capacity becomes eligible, not merely when an old entry expires.
- It exits with 75 (`cli.py`, quiet and non-quiet `chat -q`).
- The candidate on the tree, verification evidence and the original deadline are untouched. Nothing is advanced, reverted or given a verdict.

**Reaper (`detect_crashed_workers`):**
- A run with a persisted deferral ends as `rate_limited` whatever the exit status, including after a dispatcher restart that lost the reap record.
- The task returns to the phase it came from, `ready` or `review` (the reviewer origin is kept).
- `consecutive_failures` and product counters are neither incremented nor reset.
- The run metadata carries `local_budget_deferral`, `retry_not_before`, `accounting_mode` and `model`.
- `last_failure_error` reads `LOCAL_BUDGET_WAIT: …; the previous run's work stays on the tree`. The resumed worker sees this in its `kanban_show` context. The wording avoids the respawn-blocker pattern.

**Respawn guard (`check_respawn_guard`):**
- While the latest run is such a deferral, the card is held (`local_budget_wait`) until `retry_not_before`, and after that until the shared ledger has a free slot, checked by peeking without taking one. Another process may have used the capacity meanwhile.
- The native atomic claim then resumes **the same card**. No worker is spawned and no model call is made while it is held.
- A newer genuine failure or a manual stop (block) supersedes the deferral.
- Provider 429 handling is unchanged: a persistent external 429 remains the bounded `STOP MODEL_QUOTA`.

**Golden side:** the golden's run deadline is not known to the kanban dispatcher. A deadline that expires while a card is held must end through the golden's existing deadline outcome.

## Token accounting (0010, V15-1 change 2)

**Settings.** `RHOAI3_ACCOUNTING_MODE=token` selects the mode; the platform writes these values from the run's profile into the managed `.env`:

| Variable | Meaning |
|---|---|
| `RHOAI3_TOKEN_BUDGET` | `<B>/<window_seconds>`, the run allowance, e.g. `51000000/3600` |
| `RHOAI3_TOKEN_RESERVATION` | `<C>`, the served prompt+output bound, e.g. `262144` |
| `RHOAI3_REQUEST_LEDGER` | the shared ledger |

- Exactly one mode per process. Mixed or incomplete settings, or `C > B`, raise `AccountingConfigError` and nothing is sent.
- Request mode (`RHOAI3_REQUEST_BUDGET`) is unchanged for runs pinned to it.
- In token mode there is **no request-count ceiling**.

**Reservation.**
- Every physical HTTP attempt reserves `C` under the ledger lock. That covers main calls, 429 retries, truncation cap-boost retries, stream reconnects, sync/async auxiliary calls, the gateway and the reviewer.
- A request is admitted only if `settled_charges_in_window + open_reservations + C <= B`.
- The main-loop reservation and the transport hand-off consume the same reservation exactly once, through the request-ownership `PacedAttempt`.

**Settlement.** A wrapper on `chat.completions.create`, installed at the same client construction choke points, settles each reservation **exactly once** at the terminal response:
- **Valid usage:** the charge is the validated prompt+completion. The integers must be non-negative, the total consistent and the charge ≤ `C`.
- **Streams:** they settle at the terminal chunk to the last usage record; cumulative frames are not summed.
- **No valid usage:** a terminal response without valid usage, or an HTTP error response, settles at `C`. Missing usage never counts as zero.
- **Uncertain end:** a cancellation, crash, timeout, or a stream that ended without its terminal chunk writes nothing. The reservation stays open until `reserved_at + hold + window`, then stops counting (see **Retention** below). It never grants speculative credit.
- **Expiry:** settled charges count for one full window after settlement.
- **Duplicates:** repeated settlements are ignored.

**Ledger lines.** `R <ts> <pid> <rid> <C> <label>` and `S <ts> <rid> <charge> <status>`. State is reconstructed by reservation id; no prompts or secrets are stored.

**Refusals and deferrals.**
- A token-mode request that reaches the transport without the settlement wiring is refused before sending (`AccountingNotAttached`).
- A full allowance defers through 0009 with `accounting_mode=token` and `retry_not_before` = when enough settled charge expires.
- Open reservations also have a known expiry (retention), so a wake time is always computable. The `uncertain` flag (bounded 60 s re-check) remains only as a guard.

**Usage measured on the fake-provider paths** (`b3-b4/README.md`):
- Main streaming requests ask for usage (`stream_options.include_usage`), and it settles.
- Auxiliary (compression) calls are non-streaming with usage in the body.
- 429 responses carry no usage (charged `C`).
- Hermes' own `session_model_usage` **omits truncated responses** (the length branch skips the usage bookkeeping). The ledger does not.

**Not in the runtime:**
- Admission (`run-preflight.sh`, `sum(token_allowance) + reserve <= subscription`) and the profile fields are platform and golden changes; see the list in `b3-b4/README.md`.
- Enabling token mode for new runs follows the focused live qualification in the design.

### Retention of open reservations (0010 amendment)

**What it does.** An open (unsettled) reservation counts until `reserved_at + hold + window_seconds`, then stops counting. Settled charges are unchanged: they count for one window after settlement.

**Why.**
- An uncertain request (cancelled, crashed, dropped stream, client timeout) keeps its full reservation, as the architect requires. That does not have to mean forever.
- Any upstream charge for a request lands no later than the request's own end. Once `hold` covers the longest a request can run, a charge for that request has left MaaS's own one-hour window by `reserved_at + hold + window` as well.
- Holding forever meant every dropped stream permanently removed C = 262,144 tokens. At B = 51M, about 194 such events would stop a run for good; v12 had stale-timeout drops.
- Tests (a)–(c) show the difference. (a) A dropped stream still counts at `reserved_at + window`. (b) It stops counting after `reserved_at + 900 + window` on a fake clock. (c) 200 drops spread over time never exhaust B permanently: the 195th waits for a known wake time, then proceeds.

**Setting.** `RHOAI3_TOKEN_RESERVATION_HOLD_SECONDS`.
- Default: the longest client request timeout this process honours, with a floor of 900 s. That is the largest of `providers.*.request_timeout_seconds`, `providers.*.models.*.timeout_seconds`, `auxiliary.*.timeout` and `HERMES_API_TIMEOUT`, and 1800 when the `custom` provider declares none.
- An explicit value below that is refused with `AccountingConfigError`.
- With the producer's managed `.env` (`HERMES_API_TIMEOUT=1800`) the default is **1800**.

**Which timeout really bounds a request (from pinned source).**
- **Non-streaming.** `_resolved_api_call_timeout` (`run_agent.py:1402`) is the per-call `timeout=`. It uses `providers.<id>.models.<m>.timeout_seconds`, then `providers.<id>.request_timeout_seconds`, then `HERMES_API_TIMEOUT` (default 1800). With the producer config the provider value **900** wins; `HERMES_API_TIMEOUT` then applies only to a model path without a provider-configured timeout.
- **Streaming (the main agent).** `_call_chat_completions` (`chat_completion_helpers.py:3841`) builds `httpx.Timeout(connect, read=<stream read timeout>, write=<base timeout>, pool)`. There is **no total timeout**. The read timeout (900) and the stale detector (`stale_timeout_seconds` 900) bound **inactivity** only. A stream that keeps producing chunks is bounded end to end only by its output: at most 32,768 tokens plus prefill.

**Recommendation.** No client timeout bounds a streamed request end to end. The platform should set `RHOAI3_TOKEN_RESERVATION_HOLD_SECONDS` explicitly, to at least `max(1800, stale_timeout + 32768 / slowest generation rate)`. At ~18 tok/s that is ≈ 900 + 1,820 s, so **3,600** is a safe round value. It must never be below the longest client timeout (1800 here), and the runtime enforces that part. Whether MaaS still counts a request the client dropped, and when, is part of the design's live qualification.

## What this does not cover

- **Worker recovery policy** is golden-side (commit "a halted worker gets one automatic recovery ..."): K4 mints loop cards with `max_retries` 2 (`k4_schema.LOOP_MAX_RETRIES`), so the first guard halt respawns the card once and the second blocks it with the `gave_up` guardrail metadata; `brief.py` hands the respawned run its unaccepted candidate (`candidate_on_tree`) and the one next action. The count lives in the kanban database, outside product Git. Not covered anywhere yet: a named `WORKER_RECOVERY_EXHAUSTED` code (the native `gave_up` event carries the halt metadata instead).
- **Multi-call cycles** such as A, B, A, B. Upstream detects these with a later `identical_cycle_halt`, which this series does not include. A worker that alternates two identical calls is still bounded only by the iteration budget.
- **Pollers.** `process` and `*_get_result` / `*_poll` stay exempt from the streak halt, with no per-operation deadline. They are bounded only by the turn's iteration budget, as the test shows. Polling through `terminal` is not exempt.
- **Persisted-path existence.** The stub fix trusts a recorded persisted path and does not check that the file still exists.
- **Live compressor summary.** The compression regression uses the pinned compressor's deterministic prune pass (`ContextCompressor._prune_old_tool_results`). It does not use the LLM summary path.
- **Upstream threshold config.** `idempotent_tools` and `mutating_tools` are still not read from YAML at this pin, as noted in the design.
- **Sampling and auxiliary profile.** These are covered in `b3-b4/README.md`. The auxiliary compression profile still depends on the Stage 050 producer change.
- **Where it was run.** Everything was checked on macOS with Python 3.11 against a local clone, with a scripted fake provider on loopback. Nothing was checked against a live cluster, an image build, or a real model.

## Evidence

`qualification-log.txt` in this directory holds the B11 before and after output. `b3-b4/qualification-log.txt` holds the B3/B4 and R2 evidence and the final-tree run of every qualification test.
