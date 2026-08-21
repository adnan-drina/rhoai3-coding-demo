# Independent research commission — official Hermes + Spec Kit capabilities for a v2 migration harness

**Rev 2** · 2026-08-21 · folds Operator `E-20260821T124605Z` (workspace-kind premise). Supersedes rev 1.
**To:** two external research agents (give **each** this exact prompt; do **not** share answers between them until both have submitted).
**From:** Architect, rhoai3-coding-demo / stage 080
**This is research, not implementation.** Do not write code. Do not propose git branches, dest provision, or patches to our tree.

**Blind for Part A.** Do not open this repository, AD-019, any `SOLUTION-ARCHITECTURE*.md`, dest workspaces, or our skills extractions until Part A is written down. Part B is self-contained; it is the only architecture you are allowed to see, and only after Part A. If this prompt arrived next to a checkout, treat the checkout as sealed until then. (Rev 1 failed this protocol by naming a repo path in Part B and inviting a “v1 facts” table that did not exist.)

**Method (non-negotiable):**

1. Complete **Part A** in writing first. Stop. That section must be able to stand if Part B were deleted.
2. Only then read **Part B** and attack it.
3. Prefer **live official documentation fetched today** over anything we summarise. Our last in-house capture of Hermes docs is **2026-08-12**; the seat pin is Hermes **v0.20.4** (`build 2026.8.18`) and Spec Kit **specify-cli 0.16.1**. If live docs disagree with a claim in this brief, **the live page wins** — say so.
4. Mark every factual claim: **verified (URL + retrieved date)** / **taken from this brief** / **could not determine**.
5. If you cannot fetch a page, say so. Do not invent CLI flags, config keys, or CRDs.
6. Disagreement is the useful output. Agreement with no new evidence is not.

v1 measurements in this brief are **ours**. Treat them as taken-from-brief unless you independently know otherwise. Do not use a repo to check them during Part A.

---

## The problem (shared context for Part A)

We are rebuilding an **autonomous** Spring Boot → Quarkus migration on **Hermes Agent** (Nous Research) + **GitHub Spec Kit** + **Migration Toolkit for Applications (MTA)**. A human is accountable for the repo, but there is **no human approval step inside the phase chain**. A typed refusal is a legitimate terminal. A waiver is not.

Five phases (nomenclature we will keep):

| Phase | Intent |
|---|---|
| **M1 ANALYZE** | MTA/Kantra + entry-point/type inventory. Evidence is input to planning, not a second spec we author by hand. |
| **M2 PLAN** | Spec Kit: `spec.md` → `plan.md` → `tasks.md`. The planner is forbidden from implementing. |
| **Mint** | Turn `tasks.md` into N executable Kanban story cards, parked until a grant. |
| **M3 IMPLEMENT** | One card per unit of work; one worker; pinned workspace. |
| **M4 VERIFY / M5 CLOSE** | Product oracles (compile, parity, rescan). Release verdict. |

Stories **may** contend on a shared destination `pom.xml` **under a shared-directory workspace**. Whether that contention is intrinsic to the migration, or an artifact of our workspace-kind choice, is an open question for you — see **A8**. A worker must not widen its own write set, and must not declare its own success.

**v1 harness (the thing we are not copying):** ~47k lines of Python/shell in the golden scaffold, of which ~10% does migration work and ~90% governs the agent. The mint alone is ~8k lines / 25 scripts. Across ~40 numbered dest runs, **no wave has reached M4**. Four consecutive runs spent hardening the mint found **zero** of eighteen defects that appeared once story cards actually executed. A later run (v41) had M2 rewrite M1’s type-inventory flag `generated: true` on a path in **no** body’s write set; coverage then passed by skipping those rows. We treat that class as: **a mint that seals a falsified premise is worse than one that does not seal.**

v1 created every card with `--workspace dir:/projects/modernized`. Native `worktree` appears in that scaffold only as comments, lints, or negatives. That is a configuration choice. It is not a product limitation unless A8 shows otherwise.

