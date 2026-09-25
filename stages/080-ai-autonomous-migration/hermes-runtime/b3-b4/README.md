# B3/B4: wire profile, truncated output and HTTP 429 (Stage 080 Hermes runtime)

This directory qualifies three worker behaviours: the non-thinking sampling profile the worker sends, a response truncated by the output cap, and HTTP 429 rate limiting. The design sections are B3 and B4 in `tmp/v12-run-20260924/architect-durable-fixes-design.md`. The work stacks on the B11 series in `../patches`. Two issues needed a runtime fix, delivered as `../patches/0005-…` and `../patches/0006-…`. The wire profile needed no runtime patch. It does need one configuration fix, described below.

| | |
|---|---|
| Base runtime | `v2026.8.19` / `fcbd1076a93841fa88855acce810e342a5b78101` (tree `cc9f987a…`) |
| Series 0001–0004 (B11) | tree `a09b3b45fe2fb0f98665cc2bb3bbf874ca2b4d48` |
| Series 0001–0006 | tree `87a39dca63bca478e1ab93e9ce24ad757de25f8f` |
| Series 0001–0007 | tree `6d6efd1992525da692f2f0f7f23881cf65f3999a` (0007 with request ownership; the earlier `433f0c6f…` and `82b70bae…` are superseded) |
| **Series 0001–0008 (final)** | **tree `101ca3d1da753267ffcb7f9b280f09258085256a`** (supersedes `374562df…`, committed as 2cfd40d1). This was verified by applying all eight patches with `git apply --index` to a clean `fcbd1076` checkout and running `git write-tree`. 0007 is the R2 request pacer and 0008 is auxiliary per-call precedence; see `../README.md`. |
| Worker config under test | Rendered from the Stage 050 producer by `render_worker_config.py`. It executes only the `cfg = {...}` prefix of the `HERMESEOF` block in `gitops/stages/050-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml`. Snapshot: `tests/rhoai3_b3b4/worker_config.json`. |
| Provider | The scripted fake OpenAI-compatible server in `tests/rhoai3_b3b4/fake_openai_server.py`, on loopback. No real model is called. |

## B4: what reaches the wire (no runtime patch)

This was run through the real CLI path, `hermes chat -q … -Q`, with the producer config: provider `qwen38`, runtime provider `custom`, `api_mode` `chat_completions`. The main-agent request body arrives as follows:

```json
{"chat_template_kwargs": {"enable_thinking": false}, "max_tokens": 8192, "min_p": 0.0,
 "model": "qwen3-8-27b-int4", "presence_penalty": 1.5, "repetition_penalty": 1.0,
 "stream": true, "stream_options": {"include_usage": true},
 "temperature": 0.7, "top_k": 20, "top_p": 0.8, "messages": […], "tools": […]}
```

- **Placement.** Every `extra_body` field arrives at the top level of the JSON body. The OpenAI SDK merges `extra_body` into the body, so no `extra_body` key is sent. `chat_template_kwargs` stays a nested object, which is how vLLM expects it.
- **How it gets there.**
  1. `agent/agent_init.py:474` (`_merge_custom_provider_extra_body`) puts the provider's `extra_body` into `agent.request_overrides["extra_body"]`.
  2. `agent/transports/chat_completions.py:702` (`api_kwargs.update(overrides)`) applies it.
  3. `openai/_base_client.py:506` (openai 2.24.0) merges it: `_merge_mappings(json_data, extra_json)`.
