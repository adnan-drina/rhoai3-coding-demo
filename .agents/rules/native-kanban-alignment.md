---
name: native-kanban-alignment
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**
---

# Native review, attachments, and K4 translation — do not retire G1–G4

Operator `112748ZO` measured 32 custom M4 scripts and zero uses of
native `request-review` / `attach` / owned payload→card translation.
Native-first is a default with a **stated exception**. G1–G4 domain
parity (Maven, PIT, HTTP) has no general-tool substitute. Do not delete
those gates on a line count.

Official: `.agents/skills/hermes-kanban/` — `review` is a first-class
state; `kanban_request_review` is a worker terminator; `block` is
escalation not review; attachments 25 MB/file; `kanban swarm` is
parallel workers + verifier + synthesizer.

## Non-negotiable

1. **Keep G1–G4.** Domain receipts (`write-receipt.py`,
   `check-verdict-routing.py`, O1–O3 HTTP) stay. Native `review` does
   **not** replace runtime oracles. When an M4 paved-road exists, its
   audit **executes** those oracles (scripts). That replaces LLM verdict
   prose, not the oracles.
2. **Board lifecycle:** refuse-complete-on-red **STANDS**. Dest seats a
   `reviewer` profile (kanban + terminal; file/code_execution/delegation
   disabled) and pins `kanban.review_dispatch: true` on the **next golden**
   only. Implementer terminator is `kanban_request_review`. Reviewer
   `kanban_complete` is hook-refused unless `assert-paved-road-audit.py`
   last exited 0 on the official log. Dest-init `pre_tool_call` **matcher**
   must include `kanban_complete` (official: tool-name regex). dest-14 M2
   native complete never invoked the hook — `k2_selftest` piping a
   `terminal` CLI command is not dispatcher evidence. The hook appends
   `evidence/receipts/hook/complete-invocations.jsonl` on every complete
   invocation it sees (absence means the matcher never fired). Canary
   card is next golden dest-init, not dest-14. OBJECT dest-apply
   onto dest-14.
   OBJECT parking cards in `review` before that profile exists. Do not
   `kanban_complete` dest-4 `t_9acd47cb` on PASS JSON minted during the
   verdict card (`112249ZA` item 7; Review `112352ZR`). Same-card reviewer
   complete after a green audit **is** Done for that card.
3. **Attachments:** M1/M2 KEEP evidence listed in run metadata MUST also
   `kanban attach` (≤25 MB). PVC paths stay (dual-write). Not dest-4
   mid-run. A dest wipe must not be the only copy of harvest.
4. **K4:** derivation stays in `k4_convert.py`. Graph create is
   **named, tested mint-writer** (`.hermes/kernel/k4_mint.py` → CLI
   `hermes kanban create`). Native-first is
   **not** LLM-first (Operator `113305ZO`): `decompose` **can** express
   serial `parents` (retract “cannot do serial”) and still must **not**
   mint dest cards (`temperature=0.3`, skills are not an input). OBJECT
   `kanban swarm` for serial T0 (official swarm is parallel workers +
   verifier + synthesizer). The swarm/`decompose`-as-mint **ban STANDS**
   (Operator `134635ZO` / `135224ZO` / AMEND `164058ZO`):
   **Cost of the ban:** typed partition vs LLM free decompose; ~K4
   kernel lines. **Not a cost of the ban:** dest-5 missing `--skill` /
   `--workspace` on K4 stories — those are partition/payload gaps
   (items 16–17). dest-5 LLM factory cards are a failed custom barrier,
   not evidence to lift. A measured dest experiment (native `decompose`
   + story-oracle lints vs K4 on the same specimen) is a **later named
   GO**. Do not lift this sitting. Do not implement that experiment.
5. **Fact vs judgement (Operator `113305ZO`):** mechanical facts
   (exec bits, digests, schema, coverage counts) stay **code**. Genuine
   judgement may move to a skill+LLM **only** if a deterministic check
   validates the output. Do not convert the ≥12 pure-logic M4 gates
   this sitting; dest-5 first.
6. **Reviewer-side native:** GitOps golden now seats `reviewer` and
   `review_dispatch: true`. dest-8/dest-14 live boards that predate the
   recut still ran `review_dispatch: false` (`LEGAL_REFUSE=kanban_block`).
   Do not dest-apply this onto dest-14. M4 HTTP oracles stay scripts.
7. **M1→M2 payload (Operator `141045ZO` AMEND `134635ZO` §3.1):**
   dest-5 M1 already attaches bulky artefacts and puts endpoint+symbol
   plus extension **names** in completion metadata. Residue: name the
   M2 **consumer** (`kanban_attachments`); `artifacts_created` may still
   be a path list. Petclinic still needs that named consumer. Do not
   mid-run patch dest-5 M1.
