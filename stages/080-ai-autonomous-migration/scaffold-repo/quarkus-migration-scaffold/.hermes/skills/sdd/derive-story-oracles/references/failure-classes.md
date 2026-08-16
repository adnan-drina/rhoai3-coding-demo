# Oracle-design failure classes (T-8 §5 / R-SKILL-E)

Three classes. Fixes belong at **assignment** time (before mint), not by
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
body's `files_writable`. Mint-time: `assert-mint-oracles.py` refuses a
test-shaped cmd that does not name `proves` test source(s) in this write-set
(SR-13 / L2a). An unrelated dest `src/test` file must not satisfy the oracle.

## 3. Comment-satisfiable oracle

A source-grep "oracle" whose pattern can match javadoc or prose describing the
requirement without enforcing code.

**Rule:** for security, use `@TestSecurity` behavioral HTTP asserts — never treat
grep alone as sufficient proof of enforcement.
