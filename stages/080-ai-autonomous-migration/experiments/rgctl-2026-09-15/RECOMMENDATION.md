# Recommendation

> ## Architect's rulings on this experiment (received 2026-09-15, recorded as given)
>
> The result is ratified: **sufficient evidence to adopt the execution model's useful
> parts.** The rulings, as received:
>
> 1. **Coordinated multi-file units with checkpoint acceptance are adopted**, together
>    with scope revisions on new evidence. A unit may span every file a single
>    mechanical family touches and is evaluated once at its planned checkpoint;
>    intermediate regressions inside a unit are permitted.
> 2. **Runtime feedback becomes part of execution, not a terminal gate.** Package and
>    start the application as soon as the build permits; behavioural failures drive
>    later units. Keep the mechanism lightweight.
> 3. **The tested rgctl version is excluded from planning and acceptance authority.**
>    It may be used as an optional readout only, scoped to the version and
>    configuration tested here. It decides nothing and gates nothing.
> 4. **The ADR-009 baseline-state correction is ratified.** PostgreSQL stays. The
>    initialized logical data and the generated-identity behaviour must reproduce the
>    declared source baseline; versioned seed and reset assets are to be applied before
>    the next official parity run. Initialization is to be derived from the application
>    contract — PetClinic's particular sequence strategy must not be generalized.
>
> Four claims in an earlier revision of these deliverables were corrected before this
> was published; they are marked as corrections in `FINDINGS.md` (B-1) and
> `COMPARISON.md` (v9 packaging and startup; the specialty response; the autonomy
> wording).

**Retain selected parts. Reject rgctl as a planning or gating mechanism.**

## The decisive question

> Did this approach produce a working, behaviorally verified migration with less
> intervention and less orchestration work?

**A working, behaviourally verified migration: yes, and the gain is specifically
behavioural.** v9 also reached a clean package (gate accepted at `6a4ba85`), a booting
artifact (gate accepted at `be484e84`) and zero compile diagnostics; build and startup
are not where the two runs differ. What differs is behavioural coverage: **17 of 18
parity scenarios passing** where v9 passed none, **20 of 34 entry points** proven equal
to recorded source responses where v9 proved none, **16 of 17** generated ADR-015
product tests passing where v9 had no product tests at all, and both security modes
working where v9 answered 403 to every read.

**With less intervention and less orchestration work: yes — but not because of the
graph.** Zero human interventions during this execution, using the accumulated
decisions (ADR-001..016) and the v9 evidence as inputs, against v9's three Operator
steps and three architect rulings; 13 commits against 21 cards; no board, no gates, no
card minting. The decisions this execution consumed were produced by earlier human
work, so this describes execution effort, not a rate, and no causal speedup is claimed.
The credit for the behavioural gain belongs to three things, and rgctl is not one of
them.

## What actually produced the result

1. **Coordinated repair scope.** The single largest move was WU-1: 108 diagnostics
   removed in one 13-file edit. A `throws` clause on an interface and on every
   override cannot be repaired one file at a time, and the official loop's per-file
   scope makes exactly this edit unrepresentable. (Its *measure* was never the problem:
   v9 recorded the same uncapped 233 baseline and drove it to 0 — see the corrected
   B-1 in `FINDINGS.md`. The constraint is the unit size, not the counter.)

2. **Reaching a running artifact early.** Eleven of the eighteen defects were
   invisible to the compiler, the graph and the static findings. Jackson enforcing
   creator `required`. Absent containers arriving null. Creator-first property order.
   Hibernate 6 refusing the source's column-name HQL. Cascade ordering. A
   `@ControllerAdvice` that never sees a transaction-time failure. A build-time
   security property. None of these can be planned for; all of them fall out of one
   replay of a recorded source request against the packaged artifact.

3. **Reading the contract instead of the tool.** The ADR-012 obligation, the seed
   dataset mismatch and the identity-sequence mismatch all came from reading the
   corpus contract and the declarations. The graph had nothing to say about any of
   them.

## What to adopt

- **Coordinated work units with a checkpoint, not per-file cards** — ruling 1. Allow a
  unit to span every file a single mechanical family touches, evaluate it once at its
  planned checkpoint, and allow the scope to be revised when new evidence appears.
  WU-1's 108 diagnostics in one 13-file edit is the shape this enables.
- **Package and boot as early as the build permits** — ruling 2. Every unit after WU-5
  here was discovered by running, not by planning. Behavioural failures should drive
  later units, with a lightweight mechanism rather than a new subsystem.
