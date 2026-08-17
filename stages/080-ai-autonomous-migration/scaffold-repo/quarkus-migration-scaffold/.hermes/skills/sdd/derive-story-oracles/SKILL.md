---
name: derive-story-oracles
description: Before minting or reminting an M3 body's exit_criteria — take phase acceptance criteria as the exit oracle, treat operand_class as a set for class-legal names and B-16 skill attachment, refuse wrong-class/dual-oracle and vacuous always-true cmds; use when assigning story-class verification
license: Apache-2.0
compatibility: Linux seat; M3 typed bodies; specimen-agnostic vocab
metadata:
  author: rhoai3-harness-team
  version: "1.1.1"
  hermes:
    tags:
    - sdd
    - oracles
    - m3
    category: sdd
    kind: guidance
---
# Derive story-class oracles (T-8 AMEND)

Guidance only (R-SK.14). Replaces the retired `semantic-exits.md` family table
with **derivation**: the phase **acceptance criteria** are the exit-oracle
source; `operand_class` is a **set** for B-16 skill attachment and the union
of class-legal `exit_criteria[].check` names from
`specimen_agnostic.OPERAND_CLASS_SEMANTIC_EXITS`. **OBJECT dropping the
field. OBJECT a default `mvn -q test` on every card.**

**Enforcement** (not this skill): `check-surgical-scopes.py` refuses missing
legal exits **and** any foreign semantic exit even when a legal one is also
present (dual-oracle refuse). `semantic_exit_cmd_ok` accepts the Maven
vehicle (`mvn test|verify|test-compile`; `compile` for `build_resolves`).
curl / scripts are not card exits — an HTTP AC is a `@QuarkusTest` in
this write-set (B-1). `true` still refuses.

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

1. Read `identity.operand_class` as a **set** (string or list). Unknown
   tokens that are not `user_story` **stop** — fail-closed
   (Architect E-20260814T181701Z). Do not infer REST/HTTP exits onto an
   unrecognised class. `user_story` is AC-sourced.
2. Stamp `exit_criteria[].cmd` from the phase **acceptance criteria**. Do
   not invent `mvn -q test` because the class map used to. If the AC is a
   test-shaped `mvn … test` or `mvn … verify`, the proving test lives in
   **this** write-set (SR-13 / L2a). Do not stamp `curl` or a script as
   the card exit.
3. Open `references/concern-oracle-table.md` — pick the **official executable
   technique** for the concern this story can actually produce evidence for.
   `bootstrap` stamps only `app_boots`. `persistence` stamps only `mapping_valid`.
   Do not alias those onto `health_probe` / `hql_entity_path` / `create_fk`.
4. Named checks must sit in the **union** of
   `OPERAND_CLASS_SEMANTIC_EXITS[c]` for each class `c` (see
   `../check-spec-readiness/scripts/specimen_agnostic.py`). At least one
   required for known classes; **zero** foreign semantic names.
5. Attach skills with `skills_for_operand_classes` (B-16) — rest →
   `spring-to-quarkus-patterns`, persistence → `form-entity-persistence`.
6. Refuse the three failure classes in `references/failure-classes.md`
   (wrong-class, vacuous pass, comment-satisfiable).
7. Lint before mint:

```bash
python3 ../check-spec-readiness/scripts/check-surgical-scopes.py <root> <body.json>
```

8. Family stamps (`identity.semantic_families`) remain optional REST detail —
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
- Stamping `curl` or a script as the card exit — live HTTP is M4/M5;
  the AC names a `@QuarkusTest` in this write-set.

## Verification

- `check-surgical-scopes.py` exits 0 on the body.
- Wrong-only **and** correct+wrong foreign exits both FAIL.
- Legal-only body for the class PASSES.
- Retired `semantic-exits` contract is not in golden (no `governance/` folder).
