# Oracle-design failure classes (T-8 §5 / R-SKILL-E)

Four classes. Fixes belong at **assignment** time (before mint), not by
weakening the gate.

## 1. Wrong-class oracle

An exit whose concern the story's write-set cannot produce evidence for
(e.g. HTTP-semantics check on a config-only story; query-path check on an
entity-mapping-only story).

**Rule:** before stamping, confirm each `operand_class` token's allow-list
membership (`OPERAND_CLASS_SEMANTIC_EXITS` union). Set membership is
decidable **before** the oracle runs. Phase AC supplies the **cmd**.

**Gate:** `check-surgical-scopes.py` refuses foreign semantic exits even when a
legal exit is also present (dual-oracle).

## 2. Vacuous pass

The asserted fact was already true before this story's writes (prior story
created the FK / schema / route). Executable but not informative about **this**
story.

**Rule:** prefer before/after delta, or scope the claim to artifacts in **this**
**body's** `files_writable`. Vacuous-pass refuse lives in KEEP
`check-semantic-exits.py`. An unrelated dest `src/test` file must not satisfy the oracle.

## 3. Comment-satisfiable oracle

A source-grep "oracle" whose pattern can match javadoc or prose describing the
requirement without enforcing code.

**Rule:** for security, use `@TestSecurity` behavioral HTTP asserts — never treat
grep alone as sufficient proof of enforcement.

## 4. T0_3_SERVICE — whole-domain service is not foundational

`T0_3_SERVICE`: a whole-domain `*Service.java` is not foundational. **Split into one service class per aggregate** (example names: `OwnerService`, `PetService`) — each owned by the story that owns those entities. Do **not** distribute methods within a shared class: the shared file still imports every aggregate and will fail the topological check (`CYCLE_IMPORT`).

**Wrong reading (v42):** M2 read "owns the service **methods**" as "distribute methods inside one class" and authored `Add … to ClinicService` on six stories. Coverage still saw one `dest_file`; the shared class still imported every aggregate.

**Rule:** one **service class** per aggregate, owned by the story that owns those entities. Do not keep a vestigial facade `ClinicService` so a 1:1 `dest_file` row stays green. The 1:N supersede exception (coverage script + `tasks.md` template) is how the inventory row is retired — not methods-in-shared-class.
