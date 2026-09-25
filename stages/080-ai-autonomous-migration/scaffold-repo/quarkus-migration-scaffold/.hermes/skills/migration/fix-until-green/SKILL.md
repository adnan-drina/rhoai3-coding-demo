---
name: fix-until-green
description: >
  Use on every M3 loop card (title "M3 c:<cluster>"). The common
  procedure of the fix-until-green loop: read the brief (the cluster's
  items from the sealed work list), edit only the cluster's write set,
  then let the tools decide — run-verify.sh recomputes compiler
  diagnostics, tests and the MTA rescan into the work list, and
  advance.py is a transaction: it promotes the candidate only when the
  card is the issued one, the tree is exactly the one verify.py measured,
  every changed path is inside the write set, and the measure strictly
  decreased with no new mandatory obligation; otherwise it discards the
  candidate (index and working tree) and re-mints the same cluster; at
  the ADR threshold the cluster is deferred to a human and the loop
  STOPS. Never edit tests, evidence/, verification/, decisions.yaml, or
  the work list. Not a producer skill (pair with the kind's producer).
license: Apache-2.0
compatibility: Linux seat; JDK 21 (javac); Maven offline; git; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - migration
    - m3
    category: migration
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning", "/projects/modernized/verification"]
      writes: ["/projects/modernized/src/main", "/projects/modernized/pom.xml", "/projects/modernized/verification"]
---
# Fix until green (the loop, one card = one cluster)

One state (the destination branch), one predicate (build green, zero
mandatory incidents, tests green, parity), one work list (tools only),
one loop. The model proposes; the tools decide.

## Procedure

Resuming a `VERIFICATION_PENDING` card: keep its retained edit. Once the named
prerequisite changes, restore it with `restore-pending.py` unless the Operator
already restored it, then run acceptance verification **before** `advance.py`.
Restoration does not restore candidate verification; current reports describe
the accepted tree. A premature `LOOP_CANDIDATE_CHANGED` on this pending card
means reverify, not reimplement or mint another attempt.
If the latest diagnosis identifies a repair inside the card's write set, make
that repair on the restored candidate before verifying. A pending record takes
precedence over an "issued cluster no longer open" hint: disappearance alone
does not prove the gate passed. Follow an explicit `REFUSE`/`FAIL` by resolving
its precondition; retry an interrupted advance once only when its verdict is
unknown. An unchanged retry cannot fix stale verification.

Once the brief and reference establish the failing API and its replacement,
make a coherent candidate and verify it. Re-read unchanged inputs only to
answer a specific unresolved question needed for that edit. Files are the
hard write boundary; supporting edits within them are allowed, but this does
not require repairing every behavior in the file. An unchanged runtime concern
that is not a prerequisite belongs in the handoff for its later gate, not an
open-ended investigation before this checkpoint. Fix regressions introduced by
your candidate; do not defer those as unrelated work.

For redirect parity, copy the **captured status**, not a convenient redirect
helper. If the source answered 302 and the method returns JAX-RS `Response`,
use `Response.status(302).location(target).build()` with the source-matching
target. `seeOther` selects 303; `temporaryRedirect` selects 307. Omitting
`.build()` returns a `ResponseBuilder`, not a `Response`. Keep the existing
response API; introducing an unavailable Servlet API or a dependency does not
repair this mismatch. Obtain a fresh scope amendment before any configuration
edit on a new card; a prior card's amendment never carries over.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/brief.py" --root /projects/modernized --cluster <id>   # 1. THIS card (issued.json if --cluster omitted and $HERMES_KANBAN_TASK matches; never the work-list head after a bounce)
#   … patch the write set one item at a time (the brief lists each item with its advice and,
#     for pom.xml, the element at the reported line); never a whole-file rewrite; never tests … # 2. propose
bash "${HERMES_SKILL_DIR}/scripts/run-verify.sh" --root /projects/modernized --mode acceptance  # 3. tools recompute the work list
python3 "${HERMES_SKILL_DIR}/scripts/advance.py" --root /projects/modernized \
  --cluster <cluster id from the brief> --card "$HERMES_KANBAN_TASK"               # 4. accept / revert / pending / defer, then mint or block
#   (terminal tool `timeout: 600` for verify and advance; foreground only.
#    Retry an interrupted advance once with the SAME arguments; it answers "ACCEPTED already" /
#    "REVERTED already". A recorded verdict is final; nonzero alone is not a retry instruction.)
```

Optional cheap pass before acceptance (classpath + JDK diagnostics only; cannot feed `advance.py`):

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-verify.sh" --root /projects/modernized --mode diagnostic
```

On a verifier process failure, read that invocation's output and
`verification/build/run.json` if present; name the failed phase and exact
error. Retry once only after correcting an identified invocation problem.
If it persists, block with that evidence. Do not add a separate Maven run,
background verification, or try shell/path variants without a diagnosed
cause. Normal compiler errors are measurements, not verifier failures.

For parity, start with this invocation's `verification/parity/_run.json`:
check its card/candidate binding and `receipt.composed_by_this_run`, then read
each selected `scenarios.results[].reason`. A matching body does not settle
status, headers, effects or navigation. Older scenario files in another mode
or directory are not this candidate's evidence. If advance rejects newly
reported obligations, the next attempt must address those differences too;
repeating the same edit repeats the rejection. Use an existing evidence-backed
scope amendment before touching another file. If the needed repair cannot be
authorized in this card, preserve the candidate and block with the measured
dependency. Do not normalize the comparator or assume a later card can close it.

For `REFUSE: PACKAGE` or `REFUSE: BOOT`, read the corresponding
`verification/build/package.json` or `boot.json` and the file its `log` field
names (`verification/build/package.log` / `boot.log`). Inspect the first failing
build step and its exception chain; the console summary is not the full error.
These paths are readable evidence under this skill. If access is actually
refused, report the attempted read and refusal. Do not start another Maven
build just to rediscover an error already retained in that log. A new failure
caused by classes inside your write set remains your repair, even if the
platform names their external injection point. Fix that candidate before the
next verification; a changed first error alone does not justify a scope block.

For dependency inspection, reuse `verification/build/.work/classpath.txt`
when `verification/build/run.json` records a successful classpath phase and
the POM, Maven configuration and build profiles are unchanged. Filter that
file for the libraries you need; do not rebuild the same classpath for each
filter. If it is missing or stale, obtain fresh evidence through the verifier.

- Evidence: the measured artifact is the packaged application run-verify.sh
  builds under the declared build profiles (`decisions.yaml build_profiles`)
  and starts as the parity phase starts it. `mvn quarkus:dev`, a dev-profile
  build, `java -jar`, or any server you start is NOT evidence (K2 refuses it
  on a loop card). The ONLY way to observe the destination is run-verify.sh:
  it packages, starts, replays the card's scenarios and its read oracles, and
  leaves the verdicts, the destination log and (for a 5xx) the exception
  under `verification/parity`; the brief is their digest.
- Stop: run-verify.sh prints `verify runs on card …: N` with the obligations
  still reported (`verification/loop/verify-runs.json`; the brief's
  `verify_runs`). Use `acceptance_count` and `stop_rule_applies`, not the total
  `count` or a row's `n`: diagnostic runs do not consume this limit. One failed
  acceptance followed by a corrected edit permits its second acceptance run.
  After two acceptance runs with the same obligations still
  reported: write a typed diagnosis (what you changed; what each verify
  measured; the one hypothesis you could not test and the evidence that would
  test it) and `kanban_block` kind=needs_input carrying it. No third verify
  without a new edit. Never start a server to explore.

`advance.py` is a transaction over the candidate verify.py measured:

| Check | Refusal | Effect |
|---|---|---|
| `--cluster` is the issued card (`verification/loop/issued.json`, written by K4) and `--card` is its minted `t_*` | `LOOP_NOT_ISSUED` / `LOOP_WRONG_CARD` | nothing promoted; candidate discarded |
| the product tree is exactly the tree verify.py measured (`candidate_sha256`), for everything this migration owns — every tracked path, plus an untracked file under `src/`, `.mvn/`, `pom.xml`, `decisions.yaml`, `migration.yaml` | `LOOP_CANDIDATE_CHANGED` | nothing promoted; candidate discarded; attempt counted |
| … and the digest moved only because of **untracked files outside** that product — tool output, not a repair (dest v9 `t_46556d5e`: the worker's `javap` diagnosis left extracted `.class` files under `io/quarkus/` at the tree root after its verification, and a measured repair was REVERTED for them) | `LOOP_SCRATCH_IN_TREE` (naming the files) | **not a verdict**: nothing promoted, nothing discarded, **no attempt counted**, the candidate and the scratch stay where they are. Remove the files — `rm [-r] [-f] <path>...` with **exactly** the paths the refusal printed (or paths under them), one plain command, relative to the destination root or absolute inside it — and run `advance.py` again. K2 allows that removal only while this refusal is the latest `advance.py` output in the card log; any other `rm`, a glob, `..`, or a product path (`src/`, `.mvn/`, `pom.xml`, `decisions.yaml`, `migration.yaml`) stays refused. At most eight paths are printed; remove those, re-run, and the next refusal names the rest |
| every changed path is inside the write set (tests are never in one) | rejected: `outside the write set` | candidate discarded; attempt counted |
| the measure is not fully known (harness / environment / unresolved) | `VERIFICATION_PENDING` | candidate files retained; accepted tree restored; attempt **not** counted |
| a changed Java file introduces an unhandled checked exception, or adds one to a member's `throws` — compiler-derived: the last accepted commit and the candidate are modelled under the same compiler configuration, catches and declared throws accounted for | `REVERTED` (`introduced … unhandled checked exception`) | candidate discarded; attempt counted — **even when the measure fell** (javac reports one such site per compilation, so a count can fall while six are introduced) |
| whether a changed file introduces one cannot be decided (a site the compiler could not decide, or incomplete baseline coverage the parse tree cannot settle) | `VERIFICATION_PENDING` (`unassessable-exceptions`) | candidate retained; attempt **not** counted |
| the issued compile diagnostic's identity — file, member, call site, exception, never the line — is gone, the count did not fall, and the compiler now names another member of this card's sealed family | `CONTINUE` (exit 3) | the candidate **stays on the tree**; no attempt; recorded on the issued card; at most one continuation per family member; a continuation that did not move is `REVERTED` |
| the candidate reports an **attribution** compile diagnostic (a symbol javac cannot resolve, a package that does not exist — every code outside javac's flow-analysis set) that the accepted tree's diagnostics snapshot did not report, in any file — javac reports all of those in one compilation, so one the accepted tree lacked was introduced (a deleted method breaks callers in files the card never touched); the identity is line-free (file, code, message digest) | `REVERTED` (`INTRODUCED_COMPILE_DIAGNOSTIC: introduced … compile diagnostic(s) the accepted tree (<sha>) did not have`, up to three named as `path:line code — message`) | candidate discarded; attempt counted — decided **before** the measure, so a count that fell while a caller broke is rejected too; `legal_next`: fix the named symbols in the same write set, never widen it to satisfy a missing import (dest v9 `t_3903f495`: `jakarta.ws.rs.Context` for `jakarta.ws.rs.core.Context` swapped 13 diagnostics for 13 and was parked as exposed) |
| … and what the compiler names now is a **flow-class** diagnostic (unreported exception, uninitialized variable, missing return, unreachable statement — reported one site at a time, so the accepted tree may well have had it) outside every sealed scope of the card, or one the accepted snapshot could not be compared against | `VERIFICATION_PENDING` (`exposed-outside-scope`) | candidate retained; accepted tree restored; attempt **not** counted |
| a failing package/boot gate no longer names the issued obligation | `VERIFICATION_PENDING` (`unproven-repair`) | candidate retained; attempt **not** counted |
| … and the failure the gate names now is **outside this card's write set**, or has no location | `VERIFICATION_PENDING` (`outside-scope-prerequisite`, or `unclassified-gate-failure` when nothing locates it) with `GATE_FAILURE_OUTSIDE_SCOPE`: the offending paths, the card's write set, the beans the container names and which of them this candidate changed, and the **Operator prerequisite**; the same facts are on the pending record (`outside_scope`) | candidate retained; attempt **not** counted. Do **not** edit those files in this candidate, widen the write set or re-run the build to diagnose them: a location is not a cause (v16 `t_d3f89ded`: a CDI ambiguity named unchanged consumers while the beans that caused it were another card's). The Operator classifies it and records the repair with `operator-step.py` beside the pending card (then `restore-pending.py`, `run-verify.sh --mode acceptance`, `advance.py`), or rejects the candidate when it changed a bean the failure names. Nothing is accepted by filename |
| a **parity** card: every issued obligation's scenario comes back `PASS` in the re-composed receipt, no entry point that was `PASS` before is anything else now, the tuple did not regress and package/boot did not go backwards | accepted (`the parity comparison discharges …`) | the repair is accepted with the tuple unchanged — a parity repair is invisible to `(incidents, compile, tests)` |
| a **parity** card whose obligation is still reported, or that broke a scenario the receipt recorded `PASS` | `REVERTED` | candidate discarded; attempt counted |
| a **parity** card whose comparison did not run or whose receipt could not be composed | `VERIFICATION_PENDING` | nothing was measured about the obligation; candidate retained; attempt **not** counted |
| a **parity** card whose re-composed receipt is a measurement of another card or of a tree this verification did not measure (its `binding`) | `VERIFICATION_PENDING` | somebody else's evidence is not this card's; candidate retained; attempt **not** counted |
| a **unit** card (its sealed scope is `rhoai3.batch-scope/v4`, `kind: unit`): every diagnostic the unit sealed is gone, every sealed member assesses clean (`assess_unit`, from the tree), no test or incident slot regressed, no gate went backwards — and what the compiler still reports is only what the unit's sealed symbols or its **catalogued** targets explain | accepted (`the unit's obligations are discharged at its checkpoint; N diagnostic(s) remain that its sealed symbols explain`) | the compile count may stand still, or briefly rise, at the checkpoint — that is what makes a coordinated multi-file repair expressible. Each tolerated diagnostic is recorded on the step as `explained_regressions` with the catalogue row that documents it; the build or config cluster that closes the gap is the **next** card, never a wider write set |
| a **unit** card whose remaining diagnostics its sealed symbols do NOT explain — a token nothing in the file binds, a replacement no catalogue row documents, a file outside the file seal, or a second symbol family | `REVERTED` (`introduced … compile diagnostic(s) the accepted tree did not have`) | the introduced-attribution veto is partitioned, not weakened. A diagnostic is explained only when its token RESOLVES, through the declaring file's own imports in the compiler model, to a qualified identity that is a sealed symbol or a catalogued target: `jakarta.ws.rs.core.Context` has a `symbol_renames` row and `jakarta.ws.rs.Context` does not, so dest v9 `t_3903f495` still reverts with the symbols named — and an unbound `UriBuilder`, spelled like the catalogued target but imported by nothing, explains nothing either |
| a **unit** card whose sealed symbol is an **adapter-owned annotation** (`compat-mapping.json` `adapter_owned_annotations`, keyed by the qualified name: today `org.springframework.web.bind.annotation.CrossOrigin`, whose behaviour the CORS response adapter owns, ADR-019) | the unit's `target_symbols` row is `retire: true` with no `to`, and the brief's `first_action` is the row's action: delete the annotation, class-level or method-level, with its arguments, and its import — nothing else | accepted like any retirement: the sealed identities are gone and every member assesses clean. In a diagnostic family or a package leaf the compiler's complete parse proves the name absent despite unrelated attribution errors (`proof: parsed-symbol-absence`); a missing or incomplete parse, the annotation or its import left, or a deleted handler refuses. A replacement annotation, a filter or `quarkus.http.cors.*` is no part of it, and another package's `CrossOrigin` gets no row. The retirement clears a compile obligation only: the CORS parity obligation and its owed adapter unit still stand (v16 `t_7074fcda`) |
| a **unit** card whose sealed symbol is the type of an **HTTP handler parameter** with a `handler_parameters.undocumented` row (today `UriComponentsBuilder`, `BindingResult`, `Errors`) | the unit's first `target_symbols` row is `handler_parameter: true` with that row's action and the handler `sites`; a `symbol_renames` row for the same symbol covers only the other uses (`applies_to`, `not_for`: those handlers), and the brief's `first_action` says both in that order | `assess_unit` checks every sealed handler after the candidate: it must still exist, and must not take the retired type or its renamed type unless that parameter carries `@Context` -- an unannotated `UriBuilder` compiles and is refused at augmentation as a second request body (v16 `t_7074fcda` / `t_d3f89ded` run #25). A helper's or a local's builder keeps its mapping; another package's type spelled the same way is not matched. For `BindingResult`/`Errors` the row is a **conditional translation** (V16-8): `hasErrors()` becomes `!validator.validate(<body>).isEmpty()` and `!hasErrors()` becomes `validator.validate(<body>).isEmpty()`, the rest of the guard verbatim; the checkpoint compares the handler's validation guards with the frozen source handler's (compiler models of both; `INVERTED` named) and refuses a `@Valid` left on a handler that validates itself |
| a **unit** card where the compiler now names another member of the same unit (a file the unit seals, at a member row its inventory carries) | `CONTINUE` (exit 3) | the candidate stays on the tree; no attempt; bounded by the member count and by the did-not-move rejection |
| a **unit** card with a sealed member that `violates` (its operation deleted, its consumer no longer called, its file gone) | `REVERTED` | whatever the measure did: a repair is not made by removing what was to be repaired |
| a **unit** card whose rule owes a concrete implementation (a fragment parent no implementer answers) and has not written it, or wrote a type that does not implement the parent, or (`spring-data-fragment-impl/v1`) wrote a delegate that is not `@ApplicationScoped @jakarta.enterprise.inject.Typed(XImpl.class)` -- its only CDI bean type must be its concrete class, or every injection of the parent is ambiguous with the generated repository (v16 `t_1118e877`; checked structurally from the compiler model, `inconclusive` when it cannot read the class literal), or severed an inheritance the unit was formed on | `REVERTED` | `assess_unit` is rule-specific: a diagnostic family retires its symbols, a declaration closure PRESERVES its declarations and its inheritance and requires the implementation it owes plus the gate it carries |
| a **unit** card with a sealed member that could not be assessed, and **no** introduced diagnostic or checked exception | `VERIFICATION_PENDING` (`unassessable-scope`) | an assessment that could not be made is not one that passed; candidate retained; attempt **not** counted. A KNOWN regression is decided first: the introduced-diagnostic and checked-exception vetoes run before either unassessable return, so v12 `t_b33f25fa`'s seven new files importing a class that does not exist REVERT with the symbol named instead of parking the card |
| the accepted diagnostics snapshot is missing and a current diagnostic carries no accepted `err:` id | `VERIFICATION_PENDING` (`diagnostic-baseline-missing`, `DIAGNOSTIC_BASELINE_MISSING` naming the snapshot) | whether the candidate introduced it cannot be decided, so it is never accepted on a falling count; candidate retained; attempt **not** counted |
| a **unit** card on the `package` gate whose issued obligation is no longer reported, whose sealed members all assess clean, and for EVERY failure the gate now reports there is positive evidence: the typed reach test (`amend-scope.unit_reach`) answers `OUTSIDE_SCOPE` -- never `UNKNOWN` -- and the failure is independent of the candidate (an accepted step already recorded that exact obligation id, or its cause is file-local -- today only `unsupported-spel` -- and the exact expression is unchanged since the accepted commit) | accepted (`gate_handoff`: the obligation it handed off to, where it is, the reach and independence evidence, the accepted commit, and `debt: package+boot owed` -- the closing card still needs both gates passing on one artifact, so M4 is not minted before; a unit that owes CDI beans also carries `bean_obligations` and `bean_wiring: unverified`, because the build stopped before augmentation validated them -- the handoff is never a claim of bean correctness) | the build reports one failure at a time, so the unit cannot make the gate pass and no card can while the unit holds the slot (v12 `t_b33f25fa`: the fragment implementations were right and the build then stopped on an unrelated, unchanged SpEL `@Value`); the new obligation is the next card. An unlocated or set-wide failure, a reach that is `IN_SCOPE` or `UNKNOWN` (no model, no type for the file, an unreadable annotation), a cause not shown independent, an unknown measure, or any member not assessed clean keeps the card `VERIFICATION_PENDING` (`unproven-repair`), and the reason says `GATE_HANDOFF_UNPROVEN` with the cause |
| any accepted candidate that **changed CDI wiring** (a bean added or removed, its scope, `@Typed`, qualifiers, producers, injection points or the supertypes of a bean -- compared from the compiler models of the accepted commit and the candidate) while the package gate did not pass on **this** candidate | accepted with `cdi_wiring` on the step and `NOTE: CDI_WIRING_UNVERIFIED` | compilation cannot establish bean correctness: the step records the change, `verified: false` and `debt: package+boot owed`. The first candidate the package gate reaches (it runs under the decided build profile as soon as the compile count is zero) proves or refutes the wiring; M4 needs both gates passing on one artifact |
| the issued compile diagnostic is still reported, or the measure did not otherwise decrease | `REVERTED` | candidate discarded (index and working tree); accepted reports restored; attempt counted |

| Outcome | What happened | Your terminator |
|---|---|---|
| `ACCEPTED` | exactly the changed paths committed, tool reports snapshotted, work list rebuilt, admission re-sealed, next card minted (K4) with this card as parent and K3-verified | `kanban_complete` (the loop record is the audit; K2 allows it once brief, run-verify and advance ran in this log) |
| `ACCEPTED`, then `LOOP_ADMISSION` / `LOOP_NO_SUCCESSOR` refused (exit 1; e.g. a lost M1 binding) | the accepted commit stands; `verification/loop/continuation.json` records `admission-refused`, `no-successor` or `mint-failed` with the reasons | `kanban_block` kind=needs_input naming the reason -- K2 refuses `kanban_complete` until the continuation is `minted` (v12 `t_b33f25fa` completed with no successor and the board sat idle). Re-running `advance.py` with the same arguments finishes admission and the mint once the prerequisite is restored |
| the worker is halted by the runtime's tool-loop guard (5 identical successful calls, `STOP WORKER_TOOL_LOOP`) | the run is recorded as failed on the board; product edits stay on the tree; no product attempt is spent | nothing -- the runtime ends the run. The card is respawned ONCE (`max_retries` 2) and the new run's brief carries `candidate_on_tree`: its unaccepted edits and the one next action (`advance.py` when the last acceptance run measured exactly this tree, else `run-verify.sh` then `advance.py`). A second halt blocks the card (`gave_up`, with the guard's metadata) |
| `RUN_CONTROL_MISSING`, `HARNESS_RELEASE_MISMATCH` or `MODEL_PROFILE_MISMATCH` from `run-verify.sh`, `advance.py` or `k4_mint.py` (exit 2) | nothing measured, promoted, discarded or minted; attempts and deadline untouched | `kanban_block` kind=needs_input naming it: the run executes only under the platform's run-control record (`/etc/rhoai3/run-control`), the harness release it records and the model profile it pins; a mid-run change is an assisted continuation the Operator records in the platform object, never picked up silently |
| `REVERTED` (exit 1) | same cluster re-issued with the next attempt key | `kanban_complete` — the retry is its own card; never loop inside this card |
| `CONTINUE` (exit 3) | repair-family or unit card: the candidate stays on the tree, the continuation is recorded in `issued.json`, no attempt is spent | none — it is not a verdict. Repair the members the brief lists, `run-verify.sh --mode acceptance`, then `advance.py` again on this card |
| `VERIFICATION_PENDING` (exit 1) | candidate retained under `verification/loop/pending-files/`; issued card kept; K4 will not mint; `advance.py` writes the run's stop request (`HERMES_KANBAN_STOP_REQUEST`, runtime 0011) after the pending row is persisted | none: the runtime blocks the card (`needs_input`, naming the cluster, the cause and the retained candidate) and ends the run -- do not call `kanban_block` or anything else. Only when `advance.py` says `Terminator: kanban_block` (no stop-request variable: an older runtime or a manual run) is `kanban_block` kind=needs_input naming the cluster the terminator. When the prerequisite changes (the Operator's unblock starts a new run): `restore-pending.py` then `run-verify.sh --mode acceptance` then `advance.py`; K2 allows that sequence whenever this card has a pending record. When the prerequisite is Operator-owned (an ADR-008 test port), the Operator records it with `operator-step.py` **beside** this card: the card is not live (its candidate is aside, the accepted tree is on disk), so the step commits and re-measures, the card is kept untouched, nothing is minted, and the restore then runs on that step as its baseline |
| `DEFERRED` (exit 1) | attempt threshold reached → cluster in `verification/loop/deferred.json`; **the loop stops**, nothing mints | `kanban_block` kind=needs_input naming the cluster (Operator: remove the cause, then `operator-step.py --clear-deferred <cluster>` with the product change, or `--clear-deferred <cluster> --disposition-only` when the cause was a harness defect; `rewind.py` only to abandon later steps) |
| (Operator) `scripts/rewind.py` | the Operator puts the loop back at an accepted step: product tree restored and re-measured, later steps and the spent budget moved to the record as `rewound`, deferral cleared, next card minted in a new epoch | not a card action; `--operator` and `--reason` are recorded in `steps.json.rewinds` |
| `REFUSE: LOOP_*` | stale state / no baseline / receipt not authoritative | `kanban_block` kind=needs_input |

## Outcome-board runs

On a run that declares `outcome-board/v1` the transaction is the same, and
the surroundings follow the outcome protocol (`.hermes/LAYOUT.md`):
`outcome_gate.py issue` comes first on every run. A verdict is recorded on
the outcome ledger, and its budget is cumulative across runs and restarts. A
REVERTED attempt is re-issued on the same card instead of re-minted. An
acceptance is begun on the ledger before the commit and recorded after it.
The card completes when the OUTCOME is accepted, not when one cluster is.

## After M4

M4 is a measurement, and `REFUSE` is one of its answers. The close card ends
on `kanban_request_review`; what happens next is one command, run by the
reviewer (or the Operator) once the review audit passes:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/resume-after-m4.py" --root /projects/modernized --exec --operator WHO
```

It refuses unless the verdict is this run's (its `card_id` is the issued close
card, the parity receipt it cites is bound to the admission receipt that seals
the tree), no candidate is retained for the close card, and the product tree
is clean. When the seal is stale for one reason only — a harness generation
rewrote a contract file the receipt seals, and nothing else moved — it re-seals
admission before binding the verdict and records `contract_reseal` (what moved,
both receipts) on the close row and in `release-blockers.json`.

Then it reads the two sides of the evidence separately. **What a card can
repair comes from the parity receipt** — `parity_items` over the receipt on
disk and the verdict files beside it, kept when the locus is a file of this
tree — **never from the verdict's floor list**: v9's REFUSE named
`check-empty-security` and `check-product-tests` and did *not* name
`compose-parity-receipt`, over a receipt that was FAIL with thirteen FAIL rows.
**What no card discharges comes from the failed floors and from the receipt's
refused rows**:

| Floor / row | Owner | Why it is not a card |
|---|---|---|
| `check-empty-security` | ADR-014, one bounded Operator step | method security with no identity provider behind it; the conditional authorization adapter and the Basic/JPA identity mapping are the Operator's, and deleting an authorization semantic or permitting all is refused |
| any receipt row whose reason carries `status 401 vs` / `status 403 vs` | ADR-014, one bounded Operator step | the destination refused a request the source answered — whether the row is typed `INCONCLUSIVE` (the comparison could not be made) or `FAIL` (403 where the source answered 200). The obligation `parity_items` derives from it is **withheld from the mint**: a worker at a controller cannot make a security decision |
| `check-product-tests`, `assert-surefire-results` | ADR-015, a harness capability | the generated product tests are the harness's; a card gets no authority to author or weaken them |
| any other failed floor | no ADR (Operator) | named as-is, so an unowned floor is visible rather than silent |

Each floor is recorded **once** however many receipt rows explain it
(`explained_by` counts them).

| Outcome | What it means | What it does |
|---|---|---|
| `CLOSED` (exit 0) | the verdict is an accepting token the road defines (`ACCEPT_TOKENS`), `failed_floors` is empty, and the receipt names no obligation a card repairs and no floor a decision owns | records the close (`closed: true`), clears `verification/loop/issued.json`, and rewrites `release-blockers.json` from THIS verdict — an empty record naming the verdict that cleared it and when, with what is still `outstanding` (the parity receipt's verdict and entry-point coverage, the coverage account's remaining gaps, the verdict's own reason). Closed is not shipped |
| `RESUMED` (exit 0) | the receipt yields at least one obligation that is not ADR-014's | closes the M4 card on the record, rebuilds the work list, re-seals admission and mints the head cluster — the same transaction an accepted step runs. The loop is running again |
| `BLOCKED` (exit 2) | nothing a card may carry is left once the refused rows are withheld — including a head cluster made of nothing but them, since the mint takes the head and nothing chooses it | mints nothing, keeps the close card issued, and writes `verification/loop/release-blockers.json` naming each floor, each refused entry point, the seat that owns it, and the `withheld_obligations` by id |
| `REFUSE: LOOP_RESUME` (exit 1) | the verdict is not this run's, a worker still holds the tree, or this verdict was already resumed or already closed | nothing changed |

Both at once — v9's first M4 verdict — is the normal case: the parity card is
minted **and** the blockers file is written, one printed line per class. The
loop continues on what it can repair; the decisions are recorded, not hidden.
A resume is not a re-run of M4: the same tree measured again returns the same
verdict.

Measurement contract: a component is known only when its tool ran in this
verification (`verification/build/run.json`). Tests that did not run, an
empty surefire directory, a `mvn test` failure with no recorded failing
test, a skipped MTA rescan, or a pom Maven cannot resolve (the compiler
never saw the sources) make the measure unknown. Unknown is not a
product regression: `advance.py` records `VERIFICATION_PENDING`, keeps
the candidate, and does not count an attempt. Known product regressions
still reject. Diagnostic mode (`run-verify.sh --mode diagnostic`) cannot
feed the acceptance transaction. Unknown ranks above every known measure: a candidate the
tools could measure beats a baseline they could not, provided it adds no
mandatory obligation. Obligation identity is line-free: moving code is
not a new obligation.

The measure is `(mandatory incidents, compile errors, failing tests,
parity mismatches)`. The first three are the tuple; parity sits beside it and
is measured by its own gate — a parity card is accepted when the comparison
the acceptance path re-ran records its scenarios `PASS`, never by the tuple
falling (v9 card `t_77cae2b2`: a correct CORS repair was reverted because
`[0,0,0]` did not decrease and nothing re-compared the scenario). Removing a Spring annotation may add compile errors
while removing an incident — that is progress (lexicographic). Making a
test pass by editing the test is not possible (tests are never in a
write set).

No reviewer seat runs for a loop step: `kanban_request_review` on a loop
card is refused by K2. The card pins `paved-road-m3` (the index that views
this skill); the audit it declares grades the official log plus the loop
record naming the card.

## Verification

- `scripts/fix-until-green.test.py` — bootstrap → baseline → accept →
  revert (attempt 2) → unresolvable candidate retained as VERIFICATION_PENDING
  (attempts stay 0) → known no-progress defer (loop stops) → Operator rewind
  (tree, budget, deferral, new epoch) → re-land → green → M4. URI Location
  family: a transformation that makes the count fall while introducing an
  unhandled checked exception is REVERTED; the family is the sites ONE step
  introduced (a legacy site stays out); Owner→Pet CONTINUEs in the same card
  without an attempt; a stalled continuation rejects; an exposure outside the
  family is a typed VERIFICATION_PENDING.
- Every accepted step is a commit; `verification/loop/steps.json` is the
  append-only record; the sealed work list is rebuilt, never edited.

## Scripts

- `scripts/brief.py` — the head cluster's brief
- `scripts/run-verify.sh` — `--mode diagnostic` (classpath + JDK diagnostics) or `--mode acceptance` (default: online warm-up, then offline JDK diagnostics, surefire, MTA rescan, packaging/startup as soon as the measure is known and the compile count is zero, then the parity comparison **for a parity card** and, under `decisions.loop.runtime_feedback: v1`, one unscoped sweep once the destination boots) → `verify.py`; every tool's exit status and stage duration lands in `verification/build/run.json`
- the packaging and startup gates run as soon as the measure is **known** and the compile count is **zero** — not when the whole tuple is `[0,0,0]`. MTA incidents and failing tests do not stop Maven from producing an artifact, and a packaging or startup regression is exactly what a coordinated multi-file unit causes, so the cheapest moment to catch it is the checkpoint that produced it. The trigger is recorded in `run.json` as `runtime.trigger` (`compile-zero` or `none`) so the audit says why the gate ran; `--mode diagnostic` and `--no-runtime` still never run it
- **runtime feedback** (`decisions.loop.runtime_feedback: v1`): once the startup gate passes, the full scenario comparison runs **unscoped** on any card, bound to the issued card exactly as a parity card's is, and the work list rebuilt after it carries the behavioural failures as parity obligations immediately instead of at M4 — eleven of the isolated experiment's eighteen defects were invisible to the compiler and fell out of one replay. It costs at most one run per candidate: the sweep is skipped, by name, when the tree's receipt is already bound to this candidate digest. `run.json` records which of the two triggers ran (`runtime.parity.trigger` ∈ `issued-card`, `runtime-feedback`) and whether the run was scoped. With the key absent the v9 behaviour stands and only a parity card runs a comparison
- the parity stage runs for a card that carries `gate: parity` (or `--parity` forces it), and the startup gate must have passed in this verification: it copies the receipt it started from to `verification/build/parity-before.json`, runs `paved-road-m4/scripts/run-parity.py` scoped with `--scenario` to the scenarios **sealed on the issued card** (and `--read-oracle` to the entry points sealed there). The live work list is remaining-work only and is never a recovery source: a missing, invalid, inconsistent, or incomplete issuance seal is `VERIFICATION_PENDING` (`issuance-scope-missing`) with no comparison and no attempt — never a silent default to disabled, never a shrink of a two-item seal to the one remaining row, and never the whole corpus. A sealed mode plus explicitly identified read-oracle entry points is a valid comparison with an empty scenario list: only those oracles run, no scenario ids are invented, and `runtime.parity.scoped` stays true so acceptance does not treat it as the whole phase. Acceptance requires the runner and receipt mode to match the issued card; a wrong-mode PASS cannot discharge it. A read-oracle obligation (the entry point's method-and-path replay; it names no scenario) is re-measured by nothing but that replay: dest v9 `t_4d75569c` held a scenario obligation and a read-oracle obligation on one controller, the scoped run skipped every read oracle, the entry point's FAIL record stayed exactly as the baseline had it, and a correct body repair was REVERTED as "still reported". No other card pays for it
- **the verdicts that stage produces are of the CANDIDATE.** `verify.py` above rebuilt the work list on it, so the live admission receipt's worklist seal is the *accepted* tree's and can never match: without `--issued`, every scenario comes back `receipt not authoritative: worklist digest … != sealed …`, the composer refuses, the stale receipt stays on disk and the card is REVERTED (destination v9 card `t_222c582a`, and every parity card before it). The binding the comparison records instead — `{mode: candidate, candidate_sha256, issued_receipt_sha256, card}` on each verdict and on the receipt — is what `advance.py` checks: a "now" receipt bound to a candidate counts only when its `card` is the card being advanced and its `candidate_sha256` is the one `run.json` recorded; otherwise parity is UNMEASURED here (`VERIFICATION_PENDING`, no attempt). The "before" receipt must be the one the card was **issued against**: the accepted snapshot under `verification/loop/accepted/parity/` when there is one, otherwise `parity-before.json`. That snapshot is re-taken by every step that changes what the baseline *is* — an accepted parity step, and the M4 close (`resume-after-m4.py`), because the cards it mints are issued from the receipt M4 composed. The accepted step records the binding it was accepted on
- `scripts/verify.py` — tool outputs + recorded outcomes → work list + state + candidate identity
- `scripts/advance.py` — the acceptance transaction (`--baseline` records step 0; unknown measure → `VERIFICATION_PENDING`)
- `scripts/restore-pending.py` — put a retained candidate back on the product tree (then acceptance verify + advance)
- `scripts/operator-step.py` — Operator step: a decided change to the product tree (an ADR retirement applied by `bootstrap-destination.py --retire-only`) committed, re-measured and recorded as a loop step (`verdict: operator`) so the next card's baseline is true. Refused while an issued card is **live** (no retained candidate: a worker's candidate may be on the tree); recorded **beside** an issued card whose candidate is retained (`VERIFICATION_PENDING`), which keeps the card untouched, records `beside_pending` {cluster, card, cause} in the step, and mints nothing whatever `--no-mint` says, because the pending card owns the head. `--clear-deferred` appends a disposition naming the cluster, its retry key and what it spent, and the budget rises by that (`planner/budget.py` is the one budget answer); `--disposition-only` records that disposition with no product change, for a cause that was a harness defect
- `scripts/resume-after-m4.py` — the edge out of M4 (`--root . --exec`): a composed verdict bound to the issued close card is split into parity obligations (minted as the next M3 card, through `k4_mint.py`, after the work list is rebuilt and admission re-sealed) and release floors no card discharges (`verification/loop/release-blockers.json`, each naming its ADR and seat). The close also makes the comparison it closed on the loop's **accepted parity baseline** (`verification/loop/accepted/parity/`, with `accepted/parity-source.json` recording `{mode: sealed, card}`): a candidate reverted off one of the cards it mints restores *that* receipt, not whatever an earlier accepted parity step left. On v9 it left a receipt composed by a run SCOPED to one scenario, `t_46556d5e` was reverted, the restore put it back over the full M4 receipt, and the rebuilt work list reported `open_clusters 0` / `parity_mismatches 0` — the obligation did not fail, it vanished. Exit 0 resumed, 2 blocked, 1 refused; a second run on the same verdict refuses
- `scripts/refresh-accepted-parity.py` — Operator: after an `operator-step.py` or `rewind.py` that changed the product, the accepted parity baseline is **UNMEASURED** (the receipt on disk described another tree; its digest is kept as history and the other tree's records are set aside under `verification/loop/parity-set-aside/`). Run the whole phase sealed on the accepted tree (`run-parity.py --root .`, no `--issued`), then this command snapshots that receipt into `verification/loop/accepted/parity`, rebuilds the work list, re-seals admission and records `parity_refreshes` in steps.json. It refuses a scoped, candidate-bound or other-mode run, another admission receipt, or an artifact other than the one packaging and startup verified; `--check` changes nothing. While the baseline is UNMEASURED a parity card is retained (VERIFICATION_PENDING), never reverted. A SCOPED acceptance comparison carries every entry point it did not re-run from the accepted baseline (`carried_from` on the row; `parity.carried` on the step), so an untouched scenario is never read as a regression and a re-run one is judged strictly; an entry point whose read oracle the run re-ran for the card (`read_oracles_rerun`) is re-measured, never carried, and its read-oracle obligation is discharged by its own record coming back PASS or its own kind of difference gone with nothing introduced -- the same rule as a scenario obligation.
- `scripts/rewind.py` — Operator rewind to an accepted step (`--to-step N --operator WHO --reason WHY`; re-measures with run-verify.sh, refuses on a measure mismatch, starts a new card-key epoch)
- `scripts/amend-scope.py` — widen a sealed batch card's write set by ONE file, on the record (`--path` + `--reason`), BEFORE touching it; the inventory itself is never rewritten and two amendments per card is the limit. A **unit** card is *revised* the same way and needs `--evidence <kind>:<ref>` — `javac:` a diagnostic identity the current work list carries, `model:` a relation about a symbol the unit sealed, `runtime:` an `rt:` obligation the current work list carries. Prose alone is refused, a stale identity is refused by name, the file must still be one the sealed symbols reach (it implements or extends a sealed declaring type, calls a sealed member, is named by a javac diagnostic about a sealed symbol, or reads the sealed property), and the revision is bounded at four and never past `UNIT_MAX_FILES`. A path that does not exist yet is admissible in exactly one case: the seal records an **implementation obligation** for it — the parent owed a concrete implementation and the naming contract that fixes the new type and its file — and once the file exists the relationship it was authorized on (the new type implements the parent) is verified from the model, here and again at the checkpoint. It is recorded on `issued.json` as `revisions[]` beside the amendment; the inventory, the `unit_id`, the budget and the idempotency key do not move
- `scripts/diagnose.py` — (Operator) investigate a failure no card can carry: `--list` names them, `--open` starts one of two ten-minute attempts, `--close --conclusion LOCATED|ENVIRONMENT|DECISION_REQUIRED|INCONCLUSIVE` records the finding under `evidence/diagnosis/`. It grants no write authority — a product change during an investigation refuses the close — and closing discharges nothing
- `scripts/jdk-diagnostics/JdkDiagnostics.java` — compiler diagnostics as JSON (JDK compiler API)
- `scripts/jdk-dest-model/DestModel.java` — the DESTINATION's own structure from the JDK compiler API: resolved member signatures, what a type actually inherits and what its supertypes declare, and every annotation with its exact character range and its imports. Read through `planner.dest_model`, which caches it against the content of the sources AND the classpath it was compiled with, and raises rather than guessing. A regular expression answered these questions wrongly in both directions (a fully qualified annotation read as absent; a redeclared `findAll()` as underivable; a deleted member as inherited), so nothing here is read from text
- `scripts/_java_runtime.py` — which `java` starts the packaged artifact (`$JAVA_HOME_21` → `$JAVA_HOME` → PATH, as `run-verify.sh` exports it), its `java -version`, and the class-file version the artifact needs; used by `verify-runtime.py` and by the parity runner
- `scripts/_loop_common.py` — shared helpers
- Parity scope amendments accept one complete issued item ID, for example
  `--evidence parity:9b6add2ce842582a`. The older
  `parity:parity:9b6add2ce842582a` form remains valid. Do not combine IDs;
  either form still requires a measured relationship to the requested file.
- `scripts/run-verify.test.sh`, `scripts/fix-until-green.test.py`, `scripts/amend-scope.test.py`, `scripts/brief.test.py`, `scripts/diagnose.test.py`, `scripts/resume-after-m4.test.py` — selftests

## Pitfalls

- Rewriting a whole file through one tool call. The model server buffers a
  tool call's arguments until they are complete, so a 12 KB `pom.xml`
  rewrite is several thousand tokens of silence on the wire and trips the
  stream-read timeout (measured live 2026-09-09: two `APITimeoutError`
  retries on the first pom card). Edit with targeted patches, one incident
  or one dependency block at a time; the verifier measures the result, not
  the size of the edit.

- A behaviour that differs between `mvn quarkus:dev` and the packaged build
  under the declared profiles (v9 `t_d280284d`: a create that worked in dev
  and answered 400 with an empty body packaged) is a build-profile
  difference, not a controller defect: beans gated by `@IfBuildProfile` and
  build-time config are resolved at BUILD time from `decisions.yaml
  build_profiles.active` (ADR-011), and a condition on a profile nobody
  activates removes its bean without a word. The harness's check for it is
  the bootstrap's `BUILD_PROFILE_UNACCOUNTED` block (M2), with
  `bootstrap-destination/scripts/propose-profile-retirement.py --root .`
  proposing the `build_profiles.retire` rows a person accepts (ADR-010) --
  an Operator decision, never a card's. A card names the hypothesis in its
  diagnosis and blocks; it does not run a dev build to compare.
- Touching a file outside the write set: the diff is reverted with the
  step, and K2 refuses the write in the first place.
- "Fixing" by deleting the offending code: incidents drop, but tests or
  parity will count it back at the end.
- Editing `verification/` or the work list by hand: `advance.py` refuses
  on a stale state.