Dest constraint you must still weigh (workshop, not Hermes): the run happens in **OpenShift Dev Spaces** with a PVC and a single clone of the destination repo at `/projects/modernized`. OpenShift is not an official Hermes install surface.

We are opening a **v2 campaign**: new architecture, new scaffold tree, v1 frozen. Default is **use official product features**. Custom code is the exception and must name the official gap.

### Closed options — do not re-propose without engaging the stated reason

Each was evaluated against the product and rejected. If live docs have changed such that the reason is now false, **that is the highest-value finding you can return.**

| Option | Why we rejected it (v1 measurement) | Retire if |
|---|---|---|
| `hermes kanban swarm` for the M3 graph | BV19-4: siblings under a root that is already `done`; no intra-sibling ordering. We needed order because stories shared `pom.xml` **under `dir:`**. | Product grows a serial/file-ownership knob — **or** per-card worktrees make intra-sibling ordering unnecessary. **Not re-tested since v1.** |
| Card **attachments** as the typed-body store | Writable and deletable after `done`; no content digest | Attachments become immutable + digested |
| Native `decompose` as the mint | Reads title + body only; cannot consume a typed partition from `tasks.md` | Decomposer takes a structured partition |
| Exit gates on `pre_verify` | Catalog is continue/nudge — advisory. A gate must be able to **refuse**. | Product grows a veto verify hook |
| Human approval inside M1–M5 | Autonomy constraint | Product owner reverses it |
| `kanban daemon --force` / standalone daemon as the dispatcher | Official: gateway-embedded dispatcher; two dispatchers on one `kanban.db` race | Docs change |
| `fallback_providers` to MiniMax/OpenRouter | Policy: Qwen primary; MiniMax exception-only, never silent failover | Policy change |
| Cursor/Lead as the mint orchestrator | Mint must run as a Hermes worker session | — |

### Hard constraints on any proposal

- Fail-closed. Unresolvable → typed refusal, never a lowered bar.
- One task, one type (examine / plan / write / check — never two).
- Specimen-agnostic (no literals from a particular demo app in control flow).
- Per-card write scoping is non-negotiable containment.
- OpenShift is **not** an official Hermes install surface; dest is Dev Spaces + Managed Scope. Do not invent a Kubernetes Hermes operator.
- Do not grow a second scheduler beside Kanban.
- Official docs are product authority. The April 2026 Kanban **v1 design spec PDF** is rationale only (6 states, 8 patterns). Live product: 8 states, `kanban_*` tools, 9 patterns.
- Shared-directory `pom.xml` contention is **not** a hard constraint. See A8.

---

# Part A — answer from official docs before reading Part B

Fetch the live pages. Record **retrieval date/time** and, where possible, the product version the page implies. Quote or tightly paraphrase; do not rely on memory of Hermes from training data.

## Official starting URLs (not exhaustive — follow the product’s own index)