- **Precedence.** `extra_body` wins over a top-level key of the same name. The SDK merge is shallow and its second mapping wins. `test_extra_body_wins_over_top_level_sampling` sends `temperature=0.1, top_p=0.5` at the top level and gets 0.7 / 0.8 on the wire. The main path sends no top-level temperature for this model: `_fixed_temperature_for_model` returns None for Qwen. At the Hermes level, `request_overrides["extra_body"]` *replaces* any `extra_body` that Hermes built itself, such as `reasoning`. That happens through the same `update()` at `:702`. For this provider Hermes builds none (inferred from the captured body).
- **Auxiliary compression calls (resolved by the producer).** Before `ec382b16`/`50463fa2`, the compressor's summary and micro-summary calls went out as `{"model"}` and `{"model", "temperature": 0.1}`: no `chat_template_kwargs`, no sampling row and no `max_tokens`, so thinking stayed on and output was uncapped. The producer now sets `auxiliary.compression.extra_body` to the profile's `request_body` plus `max_tokens: 32768`.
  - Measured on the wire: both calls carry the full row and `max_tokens: 32768`. The micro-summary's own top-level `temperature 0.1` and `max_tokens 1500` are overridden by `extra_body`.
  - `render_worker_config.py` now renders from the committed producer plus `gitops/.../devspaces/model-profiles.json`. It redirects the producer's `/etc/rhoai3/model-profiles/model-profiles.json` path to that file, and refuses to render if the producer stops reading it.
  - Compression is the only live auxiliary slot on the main model (`test_every_auto_auxiliary_slot_carries_the_profile`).
- **Cap boost on truncation.** A truncation retry raises the per-request output cap above the declared 8192. See B4 truncation below. B3's quota model has to allow for this.

## B4: truncated tool call (patch 0005)

**Pinned behaviour**, from source and from a fake-server run with the real worker:

- **Detection and retry.** A stream that ends with `finish_reason="length"` in the middle of a tool call is detected at `agent/conversation_loop.py:3930`. The API call is retried up to 4 times. The broken response is never appended, and `max_tokens` is boosted: 8192 → 16384 → 32768 → 32768 → 32768 (cap `max(32768, requested)`, `:3956`). That makes 5 requests per worker run.
- **Refusal.** After that the worker refuses (`:3970`, "refusing to execute incomplete tool arguments"). A second guard at `:7059` covers truncated arguments hidden behind a rewritten `finish_reason`.
- **Nothing executes.** No partial tool call ran. In the run, no file was written and no tool result appeared in any later request.
- **The problem: how the run ended.** `run_conversation` returns `{"partial": True, "completed": False}` directly, without `finalize_turn`. The `chat -q` worker then exits 0 (`cli.py:21434`, non-quiet path). The dispatcher records a **`protocol_violation`**:
  - It does not count toward `consecutive_failures`.
  - It is bounded only by the violation streak of 3 (`hermes_cli/kanban_db.py:8793`), so one card can make up to 15 truncated requests, most at 32768 max_tokens.
  - Its retry guidance tells the next worker that the previous run may have done the work and to report it with `kanban_complete`.

**Patch 0005** makes this a named failed run:

- **Markers.** Each incomplete-output return in `conversation_loop.py` now carries `incomplete_output: <kind>`. The kinds are `tool_call_truncated`, `tool_call_stream_dropped`, `tool_call_arguments_truncated`, `text_continuation_exhausted`, `truncated_rolled_back`, `first_response_truncated`, `repetition` and `reasoning_exhausted`.
- **Recording.** `AIAgent.run_conversation` passes the result to `turn_finalizer.record_kanban_turn_stop`. That function closes the run through `_record_task_failure`, with the error `STOP MODEL_OUTPUT_INCOMPLETE: finish_reason=length (<kind>), output_cap=<n>, recovery exhausted; no partial tool call was executed and this run did not complete the task`. The failure counts toward `max_retries` / `kanban.failure_limit`, the claim is released, and the native respawn and breaker apply.
- **Shared recorder.** 0005 also moves the B11 guardrail-halt recorder (0004) onto one shared `_record_kanban_worker_stop`. That function is gated on `is_dispatcher_owned_worker_context()`, so a `delegate_task` child or an in-process cron job can no longer close the worker's task. This corrects 0004, which had no such gate.

## B3: HTTP 429 (patch 0006)

**Pinned behaviour**, from source and from fake-server runs with the real worker:

| Question | Answer |
|---|---|
| Retry layers | **One.** The primary client is built with SDK `max_retries=0` (`agent/agent_runtime_helpers.py:2553`). Each attempt was exactly one HTTP request (measured). Auxiliary calls such as compression made a single request on 429 and raised to their caller; that was measured with the real compression runtime. What the compressor then does with the error was not exercised. |
| Attempts | 3 per API call: `agent.api_max_retries`, default 3 (`agent/agent_init.py:2048`). The producer does not set it. |
| Retry-After | Honoured as delta-seconds, capped at 600 s (`conversation_loop.py:6463`). With Retry-After 1 the measured gaps were 1.06 s and 1.06 s. An HTTP-date Retry-After, or `0`, fails the `float()` / truthiness test and falls back to backoff. That is from source; not tested. |
| No Retry-After | `jittered_backoff`: 2 s × 2^(n−1) plus up to 50% jitter, 60 s cap (`agent/retry_utils.py:90`, `:6466`). Measured gaps were 2.3 s and 5.2 s. |
| End state at the pin when the limit persists | The result is `failed=True, failure_reason="rate_limit"` (`:6441`). The worker exits 0 (non-quiet `chat -q`, `cli.py:21397`; only the `-Q` goal-mode path maps it to exit 75 `rate_limited`). The dispatcher then records a **protocol_violation**. After 3 violations the card is blocked, which matches v12. The retry guidance tells the next worker to report `kanban_complete`. |
| Trap to avoid | `check_respawn_guard` (`kanban_db.py:9494`) defers a card on every tick when `last_failure_error` matches `_RESPAWN_BLOCKER_RE` (quota, rate limit, 429, auth…). It never counts a failure while doing so. A failure record whose text says "429" or "quota" would therefore leave the card in `ready` indefinitely. |

**Patch 0006** records a persistent 429 as `STOP MODEL_QUOTA: the model endpoint kept throttling this worker … for all <n> attempts, last Retry-After <v>; … Infrastructure capacity stop, not a product-repair verdict`. It goes through the same shared recorder as 0005, counts toward the failure limit and releases the claim.

- **Wording.** The text is chosen so it does not match `_RESPAWN_BLOCKER_RE`. The HTTP status, attempt count, Retry-After and provider message go into the `gave_up` event payload.
- **Result fields.** The rate-limit result dict now also carries `api_attempts` and the raw `retry_after`.
- **Measured.** The first run records the named stop. The dispatcher respawns once, and the second run blocks the card with `gave_up` (`model_stop: MODEL_QUOTA`, `http_status: 429`) at `failure_limit` 2. No `protocol_violation` is recorded.
- **Not in 0006.** The retry layer itself is unchanged, because the pin already respects Retry-After, uses bounded jittered backoff and has one layer.

## Tests (`tests/rhoai3_b3b4`, copy to `tests/` in the Hermes tree)

