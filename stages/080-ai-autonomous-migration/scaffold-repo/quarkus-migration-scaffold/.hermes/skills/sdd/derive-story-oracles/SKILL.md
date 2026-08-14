---
name: derive-story-oracles
description: Before minting or reminting an M3 body's exit_criteria — map operand_class and write-set concern to class-legal semantic exits, refuse wrong-class and dual correct+wrong oracles, and prefer executable techniques over greps; use when assigning story-class verification
license: Apache-2.0
compatibility: Linux seat; M3 typed bodies; specimen-agnostic vocab
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - sdd
    - oracles
    - m3
    category: sdd
    kind: guidance
---
# Derive story-class oracles (T-8)

Guidance only (R-SK.14). Replaces the retired `semantic-exits.md` family table
with **derivation**: match the story's concern to an official executable
technique, then stamp only class-legal `exit_criteria[].check` names from
`specimen_agnostic.OPERAND_CLASS_SEMANTIC_EXITS`.

**Enforcement** (not this skill): `check-surgical-scopes.py` refuses missing
legal exits **and** any foreign semantic exit even when a legal one is also
present (dual-oracle refuse).

Official technique table and failure classes: `references/concern-oracle-table.md`,
`references/failure-classes.md` (T-8 Research grounding; no specimen literals).

## When to Use

- Before M2/M3 mint or remint of `exit_criteria` / `done_when`.
- When a worker typed-blocks on a wrong-class exit (CONFIG + `http_semantics`,
  entity-only + `hql_entity_path`, …).
- When reviewing whether a grep-shaped check is strong enough for the claim
  (comment-satisfiable risk).
- **Not** for write-set overlap — `partition-coverage` / surgical write rules.
- **Not** for domain G-1..G-4 measurement — `check-domain-parity`.

## Procedure

1. Read `identity.operand_class` (or infer from write-set: pom/build →
   `build_config`/`pom`, properties/config → `config`, REST → `rest`, …).
2. Open `references/concern-oracle-table.md` — pick the **official executable
   technique** for the concern this story can actually produce evidence for.
3. Stamp `exit_criteria` using **only** checks in
   `OPERAND_CLASS_SEMANTIC_EXITS[operand_class]` (see
   `../check-spec-readiness/scripts/specimen_agnostic.py`). At least one
   required; **zero** foreign semantic names.
4. Refuse the three failure classes in `references/failure-classes.md`
   (wrong-class, vacuous pass, comment-satisfiable).
5. Lint before mint:

```bash
python3 ../check-spec-readiness/scripts/check-surgical-scopes.py <root> <body.json>
```

6. Family stamps (`identity.semantic_families`) remain optional REST detail —
   still linted by `check-semantic-exits.py` when present; they do not replace
   class-legal derivation.

## Pitfalls

- Satisfying the gate by adding a legal exit **beside** a wrong-class one —
  dual-oracle refuse (T-8).
- Grep oracles for security/authz that a javadoc can satisfy — use
  `@TestSecurity` behavioral asserts (concern table).
- Absolute-state oracles that were already true before this story's write-set
  (vacuous pass) — require a delta or write-set-scoped claim.
- Reintroducing specimen literals into exit vocab (R-SK.5).

## Verification

- `check-surgical-scopes.py` exits 0 on the body.
- Wrong-only **and** correct+wrong foreign exits both FAIL.
- Legal-only body for the class PASSES.
- Retired contract lives only at `governance/retired/semantic-exits.md`
  (not under active contracts/).