**Hermes (https://hermes-agent.nousresearch.com/docs/llms.txt is the first-party index):**

- Features overview: `/docs/user-guide/features/overview`
- Kanban (primary — workspace kinds, `--branch`, preserved-on-completion, comments, tenants, swarm, review, block are specified here, not only on sub-pages): `/docs/user-guide/features/kanban`
- Kanban tutorial: `/docs/user-guide/features/kanban-tutorial`
- Worker lanes: `/docs/user-guide/features/kanban-worker-lanes`
- Git worktrees (non-kanban detail; Kanban page owns the `worktree:` kind): `/docs/user-guide/git-worktrees`
- Hooks: `/docs/user-guide/features/hooks`
- Skills: `/docs/user-guide/features/skills`
- Creating skills: `/docs/developer-guide/creating-skills`
- Delegation (`delegate_task`): `/docs/user-guide/features/delegation`
- Profiles: `/docs/user-guide/profiles`
- Configuration / models: `/docs/user-guide/configuration`, `/docs/user-guide/configuring-models`
- Managed Scope: `/docs/user-guide/managed-scope`
- CLI (includes `hermes project bind-board`): `/docs/reference/cli-commands`
- Env: `/docs/reference/environment-variables`
- Optional skill “one-three-one”: `/docs/user-guide/skills/optional/communication/communication-one-three-one-rule`
- Bundled `merge-reconciler` skill: follow the Kanban page’s pointer (catalog / optional-skills / creating-skills as needed)
- Source: https://github.com/NousResearch/hermes-agent (use to resolve doc/CLI drift; cite the revision you looked at)

**Spec Kit:**

- https://github.com/github/spec-kit (README, docs, changelog for **specify-cli 0.16.1** or current if 0.16.1 is gone)
- Whatever that repo names as the Hermes integration (`specify init --integration hermes` is a flag we use — confirm it still exists and what it installs)
- Workflows / overlays / `specify workflow run` / `taskstoissues` / analyze / implement — document what each actually does and what it **cannot** refuse

**Agent Skills standard:** https://agentskills.io/specification and `/skill-creation/best-practices`

**MTA (secondary — only as far as “what M1 may consume”):** Migration Toolkit for Applications **8.2** CLI guide on docs.redhat.com. Do not design the harness around MTA UI.

## Questions

**A1. Kanban as a work queue — current live contract.**
For `hermes kanban create` (and `kanban_create`): body shape, `skills`, `--parent` / parent DAG, `initial_status`, `idempotency_key`, `--max-runtime`, `--max-retries`, `--tenant`, `--workspace`, `--branch`, attachments, `workflow_template_id`. What is the 8-state enum? When does `todo` become `ready`? Is `blocked` sticky? What do `kanban_request_review` and `kanban_request_changes` actually do to state and to the block-recurrence counter? What is `kanban_block --kind` for (`needs_input` vs `dependency` vs other)? What does `swarm` actually create (parent status, sibling order, **workspace kind of the children**)? What does `decompose` read? What is `kanban_comment` / `hotspot:` for?

**A2. The blocking extension point.**
Which hook events can **veto** a tool call? What is `pre_verify` allowed to do? What is required for hooks to register in **non-TTY** / gateway / kanban-worker contexts (`--accept-hooks`, `HERMES_ACCEPT_HOOKS`, `hooks_auto_accept`, `fail_closed`)? Is there any **native** per-task write allowlist, sandbox `permission.edit`, or workspace fence that would make a custom write-set hook unnecessary? If yes, name the config key and its failure mode.

**A3. Spec Kit as the planning compiler.**
What artifacts does 0.16.1 (or current) emit (`spec.md` / `plan.md` / `tasks.md` structure)? Can `tasks.md` express file ownership, parent order, and “do not implement”? What do overlays/workflows do, especially `remove: implement`? What is `speckit.analyze` — advisory Markdown or a gate that can refuse extra endpoints/`@Path`? What is `taskstoissues` — GitHub issues, or a generic graph? Is there a supported path **tasks.md → Hermes Kanban cards** that is not “an LLM reads the markdown and calls create”?

**A4. Skills, profiles, Managed Scope.**
How do `skills.external_dirs` work (precedence, writability, attach-to-card)? Card-level skill pin vs profile-level toolsets? Official guidance on **when to use profiles** vs a single default assignee. Managed Scope: what it can pin, what it cannot (v1 ceiling). `skills.write_approval` / curator — relevant to an unattended dest or not?

**A5. Design from official primitives only.**
Ignore our v1 mint **and do not assume a shared working directory** unless A8 forces you to. Given A1–A4 and A8–A9, specify the **thinnest** official-native design that still meets: (i) plan → N stories, (ii) pre-execution contract the worker did not write, (iii) runtime write containment, (iv) worker cannot mark itself successful by lying, (v) no human in the phase chain. Name each official feature. Where you are forced to invent, say **invent** and why the docs left a hole. We are open to being told the hashed-JSON-body primitive is the wrong shape, and that intra-sibling ordering is the wrong shape.

**A6. Scale.**
Today a wave is ~11 stories. What official mechanism is the first to fail at 50? At 200? Be concrete (dispatcher tick, single-host Kanban, **worktree disk**, hook latency, spec-kit context, skill-list token floor, PVC, …). Do **not** assume shared-file contention unless A8 says that contention still exists for the workspace kind you recommend.

**A7. Blind spots.**
Failure modes a competent reading of the official docs would expect that do **not** appear in the v1 story above.

**A8. Workspace kinds and isolation.** *(the question rev 1 omitted, which scoped every other answer to `dir:`)*
What do `scratch`, `dir:`, `worktree`, `worktree:<path>`, and `--branch` give on the **live Kanban page**? What is the deterministic path convention? What is preserved on completion? What does `hermes project bind-board` establish? What are the bundled `merge-reconciler` skill and the reconciliation-card pattern for? What is the `hotspot:` comment convention?

Given **per-card worktrees**, is intra-sibling ordering still required for stories that would otherwise write one shared `pom.xml`, or does it become a merge problem the product already solves? If it becomes a merge problem: who runs the reconciler (dispatcher, orchestrator card, human), and is that compatible with “no human in the phase chain”?

What breaks in **our** dest: Dev Spaces PVC, a single clone at `/projects/modernized`, checkpoint scoping per worktree path hash, disk, relative `dir:` reject at dispatch?

**A9. Tenant, comments, `delegate_task`, worker lanes.**
When is `--tenant` / `HERMES_TENANT` the isolation primitive vs a board vs a worktree? What are comments for besides humans (durable notes, `hotspot:`, block-reason side-effect)? When does official docs say **Kanban** vs **`delegate_task`** for work that must survive restarts, show a parent DAG, and remain auditable? What is a worker lane, and is an external/non-Hermes lane paved? Which of these four, if any, belongs in a thinnest native migration design?

Commit Part A before continuing.

---

# Part B — only after Part A is written down

Our v2 architecture (AD-019, 2026-08-21, **amended** after `E-20260821T124605Z` on the workspace-kind premise). Attack it. **Do not rubber-stamp.** The useful answer is where this is wrong relative to **today’s** official docs, or where a KEEP is actually ADOPT. Do not open other files.

## Classification law we adopted

Every new file: **ADOPT** (official sufficient) / **REHOST** (our policy, official mechanism) / **KEEP** (measured gap on the pinned CLI, with a line cap and a retire gate). Default ADOPT. “More thorough than native” is not a KEEP. No new `.hermes/home/scripts/`.

## Day-one custom kernel (the entire allowed custom surface)

| ID | Kind | Claimed gap | Our answer | Cap / retire |
|---|---|---|---|---|
| **K1** | KEEP | Card body is free-text; completion metadata is post-work; attachments aren’t a digest store | Typed JSON body (identity, refs+sha256, files_writable, exit_criteria) + file hash stamped on sidecar **and** card; start refuses on mismatch. Triple equality = consistency of three copies, **not** immutability. | One schema + one loader + one validator ≤ 400 lines. Retire when Hermes ships typed task-spec + digest. |
| **K2** | REHOST | No native per-card write allowlist (claimed) | Official `pre_tool_call` + `fail_closed: true`; policy = `files_writable`. Classify generated-ness at **read time from path**, never trust a mutable inventory boolean. | One hook module. Retire when dispatcher enforces write scope. |
| **K3** | ADOPT+REHOST · **CONTESTED** | Need park-until-grant | Native parents: children wait on an `ack_gate` card that does not complete itself. Grant = `kanban_complete` on the gate. We believe `blocked` is **not** sticky. **May be an artifact of `dir:` + serial law.** | Procedure only. Survive or die in B8. |
| **K4** | KEEP · **CONTESTED** | No bulk-mint from `tasks.md`; swarm/decompose/taskstoissues unfit (claimed) | One ≤400-line converter: partition → bodies → `kanban create` with skills, parents, idempotency. Caller = Hermes wave-holder worker. Assemble → freeze digest → verify. Mint-time refuse = planning defect, not a review. **Parent-order half may be an artifact of `dir:`.** | Retire when product ships tasks.md → Kanban graph, **or** when A8 shows swarm+worktrees suffice. |
| **K5** | KEEP | Workshop dest must not link to the authoring repo | Authoring-side hermeticity CI. Not a dest `validate.sh`. | Packaging, not a Hermes gap. |

## Official features we intend to ADOPT (not wrap)

Gateway-embedded dispatcher (no standalone daemon). Terminators: `kanban_complete` / `kanban_request_review` / `kanban_block` — exactly one. **Review lane on day one:** `request_review` → `request_changes` for gate verdicts against **work already done** (we believe this avoids `BLOCK_RECURRENCE_LIMIT` → `triage`). `needs_input` only for true external escalation. Bounds via `--max-runtime` / `--max-retries`. Concurrency via `max_in_progress*` — **rev 1 said overlapping writes sequence via parents; that sentence assumed `dir:`.** Audit via `task_runs` / `kanban log`. Card id = `HERMES_KANBAN_TASK`. Mechanical parse via `execute_code`. Spec Kit owns spec/plan/tasks; `speckit.analyze` stays advisory until a reproduction shows it can refuse extra `@Path`. **Do not adopt profiles** until (a) second model endpoint, (b) true concurrent workers needing separate Hermes homes, or (c) an orchestrator that cannot hold implement tools.

Workspace kind, `bind-board`, `merge-reconciler`, tenants, comments, `delegate_task`, and worker lanes were **absent from rev 1’s ADOPT map**. That omission is the defect this rev exists to have you correct.

## First success we named

One trivial Spring Boot specimen (≤ 2 HTTP endpoints, not our previous demo app) reaches **M4** with zero dest-patches and zero kernel-cap violations. Until then, the kernel table does not grow.

## Questions on our plan

**B1.** For each of K1–K5: ADOPT, REHOST, KEEP, or **DELETE**? Cite the live doc that makes you right. The strongest result is “K_ is KEEP in your doc and ADOPT on today’s CLI.”

**B2.** Is the hashed JSON body the right primitive, or is there a native shape (handoff metadata, goal-mode cards, skill args, overlay, constitution, `kanban_complete(artifacts=…)`, something we have not named) that we are duplicating?

**B3.** Park-at-birth via an incomplete parent: is that the intended use of the DAG, or a misuse that the dispatcher will promote around (`scheduled_at`, `recompute_ready`, `initial_status`, …)? What is the official way to hold a connected graph un-spawned until a grant?

**B4.** N-1 (review lane) vs `kanban_block`: given unattended seats (`review_dispatch: false` if that still exists), does `request_changes` self-clear, or do we trade a block-loop for a review-loop?

**B5.** Spec Kit: what overlay/workflow/constitution native should replace our custom “stop before implement” and unique-owner tasks template? What must remain an override?

**B6.** What should be in the kernel that we omitted (liveness, Managed Scope assert, skill write-approval, workspace relative-path reject, **worktree/`bind-board`**, …)? What should we cut entirely?

**B7.** Single highest-value correction to AD-019, and the one sentence we should delete.

**B8.** We told you stories contend on a shared `pom.xml` and that ordering is load-bearing. That is a property of our **`dir:` choice**, not of the product. Re-derive: which of **K3**, **K4**, and the **serial ordering** survive if every story card gets its own worktree and branch? If they die, what native graph (swarm, P1 fan-out, bind-board, merge-reconciler) replaces the mint converter’s parent-order job? If they survive, name the dest constraint (PVC, single clone, Maven reactor, …) that worktrees do **not** remove.

---

## Output we want

1. **Part A**, visibly complete before Part B.
2. **Part B**, as a critique (verdict per K-row, including B8).
3. A **claims table**: claim · source URL · verified today / from brief / unverified.
4. **Doc drift:** anything live today that contradicts Hermes docs as of 2026-08-12 or Spec Kit 0.16.1 README.
5. **What I could not determine.**

Assume a technically expert reader. Skip product tutorials. The most useful sentence you can write is one that makes a KEEP unnecessary.