- **The parity harness as a measure the loop optimises, not only a terminal gate.**
  `run-parity.py` against the packaged artifact is what distinguished a working
  migration from a compiling one in this run.

**Withdrawn from an earlier revision of this document:** a recommendation to replace
the official loop's diagnostic measure on the grounds that it was capped at 100. That
was wrong. The official loop already measures with the uncapped JDK diagnostics
checker — v9's own `steps.json` records a bootstrap baseline of **233**, the same
figure my census produced, descending to 0. What remains true is only that
`mvn compile` itself caps at 100, so no ad-hoc script should read Maven's error lines
as a count. See the corrected B-1 in `FINDINGS.md`.

## What to retain from rgctl, narrowly

Ruling 3 excludes **the tested version and configuration** — rgctl 0.4.12, release
binary, as invoked in `REPRODUCE.md` — from planning and acceptance authority. What
follows is an optional readout only, scoped to that version; nothing here decides or
gates anything.

- **`discover` + `export` as a cheap architectural readout.** 573 ms for a full index,
  and the domain-crossing table in `policy/baseline.json` is a genuinely useful
  description of a migrated tree — it is how I learned that no controller reaches a
  repository directly.
- **PageRank as a tie-breaker for ordering**, and only that. It independently ranked
  `DataAccessException` first, which was correct. It cost nothing and it agreed with
  the compiler.

## What to reject, and why

- **rgctl's migration plan.** Its communities are the package tree, its order ignores
  its own centrality output, and it is computed against a source tree whose retired
  packages the accepted decisions already deleted — a quarter of its steps are empty.
- **rgctl `check` as a blocking gate.** It failed the mutation test three ways. It
  passes against a stale graph without saying the graph is stale. Its node UUIDs are
  **all** regenerated by every `discover` — 0 of 1047 survived one re-index — and an
  invalidated policy passes with `violations: []`, indistinguishable from a clean
  tree. And on this codebase the forbidden relationship is not an edge at all, so the
  rule could not have fired even with a fresh policy. This is the false-green shape
  this programme has been burned by repeatedly; it should not enter the loop.
- **rgctl's Kantra as an MTA substitute.** The 0.4.12 release binary carries a
  one-rule fixture catalog, not the documented ~2.6k-rule Konveyor set.
- **Graph edges as evidence of absence.** The graph has no `rest -> service` call
  edges despite dozens of call sites, no `SpringDataXRepository extends XRepository`
  edges at all, and inconsistent `IMPLEMENTS`/`EXTENDS` direction. An absent edge here
  means "the resolver did not resolve it", never "the dependency does not exist".

## Caveats on the comparison

This is not a controlled experiment. I had v9's evidence — including its M4 verdict
and its two named parity failures — from the first minute, and I reused v9's source
captures rather than re-recording them. Different hardware, different database
topology, different agent configuration. **No causal speedup is claimed.** The
outcome numbers are comparable because the same tooling measured them against the same
corpus; the elapsed times are not.

## What is still open

1. `sc:delete-referenced-specialties-1` — **an open error-response compatibility
   issue.** Status (`400`), content type (`text/plain;charset=UTF-8`) and resulting
   state all match the source; the body does not, because it carries the source's
   serialized exception class name and HSQLDB constraint name. Emitting those strings
   needs no retired Spring class on the classpath and no foreign key from another
   engine, so this is **not** impossible and must not be waived: it is to be
   investigated as a bounded response translation from the destination's persistence
   failure to the recorded `className`/`exMessage` shape, derived from the source
   captures, before any contract change is proposed.
2. Thirteen entry points have no corpus scenario and are **untested**, not passing.
   Closing that needs scenarios derived and captured, not migration work.
3. Enabled-mode security is behaviourally verified but **not** parity-verified —
   ADR-014 requires separately bound enabled-mode source captures and none exist.
4. **D-5 is ratified** (ruling 4) and now needs carrying into the official assets.
   PostgreSQL stays. The initialized logical data and the generated-identity behaviour
   must reproduce the declared source baseline, and the corrected seed and reset assets
   must be versioned and applied **before the next official parity run**. Initialization
   is to be derived from the application contract; the particular sequence strategy used
   here for PetClinic must not be generalized into the harness.
5. The failsafe/integration-test wiring the v9 `assert-surefire-results` floor checks
   was not exercised; only surefire was.
