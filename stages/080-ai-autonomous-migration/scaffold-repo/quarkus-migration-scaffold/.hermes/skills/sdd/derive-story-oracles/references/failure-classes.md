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

## 4. T0_3_SERVICE — write-set overlap of `*Service.java`

`T0_3_SERVICE` is **write-set legality only** (K4 `shared_service_java()`):
the same `*Service.java` must not appear in two stories' `files_writable`.
One story MAY own a shared facade. Split-one-class-per-aggregate is
petclinic architecture, not this mint refuse.

**Wrong reading (v42):** M2 read "owns the service **methods**" as "distribute
methods inside one class" and put `ClinicService` on six stories' write-sets.
That is the overlap K4 refuses.

**Rule:** do not list the same `*Service.java` on two `files_writable` arrays.
Do not treat a shared facade owned by **one** story as a mint refuse. Inventory
1:N supersede (coverage + `tasks.md` template) is how a dest_file row is
retired — not this code.
