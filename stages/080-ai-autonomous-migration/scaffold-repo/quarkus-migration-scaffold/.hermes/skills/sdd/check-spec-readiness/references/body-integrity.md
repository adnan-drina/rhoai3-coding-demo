# Body integrity (GRX merge)

**Status:** binding · **Replaces:** body-immutability, body-digest-own-story,
card-sidecar-digest-cross-assert, constraints-preservation-on-amend,
mint-completeness-constraints, injection-receipts.

An artefact says what it says; nobody edits it afterwards without a typed path.

## Binding rules (lints own precision)

1. Body digest stamp / match — `stamp-body-digest.py`, `check-body-digest-match.py`
2. Own-story digest / card-sidecar cross-assert — dispatch-phase create path
3. Constraints preserved on amend — `assert-constraints-preserved.py`
4. Mint completeness — `assert-mint-constraints-complete.py`
5. Injection receipts — `injection_receipt.py` (F2)

## Bank vocabulary (tip-sync / doctrine pins)

- Amend must not **silently drop** constraints (constraints-preservation-on-amend).
- Digest ownership is the story's **own sidecar** (body-digest-own-story).
- Mint rule: **preserve ≠ invent** (mint-completeness-constraints).
- Cross-assert **card↔sidecar** digests (card-sidecar-digest-cross-assert).
- F2 receipts use schema `rhoai3.injection-receipt/v1`.
