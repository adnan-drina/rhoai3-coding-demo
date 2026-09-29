# Bounded parallel M3: one independent repair pair (pilot)

Scope decision, 2026-09-29: exactly **two independent M3 repair outcomes** may execute concurrently
in the next validation run, using native Hermes Kanban worktrees. Everything else stays serial.
This supplements the post-v26 corrections; it does not replace or weaken any acceptance gate.

## What the pinned runtime provides (verified against Hermes tree `37b147ba`)

- `hermes kanban create --workspace worktree:<abs path> --branch <name>`. At dispatch,
  `resolve_workspace` runs `git worktree add -b <branch> <path> HEAD` from the repository that
  contains the path. The task therefore starts from the canonical HEAD at dispatch time. An
  occupied path of another branch is never reused. Completion cleanup keeps a dirty or unpushed
  worktree (`_cleanup_worktree_workspace`).
- **One dispatcher** (gateway-embedded).
  - `kanban.max_in_progress` is a **host-wide** cap that counts running implementer **and
    reviewer** runs.
  - The review lane reserves one slot when review work exists.
  - `kanban.max_in_progress_per_profile` is a single number for every profile. It cannot single
    out a pair.
- Dependencies and same-card review are native. A child becomes ready only when every parent is
  done.

Consequence: raising the cap to 2 alone would let **any** two ready tasks run together, including
an implementer and an unrelated reviewer. The pilot is therefore expressed in the board itself.

## Design

1. **Policy, pinned at creation.**
   - `run-defaults.json` `configuration.parallel_m3` is `m3-pair-pilot/v1` in this golden (it was
     `deferred` before).
   - `planner.execution_policy` reads it from the destination's **initial commit**, not the
     working tree, and applies it only on `outcome-board/v2`.
   - A run created from an earlier golden, or with any other value, is serial.
   - Stage 050 sets `kanban.max_in_progress` from that policy: 2 for the pilot, 1 otherwise. Its
     validation checks that the value matches the policy.
2. **Deterministic pair selection (M2, `planner.pair_selection`).** Over the plan's repair
   outcomes in topological order, the first pair (in stable order) that satisfies all of these:
   - Both are compile (`source`) outcomes with the **same prerequisite set**, which is satisfied
     before either starts, and neither is an ancestor of the other.
   - Their writable scopes are known and disjoint. Neither contains shared build, generator or
     configuration files (`pom.xml`, resources, generator input, `.mvn`).
   - Neither declares a type that the other's files reference, according to the frozen
     structural model. A partial or missing model is unknown, and unknown means serial.
   - Their family budget keys are distinct.
   - Their acceptance needs no whole-application gate (package, startup, parity, behaviour), so it
     is achievable on an isolated candidate.

   The selection document records every rejected candidate with its reason, and the chosen
   pair's evidence. **No qualifying pair is reported as such**; the run is then plain serial.
   Coherent objectives are never split, and ownership never changes.
3. **Serial chain with one fork (publication).**
   - Every repair outcome gets a *schedule* edge to its predecessor in topological order. The
     pair shares one predecessor, and the next outcome depends on both. M4 and M5 already depend
     on every repair.
   - Genuine dependencies are kept unchanged. Schedule edges are recorded separately
     (`schedule_parents`) and read back.
   - Revisions published later (owner repair, M4 repairs) are chained among themselves.
   - While the pair runs, no other task can be ready.
   - Trade-off, stated: in a chain, a card that blocks holds back the cards after it. In the
     cap-1 serial mode other cards continue, although M4 still waits for all.
4. **Isolation.**
   - Each pair card is published with `worktree:<dest>/.worktrees/<slug>` and branch
     `wt/<slug>`. `.worktrees/` is gitignored and is never a product path.
   - A worktree holds only **tracked** files. The run state (`verification/`, the untracked
     `evidence/`, the frozen source in `.derived/`) is gitignored. The worker's first
     `native_gate.py issue` therefore **seeds** the worktree from the canonical state, under the
     integration lock. The seed happens only when the worktree's HEAD is the canonical HEAD and the
     canonical product tree is clean, and it records a seed manifest.
   - From then on, the worktree has its own candidate, index, build outputs, issuance,
     verification records, pending and rejected rows, and rollback.
   - Verification in a pilot worktree runs **without the runtime gates**: no database, no ports.
     Those gates run only on the canonical tree during integration.
   - The board (`HERMES_HOME`), the run deadline, the request allowance and the family budgets
     stay shared. Nothing is copied that could create allowances.
   - The K2 hook confines a pilot worker to its worktree. A write to the canonical tree or to a
     sibling's worktree is refused, and so is a loop tool rooted at the canonical tree.
5. **Serial integration (`native_gate.py integrate`).** Run by the pair's implementer after its
   worktree `advance.py` has accepted the candidate. It is the only path that writes a pilot
   candidate into the canonical tree, and it holds one writer lock.
   1. Verify the task, the run, the worktree binding, the accepted candidate and its scope (every
      changed path is inside the issued write set).
   2. Issue the card on the canonical tree (its baseline is the current canonical HEAD, which after
      the sibling integrates includes the sibling's change).
   3. Apply the candidate's commits with `git cherry-pick --no-commit`. On conflict, restore the
      canonical tree and record `integration-conflict`. No attempt is spent.
   4. Run `run-verify.sh --mode acceptance` and `advance.py` on the **combined canonical tree**.
      These are the ordinary acceptance transaction, runtime gates included. A REVERTED here is a
      genuine rejection under the existing budget rules, and the canonical state is restored by
      `advance.py`.
   5. Record `integrated` (worktree commit, integrated commit, canonical tree, verification
      identity). Native completion and review require it.
   - The operation is idempotent: a replay after an interruption detects an accepted step for this
     card, or restores a half-applied tree under the lock. It never applies twice.
   - After a rejected integration the candidate stays on its branch. `native_gate.py rebase`
     rebases the worktree onto the current canonical HEAD for same-card rework.
6. **Review and completion.**
   - The reviewer audits the card's own worktree records.
   - For a pilot card, the terminator also requires the `integrated` record of its latest
     candidate.
   - Reviewers never write product files.
7. **Report.** For the pair: the overlap of the two implementer runs, both integrated commits, the
   combined verification, elapsed time, requests and tokens, retries and interventions. Also a
   comparison with a serial replay of the same baseline and candidates.

## Not in scope

- A second pair, parallel M4 or M5, or any change to other runs.
- A scheduler, sidecar, poller or second task database.
- Any change to retry allowances or quotas.
- The deferred transformation executor.