| Test | Pin `fcbd1076` | Series 0001–0004 (`a09b3b45`) | 0001–0005 (`4acbcd77`) | 0001–0006 (`87a39dca`) |
|---|---|---|---|---|
| `test_wire_payload_matches_nonthinking_profile` | pass | pass | not run | pass |
| `test_profile_check_detects_dropped_extra_body` (control) | pass | pass | not run | pass |
| `test_extra_body_wins_over_top_level_sampling` | pass | pass | not run | pass |
| `test_auxiliary_compression_request_matches_profile_producer_config` (current producer: summary = row + `max_tokens` 32768; micro-summary keeps 0.1 / 1500 plus the row's other keys) | not re-run | not re-run | not run | fails before 0008 (micro-summary sent 0.7 / 32768); passes on 0001–0008 |
| `test_every_auto_auxiliary_slot_carries_the_profile` | not re-run | not re-run | not run | pass |
| `test_truncated_tool_call_never_executes` | **fail** | **fail** | pass | pass |
| `test_429_retry_after_respected` | pass | pass | not run | pass |
| `test_429_without_retry_after_bounded_backoff` | pass | pass | not run | pass |
| `test_persistent_429_named_terminal` | **fail** | **fail** | **fail** | pass |

- The truncation and quota failures on the older trees are all at the board assertion, `detect_crashed_workers(conn) == []`: the dispatcher found a `protocol_violation`.
- The "never executes" part of the truncation test holds on every tree. Those assertions run first, and the pin already behaves correctly there.

## R2: request pacer tests (patch 0007, `test_r2_request_pacer.py`, `test_r2_pacer_waits_in_transport.py`)

Columns: 0001–0006 (`87a39dca`); the earlier 0007 (`433f0c6f`, before V13-PACER-FINAL-REVIEW); 0001–0008 before and after the ownership correction (`374562df`, `101ca3d1`: identical results).

| Test | `87a39dca` | earlier 0007 `433f0c6f` | `374562df` and `101ca3d1` |
|---|---|---|---|
| `test_budget_counts_main_retries_and_auxiliary` | fail (no ledger: 0 slots for 6 requests) | pass | pass |
| `test_budget_shared_across_two_processes` | fail (8 requests reached the server, budget 5) | pass | pass |
| `test_budget_persists_across_restart` | fail (restarted process sent a 4th request) | pass | pass |
| `test_budget_waits_for_oldest_slot` (fake clock) | fail (no `agent.request_pacer`) | pass | pass |
| `test_budget_exhaustion_is_named_failed_run` | fail (request sent; protocol violation) | pass | pass |
| `test_budget_unset_is_unchanged` | fail (no `agent.request_pacer` module to assert disabled) | pass | pass |
| `test_main_path_waits_for_slot_and_completes` (real clock, 2 per 4 s) | fail (no pacing) | pass | pass |
| `test_budget_from_managed_env_reaches_worker` (production allowance from the profile table, settings only in `$HERMES_MANAGED_DIR/.env`; ledger parent created) | fail (no ledger) | pass | pass |
| **`test_budget_total_wait_bound_under_contention`** (production allowance and max wait from the profile table; the competitor wins every expiring slot) | not run | **fail**: waited 900.5 s > 900 s | pass: RequestBudgetExhausted within 900 s, nothing sent |
| `test_budget_first_slot_beyond_wait_stops_immediately` (guards the kept behaviour) | not run | pass | pass |
| **`test_cancelled_wait_sends_nothing`** (cancel check turns true during the hook wait) | not run | **fail** (`cancel_check` does not exist in that 0007: waits could not be cancelled) | pass: `RequestCancelledWhileWaiting`, 0 requests, no slot, nothing later |
| **`test_stream_reconnect_waits_in_hook_without_stale_kill`** (kanban worker, 2 s stale timeout, the dropped stream's reconnect waits ~5 s in the hook) | not run | **fail**: the card stayed `running` and the `kanban_complete` call never reached the agent. Inferred: the watchdog cancelled the waiting attempt, and the request went out after the wait with its response discarded. | pass: the card completes, 3 requests = 3 slots, no stale message, nothing sent after exit |
| `test_auxiliary_call_waits_in_hook_past_its_timeout` (guard: a 1 s aux timeout does not cover a 3 s pacer wait) | not run | pass | pass |

- `test_budget_unset_is_unchanged` fails on 87a39dca only because the module is absent. Its behavioural part is identical on both trees by design: the task completes, 2 requests are sent and no ledger is created.
### Request ownership (review follow-up at 86d153d5; `test_r2_pacer_request_ownership.py`)

| Test | 0001–0008 before (`374562df`) | final (`101ca3d1`) |
|---|---|---|
| (a) `test_auxiliary_cannot_consume_main_reservation_and_deadline_holds`: the reviewer's case, production allowance 190/3600 and max wait 900 from the profile table. `reserve()` waits 600 s, then an auxiliary thread asks for a slot. | **fail**: the auxiliary call consumed the main reservation (labels `reserve`, `main`); the main request waited **1,200 s** (measured with the same seed) | pass: the auxiliary call waits for its own slot (labels `reserve`, `auxiliary`); the main request is admitted on its reservation after **600 s** in total |
| (b) `test_queued_auxiliary_does_not_pause_stale_watchdog_of_main_stream`: an already-sent main stream stalls for 10 s; 2 s stale timeout; an auxiliary request of the same process queues for a slot | **fail**: the stream ran 10.0 s (`EmptyStreamError` at the stall's end); the auxiliary wait hid the stall | pass: the stall is detected as stale within ~2–3 s; the queued auxiliary request is cancelled and never sent |
| (c1) `test_cancelled_attempt_cannot_use_its_reservation`: the reviewer's `_hook_acquire('already-cancelled', lambda: True)` with a prepaid slot present, plus a reserved attempt cancelled from another thread | **fail**: the already-cancelled admission passed on the prepaid slot | pass: `RequestCancelledWhileWaiting` on both; nothing sent |
| (c2) `test_cancelled_attempt_cannot_pass_after_waiting_sync_and_async`: an attempt's second request waits for a slot and is cancelled from another thread, on the sync hook and on the async hook (AsyncOpenAI) | **fail** (`reserve()` had no attempt or cancellation) | pass: only the first request is sent; the attempt header never reaches the provider |
| `test_gateway_process_calls_are_paced_from_managed_env`: `gateway.run` is imported in a separate process with the settings only in the managed `.env`; then `call_llm(task="triage_specifier")` | pass | pass: the call took a ledger slot. This is a local proxy for the gateway-embedded dispatcher's model calls; the live dispatcher was not run |

- The existing pacing, restart, contention, reconnect, cancellation and short-summary tests pass on the final tree. `test_cancelled_wait_sends_nothing` no longer asserts the removed process-wide `waiting()`.
- `tmp/v12-run-20260924/v13-pacer-contention-review.py` runs unchanged against the new 0007 and still reports `bounded-stop` at 900.0 s, with 0 requests.

- **Production values are not hard-coded.** Tests that model the production allowance read it from `model_profiles.json`, the snapshot `render_worker_config.py` writes from `gitops/.../devspaces/model-profiles.json` (190/3600, max wait 900 at the time of writing).
- **The reviewer's reproduction needed no adaptation.** `tmp/v12-run-20260924/v13-pacer-contention-review.py` still extracts `agent/request_pacer.py` from the new 0007 without changes: it keeps its own 200/3600 and calls `_try_take(cfg, label=, take=)` and `acquire()`. It now reports `bounded-stop` at 900.0 s simulated, with 50 competing slots and 0 requests.

## Run

```bash
cd <hermes clone at the tree under test>   # the worker subprocess imports the editable install
cp -R <repo>/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/tests/rhoai3_b3b4 tests/
RHOAI3_B4_CAPTURE=/tmp/b4-capture.jsonl python -m pytest -p no:cacheprovider -v tests/rhoai3_b3b4
# refresh the config snapshot after a producer change:
python <repo>/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/render_worker_config.py <repo> \
  <repo>/stages/080-ai-autonomous-migration/hermes-runtime/b3-b4/tests/rhoai3_b3b4/worker_config.json
```

The 429 tests use small real delays; the whole B3/B4/R2 suite takes about 90 s. Image build: the single authoritative hunk is `../Dockerfile.hunk.txt` (8 patches, tree `101ca3d1…`), checked with `patch --dry-run` only.

## Not covered

- **Persistence and scheduling.** Durable retry-time persistence across process exit, deadline checks, quota admission maths and a per-run profile digest check at spawn are not implemented. These are B3/B4 design items outside the Hermes runtime.
- **Other B3/B4 regression cases.** `test_quota_recomputed_*`, `test_shared_quota_consumers_accounted`, `test_429_restart_preserves_retry_time`, `test_quota_wait_cannot_extend_deadline`, `test_new_model_without_profile_refused`, `test_stale_resolved_profile_blocks_spawn` and `test_profile_refresh_preserves_card_and_budget` are not written.
- **Quota counting.** A persistent quota stop spends the worker failure allowance (2 runs, then blocked). The design's "infrastructure waiting, never a product attempt" would need B8 scheduling instead. The native `rate_limited` requeue is neutral but unbounded, and has the respawn-guard trap above.
- **Truncation cap boost.** It is left as upstream has it (up to 32768 tokens). Recovery stays inside the existing iteration budget, but not inside the declared 8192 output cap.
- **Delegated children.** The recorder's ownership gate is from source and is not exercised by a test.
- **Where it was run.** Everything was checked on macOS with Python 3.11 against a fake provider. Nothing was checked against a live cluster, an image build or a real model.
