# Stage 080 Hermes runtime

This directory contains the source patches used by the Stage 080 workspace
image and the helper that stages its outcome-authority code. The runtime
patches are build inputs; keep their contents and application order intact.

| Input | Identity |
|-------|----------|
| Hermes base | `NousResearch/hermes-agent`, tag `v2026.8.19`, version `0.20.5` |
| Base commit | `fcbd1076a93841fa88855acce810e342a5b78101` |
| Patch series | [patches/](patches/), 0001–0020 in filename order (20 patches) |
| Expected patched Git tree | `8328461c4d05e0760e694ea5b9970b019366421a` (0001–0020; image not yet built). Current published image: tree `eaa713b9` (0001–0017, see [RELEASE.md](RELEASE.md)); earlier images: `37b147ba` (0001–0016), `498e2faf` (0001–0014) |
| Release manifest | [RELEASE.md](RELEASE.md): published image, qualification, and the image each run uses |

## Patch responsibilities

| Patches | Behavior |
|---------|----------|
| 0001–0004 | Stop identical successful tool-call loops, preserve retrievable output, and record a halted worker as a failed Kanban run |
| 0005 | Record exhausted incomplete-output recovery as a named worker failure |
| 0006 | An exhausted provider rate limit (HTTP 429) or billing wall exits 75 and is reaped as the native neutral `rate_limited` requeue with the rate-limit cooldown; no failure is counted (auth/config errors still fail) |
| 0007 | Pace requests from all processes of a run through a shared ledger, with request-owned wait and cancellation state |
| 0008 | Preserve explicit auxiliary-call sampling and output limits |
| 0009 | Record local allowance exhaustion as a neutral, resumable deferral |
| 0010 | Reserve and settle tokens per physical request; retain uncertain reservations for a bounded period |
| 0011 | Honor a worker stop request (dispatcher-owned worker only; never read or acted on by child or cron executions, and scrubbed from child environments) and halt repeated read-only grep context searches |
| 0012 | Halt redundant read cycles and repeated identical refusals before tool execution |
| 0013 | Review handoff (kanban_request_review / kanban_request_changes) is a terminal worker exit; the stop nudge applies only to the dispatcher-owned worker (backport of upstream 2bd0f1c5, 474db536, 42500bf0, 41fe679d) |
| 0014 | Halt near-duplicate tool-call loops (`near_duplicate_loop_halt`): calls with the same operands after number normalisation, a growing literal, or an exact alternation, with no progress, edit or board transition in between; a new query or file is progress. Local extension, active only under `tool_loop_guardrails.hard_stop_enabled` |
| 0015 | Any new line is progress in the near-duplicate guard: a call that shows a line not shown before is not counted toward `near_duplicate_loop_halt`. Identifiers, digests and timestamps the tool printed are content; only the runtime's own appended notices (loop warnings, hard stops, identical-call notes) are excluded, and the terminal envelope is read even when they follow it. Exact repetitions and unchanged-output loops still halt |
| 0016 | The `--skills` preload records what it actually loaded: a Kanban worker's native finalizer appends one run-bound `preload` row to the task's execution ledger (status loaded / partial / failed / timeout / error / no-result; per loaded skill the resolved `SKILL.md`, its sha256 and the prompt-text digest). A requested skill that did not load is never listed as loaded. Local extension |
| 0017 | Loop escalation to a thinking profile: the identical-call note for the third consecutive identical call switches that worker's next model requests to `providers.<provider>.models.<model>.loop_escalation.request_body` (fallback `providers.<provider>.loop_escalation`; `{enabled, max_turns, request_body}`), which replaces the normal `extra_body` and whose `max_tokens` is the output cap. Ends at the first edit (`write_file`, `patch`, terminal `sed -i` / `> src/` / `tee src/`), verification command (`run-verify.sh`, `advance.py`) or `max_turns` escalated requests (default 8). Guardrails unchanged; reasoning is echoed through `model.reasoning_echo`; agent.log lines prefixed `[loop-escalation]`. Absent or disabled config changes nothing. Local extension |
| 0018 | Loop escalation also starts on three optional triggers read from the same `loop_escalation` block: `same_result_count` consecutive calls to one tool that are near-duplicates of each other (0014's measure) and return a byte-identical result (0015's reading); `same_call_count` consecutive calls with identical arguments, whatever the results; and `repeat_read_count` calls within the last `repeat_read_window` that each exactly repeat an earlier call (same tool and arguments, byte-identical result), with no edit in between. Pollers exempt from the identical-call note are not counted; an edit, verification, typed-repair, background or evidence-changing call restarts every count and the repeat history. A start on any of them appends a factual note to the triggering result, and the start log line carries `trigger=identical\|same-result\|same-call\|repeat-read`. `max_starts_per_signature` bounds the escalations one stall signature starts in a run (tool plus argument hash; tool plus result hash for same-result; tool plus the hash of the repeated (arguments, result) set for repeat-read, where a later set sharing a pair counts as the same signature); the next start is a guardrail halt, `loop_escalation_restart_halt`. Absent keys keep 0017's behaviour. Running the card's typed repair executor (a terminal command naming `typed-repair.py`) is an added end condition (`end reason=typed-repair`). The edit and verification patterns, turn cap, request body and the 0001/0012/0014/0015 halts are unchanged. Local extension |
| 0019 | A foreground `terminal` call cut at the executor's per-call deadline (the foreground limit, 420 s by default, applied whatever `timeout` the call requested) reports the requested and applied limits, that the process was killed, and the background route (`terminal(background=true)`, then `process(action="wait")`). The limit's value is unchanged. Local extension |
| 0020 | `read_file` reports a line cut at the per-line cap (`tool_output.max_line_length`, 2000 characters by default, applied in `ShellFileOperations._add_line_numbers`): `truncated` is true, `clipped_lines` lists each cut line with its full length in bytes, and the hint states that offset and limit page by line, so the cut part cannot be reached by paging. The content (with its `... [truncated]` marker) is unchanged, and a read with no cut line runs the same commands and returns the same result as before. Local extension |