8. **`hermes hooks test --payload-file` is not a semantics harness**
   (Operator `134635ZO` §4, Review `134944ZR`). KEEP
   `verify-fence-on-dest.sh`. Adopt `hooks doctor` **alongside**, never
   instead.
9. Do **not** retire gates on the audit alone. dest-4 M4 `t_9acd47cb`
   is **done** via worker `kanban_complete` (contaminated; do not
   reopen). Land review/attach on golden / dest-5. Next mint: no LLM
   factory cards.
10. **G-4 tokens must agree.** Refusal `N/A` and verdict
   `g4_hook=INCONCLUSIVE` cannot both stand (Operator `114101ZO`).
   SAMPLE-floor `INCONCLUSIVE` is honest (`check-release-readiness`).
   `N/A` is OBJECT for a live `GET /greeting` — G-4 applies; compare
   referent vs dest or leave INCONCLUSIVE. M5 reads the refusal file.
   Gate K M4-O1/O2/O3 are dest HTTP oracles (`090119Z`); they are not
   G-4. Implementing `quarkus-smallrye-health` on the verdict card
   taints O1. CLOSE still waits dest-5 M4 oracles.
11. **Petclinic/coolstore:** not this sitting. Confidence is gated on
    the named M2 attachment consumer and authored `environment.json` /
    G-4 shape (Operator `134635ZO` §7 / `141045ZO`). dest-5 is plumbing,
    not G-1..G-4 depth.
12. **No `--goal` on dest mint** (Research `135838ZS`). `k4_mint.py`
    stays without `--goal`; dest M1–M4 remain `--max-retries 1`. Do not
    wire `auxiliary.goal_judge` as a done-gate.
13. **K4 mint attribution (Operator `145214ZO` / `150131ZO` P0 / AMEND
    `164058ZO` / `180835ZO`):** M2 PLAN must **not** `k4_mint.py --exec`.
    **Retire both LLM factory dest cards** (mint-writer **and**
    mint-verifier). Do **not** reassign the verifier to `implementer` —
    `kanban_complete` on that card would **release M3**. dest
    `orchestrator` cannot run `k3_verify` (`terminal` disabled). K3 stays
    an in-process graph check in `k4_mint` (mechanical fact) then
    `kanban create` with `--workspace dir:/projects/modernized` on
    implementer stories. Stories parent to M2. `k4_mint.py` as CLI
    translation **stays**; the dest cards go. `FACTORY_TITLES` deletes
    with those payloads. dest-5 live factory cards already completed as
    barriers. Do **not** dest-cut a workspace whose mint still emits
    factory cards.
14. **Factory card titles (AMEND `164058ZO`):** `FACTORY_TITLES` is
    keyed by `k3_schema` logical_id (`mint-writer` / `mint-verifier`),
    not a display rename. Do **not** retitle to dodge the factory-card
    ban. Next mint: no factory LLM cards; the map deletes with those
    payloads. dest-5 live titles stay.
15. **Detector narration (Operator `143549ZO`, Review `143749ZR`):**
    fail-closed is **encoded execution**. Narration-alone is not a
    finding. Amend comments that call intent “first-class”. Do not hold
    dest-5 M3 on a narration-only gate.
16. **M3 `--skill` (AMEND `162349ZO`):** dest-5 converter-minted
    stories had empty `--skill` (T001: 11 discovery loads). MATCH'd
    miss. Next mint: partition populates per-story `skills`; `k4_mint`
    already forwards them to `hermes kanban create --skill`. Empty
    `--skill` on migration stories is a K4 contract fail.
17. **M3 workspace (Lead `145858ZL`, Operator `151038ZO`):** implementer
    stories mint `--workspace dir:/projects/modernized`. Scratch is
    OBJECT. dest-5 stories completed via absolute dest paths with empty
    scratch — FLAG, not dest SUCCESS of the mint contract.
18. **Gates vs withdrawn claims (Operator `145724ZO` / AMEND
    `164058ZO` Pattern 1):** a gate must not go green only because the
    worker deleted or softened the assertion. dest-5 six instances:
    `created_cards` dropped from `kanban_complete`; `PATH_IN_PROSE`
    sentences deleted from `tasks.md`; empty `## Non-Goals`; minted
    `assert-pinned-gates-ran` artifacts; `check-domain-parity`
    `"ran": false` counted as evidenced; `assert-g4-claim-consistency`
    refusal text iterated until accepted. Write-set is the typed
    partition, not PATH_IN_PROSE on tasks.md.
19. **`mvn -q test-compile` is not an exit criterion** (Operator
    `151548ZO` / `153126ZO`). Compiling is not running. A toolchain
    claim needs a real test source, or must not be claimed.
20. **Partition vs acceptance (Operator `153126ZO`):** a story whose
    acceptance needs a pom change must have pom in `files_writable`, or
    must not carry that acceptance. If scope cannot satisfy acceptance,
    terminator is `kanban_block`, not `kanban_complete`.
