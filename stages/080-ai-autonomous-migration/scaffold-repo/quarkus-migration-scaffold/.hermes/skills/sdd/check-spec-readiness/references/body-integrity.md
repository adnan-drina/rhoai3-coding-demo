# Body integrity (GRX merge)

**Status:** binding · **Replaces:** body-immutability, body-digest-own-story,
card-sidecar-digest-cross-assert, constraints-preservation-on-amend,
mint-completeness-constraints, injection-receipts.

An artefact says what it says; nobody edits it afterwards without a typed path.

## Binding rules (lints own precision)

1. Body digest stamp / match — `stamp-body-digest.py` (first stamp),
   `restamp-card-and-sidecar.py` (repair), `check-body-digest-match.py`
2. Own-story digest / card-sidecar cross-assert — dispatch-phase create path;
   re-stamp updates card and sidecar as one operation or refuses
3. Constraints preserved on amend — `assert-constraints-preserved.py`
4. Mint completeness — `assert-mint-constraints-complete.py`
5. Injection receipts — `injection_receipt.py` (F2)

## Bank vocabulary (tip-sync / doctrine pins)

- Amend must not **silently drop** constraints (constraints-preservation-on-amend).
- Digest ownership is the story's **own sidecar** (body-digest-own-story).
- Mint rule: **preserve ≠ invent** (mint-completeness-constraints).
- Cross-assert **card↔sidecar↔file** digests (card-sidecar-digest-cross-assert).
  Re-stamp is atomic (restamp-card-and-sidecar-atomically). Live
  `hermes kanban show --json` nests markdown under `task.body` (V35-DIGEST).
- F2 receipts use schema `rhoai3.injection-receipt/v1`.
