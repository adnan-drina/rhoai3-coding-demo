# Contract lifecycle

**Status:** binding (in-tree).
**Authority:** Deputy E-20260814T081104Z GR1.

## Rule

`governance/contracts/` holds **active** contracts only.

Retired, superseded, or obsolete contracts move to `governance/retired/`
(attic) with a status line and a replacement pointer when one exists.

## Fail-closed lint

Any markdown file under `governance/contracts/` whose status line matches
`retired`, `superseded`, or `obsolete` fails land-time validation.

```
python3 .hermes/enforcement/validate-contracts/scripts/check-contract-lifecycle.py --root .
```

Wired into `validate-contracts` (`validate.sh`).

## Why

A tombstone in the active directory trains agents to treat retired text as
citable. DD1/DD4/F9/GR2–GR5 retire more artefacts during the rebuild; without
this rule each retirement leaves another marker beside live contracts.