21. **dest-5 M4 (Operator `153126ZO` / AMEND `161806ZO` / `162349ZO` /
    `172359ZO`):** GO GRANTED; unaided-detection experiment **VOID** then
    **superseded**. Batch 1 makes "did M4 notice Failures>0" a floor
    REFUSE, not a worker job. dest-5 surefire reports are **gone**. Do
    **not** manufacture XML. Do **not** dest-dispatch M5. Do **not**
    dest-apply unpublished golden. Next-cut question: given a REFUSE,
    does M4 report it or Pattern-1 around it (`164714ZA`). OBJECT
    implementing `quarkus-smallrye-health` on the **verdict** card
    (`113157ZA`). Gate K stays OPEN.
22. **Disabled toolset silence (Operator `150553ZO`):** a disabled
    toolset must refuse by name, not vanish. dest-5 mint-verifier
    completed a false DAG claim after three silent terminal calls.
23. Do **not** add `/usr/lib/jvm` to `K2_ALLOW_ROOT` (`214325ZA`).
    JAVA_HOME export is already not access. Listing JDKs via that path
    is still OBJECT to widen allow-root.
24. **Exit criteria are a floor, not a definition of done** (Operator
    `161504ZO`). Meeting listed checks (`mvn -q test-compile`, skill
    consult) does **not** authorize `kanban_complete` when the worker
    has diagnosed that card acceptance cannot be met inside
    `files_writable`. Terminator is `kanban_block`. Blocking is a legal
    result, not a failure. Story bodies must name that outcome (Lead
    implements). Replacing one command (`test-compile` → `clean test`)
    does not retire this rule. `k4_convert.py` stamps those checks on
    every story; do not treat that list as exhaustive. dest-5 M4 is the
    largest instance (`162349ZO`): minted floor artifacts authorized
    `PROVISIONAL_ACCEPT` while surefire was unread. **AMEND `164230ZO`:**
    naming `kanban_block` is necessary and **not sufficient**. dest-4
    M2: `init-spec-workspace` SKILL.md names `kanban_block` on
    external-dirs exit 1; the worker re-read ~7 times and completed.
    Lead: refuse `kanban_complete` when a bound gate last exited
    non-zero — enforcement, not another paragraph.
25. **Channel split (Operator `161806ZO`):** Operator/Lead `Needs:`
    rows are not dest worker contract. Do not transcribe them into
    kanban card bodies. dest-5 M4 body item 5 (`do not repair` /
    `intentional M4 experiment`) VOID'd the unaided-detection question.
26. **M4 must not pre-specify the verdict token (Operator `161806ZO`):**
    dest-4 `t_9acd47cb` body has no token (derived
    `PROVISIONAL_ACCEPT`). dest-5 `t_ecdb4eb9` body hands
    `Token: PROVISIONAL_ACCEPT, ship: false`. A verdict phase handed
    its verdict is not a verdict phase. Next mint / clean-card rerun:
    O1/O2/O3 + parent-walk pre-verdict; **no token** in the card body.
27. **M4 must read test results, not only test files (Operator
    `161806ZO` / AMEND `162349ZO`):** surefire reports under `target/`
    are the unit-test oracle. Reading `HealthTest.java` is not reading
    `HealthTest.txt`. dest-5 M4: 0 surefire mentions in 1097 lines,
    then rebuilt until `target/surefire-reports/` was **gone**. Do not
    destroy unread evidence. Artifact presence under
    `evidence/verdicts/` is not a gate run (item 2).
    `assert-pinned-gates-ran` `verdict: PASS` must **not** list a gate
    whose artifact is `"ran": false` as `evidenced`.
28. **K4 mint must pass `--skill` per story (Operator `162349ZO`):**
    harness-minted dest-5 cards used native `--skill`; K4-minted M3
    stories used none. Same asymmetry as `--workspace` (`151038ZO`).
    Factory cards with a disabled `skills` toolset stay OBJECT to
    assign as implementer (item 13).
29. **Skills must not instruct a K2-refused path (Operator `164230ZO` /
    Research `163815ZS`):** `inventory-legacy-surface` still documents
    `/projects/.derived/legacy-at-3`; the fence refuses it. Do **not**
    widen allow-root to match a bad skill path (item 23). Lead: point
    the skill at `/projects/legacy` (identity referent). Bad
    `external_dirs` entries must refuse by name, not skip silently
    (item 22).
30. **M4 terminator split (Architect `151211ZA`, recut 2026-08-28):**
    refuse-complete-on-red STANDS. Implementer terminator is
    `kanban_request_review` (item 2). `kanban_block` is
    external/platform escalation (MaaS 500, missing key, GPU), not a
    substitute for `request_changes`. GitOps golden seats `reviewer` and
    `review_dispatch: true`. OBJECT parking M4 in `review` on dest-14
    (predates the recut). Do not dest-apply dest-14.

