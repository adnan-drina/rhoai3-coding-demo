# Plan corpus (O-PLANCORPUS)

Standing archived-plan re-lint with **live M3 gate flag parity**.

## Why this exists

Guards land after a bad plan already passed the live gate. Without a
committed corpus re-linted on every `plan-lint.py` change, those guards
never close the loop against the plans that burned seats.

Plan tip text lives only in the **app-repo** git history
(`/projects/modernized`). A golden-baseline reset orphans those SHAs.
This corpus is the scaffold-side before/after baseline (W4-108b / W4-109b).

## Live flag set (mandatory)

Outer-loop / supervisor M3 gate:

```text
plan-lint.py <tasks.md> migration/mta-findings.json \
  --findings-scope <FINDINGS> \
  --profile migration/architecture-profile.md \
  --story-deploy <DEPLOY> \
  --story-scope '<SCOPE>'
```

**Without `--story-scope`**, the same corpus emits ~17–19 `incident-unowned`
LINTs on *every* version (including accepted plans) — a **false
confirmation**. The corpus gate must use the full flag set.

## Cases

| id | source SHA | expect | signals / notes |
|----|------------|--------|-----------------|
| `s03-6348afe-class` | **6348afe** (real 101-line tip) | RED | O-STRUCTJAVA×2, O-PORTREIMPL, O-M3PRESERVEDAO, O-COLLABOWN |
| `s03-6348afe-real` | 6348afe (tasks+plan+spec) | RED | same class signals (archive twin) |
| `s03-c164532` | c164532 | RED | O-STRUCTJAVA×2, O-PORTREIMPL, O-COLLABOWN |
| `s03-be070fb` | be070fb | RED | O-STRUCTJAVA×2, O-COLLABOWN (revision-trace) |
| `s03-43d3a8e` | 43d3a8e | RED | O-STRUCTJAVA×2, O-PORTREIMPL (revision-trace) |
| `s03-ca57010` | ca57010 | RED | O-PORTREIMPL×2 — STRUCTJAVA cleared |
| `s03-c9be4b0` | c9be4b0 | RED | O-PORTREIMPL×2 (revision-trace) |
| `s03-32812a6-final` | **32812a6** (final accepted) | RED | O-PORTREIMPL×2 + **O-INFERABSENT** (derived-absent; §2.2 corpus-fireable) |
| `s03-post-port-good` | synthetic post-Port | GREEN | PLAN OK (`Shape=create` proceed path) |
| `s01-f7c1329` | f7c1329 | GREEN | archival S01 tip under live flags |
| `s01-915e21f-acceptsubst` | **915e21f** (MiniMax S01 draft) | RED | **O-ACCEPTSUBST**×10 — ceremonial Acceptance L2 (W4-191) |
| `s02-ee834b1` | ee834b1 | GREEN | archival S02 tip under **live-v3** inputs (stand-in previously false-RED `incident-conflict`) |

`s03-6348afe-class` previously held a **52-line reconstruction**. It now
holds the **real** `6348afe` `tasks.md` extracted from petclinic-rest-v3
(W4-108b closed). Expected LINT class names are unchanged. Fixture paths
may be petclinic-shaped; harness core stays migration-general.

**W4-109b revision-trace (S03 M3 chain):** `be070fb` → `43d3a8e` →
`ca57010` → `c9be4b0` → `s03-32812a6-final`. Live guards present at plan
time (`O-STRUCTJAVA`) clear by `ca57010`; `O-PORTREIMPL` (absent at plan
time) still RED on the final accepted plan. Minimum required known-RED
case for the chain end: `s03-32812a6-final`.

Each real-tip dir carries `SOURCE.txt` (sha / story / extract timestamp)
plus `plan.md` / `spec.md` when present on that commit.

## O-M3CASEINPUTS — per-case M3 inputs

Plan text alone is not enough for historical gate parity. Each case declares
its M3 inputs via `migration/m3-inputs.env` (pointers) or case-local
`migration/mta-findings.json` + `migration/architecture-profile.md`.

Resolution order in `plan-corpus-lint.sh` `stage_case`:

1. case-local findings + profile files
2. `migration/m3-inputs.env` `FINDINGS_SRC` / `PROFILE_SRC` (relative to case)
3. `_shared/` stand-in defaults (last resort)

| INPUTS_KIND | Location | Used by |
|-------------|----------|---------|
| `live-v3` | `_shared/live-v3/` (real M1 extract) | S01/S02/S03 archival tips |
| `stand-in` | `_shared/mta-findings.json` + profile | `s03-post-port-good` only (synthetic; live findings flood `incident-unowned`) |

`_shared/live-v3/SOURCE.txt` records PVC/path/md5 provenance. Absolute LINT
counts under live-v3 are comparable to the live historical gate; stand-in
counts are not.

## Run

```bash
bash .hermes/harness/plan-corpus-lint.sh
# or focused:
bash .hermes/harness/plan-corpus-lint.sh --case s03-6348afe-class
```

Host preflight: `bash scripts/track-b/v10-plan-corpus-gate.sh`

## Contract for plan-lint.py changes

Every `plan-lint.py` edit must keep:

1. known-good corpus cases → PLAN OK (`s03-post-port-good`, `s01-f7c1329`)
2. known-RED `s03-6348afe-class` → still RED with the class signals above
3. known-RED `s03-32812a6-final` → still RED with `O-PORTREIMPL` +
   `O-INFERABSENT` (final accepted plan; STRUCTJAVA already designed out;
   derived-absent oracle fires under empty corpus tree)
4. archival real tips (`s01`/`s02`/`s03-c164532`/`s03-6348afe-real` +
   revision-trace `s03-be070fb`…`s03-c9be4b0`) → match their
   `manifest.env` EXPECT rows under the live flag set
