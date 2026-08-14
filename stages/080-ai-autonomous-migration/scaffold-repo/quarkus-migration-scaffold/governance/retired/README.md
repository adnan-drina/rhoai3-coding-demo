# Retired governance artefacts

**Active contracts live only under `governance/contracts/`.**

When a contract is retired, superseded, or obsolete:

1. Move the file here (preserve the basename).
2. Keep a short `**Status:** retired|superseded|obsolete` line and a
   `**Superseded by:**` / replacement pointer when one exists.
3. Do **not** leave tombstones under `governance/contracts/`.

Enforced by
`.hermes/enforcement/validate-contracts/scripts/check-contract-lifecycle.py`
(GR1 / Deputy E-20260814T081104Z). See
`governance/contracts/contract-lifecycle.md`.