Patch 0001 backports the controller/runtime changes from upstream commit
`76648a7faf7822cdd6c0e147c35857e15780c1af`; patch 0013 backports the upstream
Kanban stop-guard fixes `2bd0f1c5`, `474db536`, `42500bf0`, and `41fe679d`;
the remaining patches are local. Patch 0006 aligns with the documented
neutral `rate_limited` requeue (upstream `be9d4369` closes the same gap; cited,
not copied). This runtime is a qualified local fork of Hermes, not stock Hermes.
The upstream test hunk inside 0001 is part of the pinned tree identity.
`hermes --version` still reports `0.20.5`; it does not identify this patch set.

## Build contract

The canonical build recipe is versioned in [build-recipe/](build-recipe/): the
Dockerfile, `.dockerignore`, build scripts, devfile fragment and
[build-080-runtime-image.sh](build-recipe/build-080-runtime-image.sh). The
build context is the local, Git-ignored `workspace-images/` directory, which
also holds generated caches and downloaded inputs under `out/` (the MTA CLI
archive comes from the Red Hat download page and is checksum-gated).

The build script:

- syncs the recipe into the context and refuses a context that then differs;
- applies all patches to a clean checkout of the base commit with
  `git apply --index` and requires `git write-tree` to equal the expected tree;
- requires the recipe to pin that tree and patch count;
- builds the image, which records patch checksums in
  `/opt/rhoai3/hermes-runtime-patches.sha256` and stamps `hermes.source_sha`
  and `hermes.patched_tree` in `/opt/rhoai3/080.pins`;
- reads back the tree, the patch count and the authority stamp from the built
  image;
- records the build context identity.

See the [operations guide](../../../docs/OPERATIONS.md) for the workshop
operating model.

## Authority packaging

[outcome-authority/stage-outcome-authority.py](outcome-authority/stage-outcome-authority.py)
extracts `kernel`, `lib`, `planning`, and `skills` from a full Git commit,
excluding working-tree edits. It computes the staged authority code identity
and writes `outcome-authority.code_sha256` beside the output directory.

```bash
python3 stages/080-ai-autonomous-migration/hermes-runtime/outcome-authority/stage-outcome-authority.py \
  --repo /path/to/repository --commit <full-commit-id> \
  --out /path/to/build-context/out/outcome-authority
```

The helper replaces its output directory. Pass the printed identity as
`OUTCOME_AUTHORITY_CODE_SHA256` to the image build. The baked authority tree
must be root-owned, inaccessible for writes by workspace UIDs or group 0,
and verified against that identity. Directories and executable files use
0755; other files use 0644. Record the verified identity as
`outcome_authority.code_sha256` in `/opt/rhoai3/080.pins`.

Authority packaging supports the v1 service implementation. The current v2
protocol uses native cooperative control without that service; see
[OUTCOME-BOARD-CONTRACT.md](../OUTCOME-BOARD-CONTRACT.md).

## Configuration and evidence

The Stage 050 producer and its `model-profiles.json` supply the runtime's
model configuration and request/token budgets. The golden scaffold supplies
migration policy and worker recovery. Those are separate from this patch set.

Historical qualification suites, frozen profile fixtures, probes, and saved
logs have been retired from this directory. They remain in Git history. Their
recorded results do not establish a current image build, live Dev Spaces
qualification, or permission to publish or activate a migration run.
