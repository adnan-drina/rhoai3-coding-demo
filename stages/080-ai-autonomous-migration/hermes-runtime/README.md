# Stage 080 Hermes runtime

This directory contains the source patches used by the Stage 080 workspace
image and the helper that stages its outcome-authority code. The runtime
patches are build inputs; keep their contents and application order intact.

| Input | Identity |
|-------|----------|
| Hermes base | `NousResearch/hermes-agent`, tag `v2026.8.19`, version `0.20.5` |
| Base commit | `fcbd1076a93841fa88855acce810e342a5b78101` |
| Patch series | [patches/](patches/), 0001–0015 in filename order |
| Expected patched Git tree | `542d0cd3ae5f22b7849ec9ffbd06914bb5324e70` (0001–0014: `498e2faf`, the published image) |
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
| 0015 | Low novelty is not zero novelty: a call showing at least three lines not shown before (incidental timestamps, durations and hex digests masked) makes progress whatever their share; a halt whose counted calls mostly showed a few new lines is `low_novelty_loop_halt`, never reported as no new output. Exact repetitions and unchanged-output loops still halt as `near_duplicate_loop_halt`. Not in a published image yet |

Patch 0001 backports the controller/runtime changes from upstream commit
`76648a7faf7822cdd6c0e147c35857e15780c1af`; patch 0013 backports the upstream
Kanban stop-guard fixes `2bd0f1c5`, `474db536`, `42500bf0`, and `41fe679d`;
the remaining patches are local. Patch 0006 aligns with the documented
neutral `rate_limited` requeue (upstream `be9d4369` closes the same gap; cited,
not copied). This runtime is a qualified local fork of Hermes, not stock Hermes.
The upstream test hunk inside 0001 is part of the pinned tree identity.
`hermes --version` still reports `0.20.5`; it does not identify this patch set.

## Build contract

Image assembly lives in the local, Git-ignored `workspace-images/` directory.
From a clean checkout of the base commit, apply all fifteen patches in order
with `git apply --index`. Require `git write-tree` to equal the expected tree
above before building. The image build must check the patch count and tree,
record patch checksums in `/opt/rhoai3/hermes-runtime-patches.sha256`, and stamp
`hermes.source_sha` and `hermes.patched_tree` in `/opt/rhoai3/080.pins`.

The local `workspace-images/Dockerfile` was checked during cleanup: it already
contains the patch application step (patch count and expected tree set by
`tmp/080-operator/build-080-runtime-image.sh`, which also verifies the series
from a fresh base checkout) and the authority packaging step. The
old incremental Dockerfile hunks were removed. That local file is not supplied
by a fresh repository clone; a separate image-build environment must implement
this contract. See the [operations guide](../../../docs/OPERATIONS.md) for the
workshop operating model.

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
