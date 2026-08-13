# `mta-findings.json` preserved model (provisional lock)

**Status:** provisional lock (`rhoai3.mta-findings/v1-provisional`)  
**Source of bytes:** copy of `mta-cli` / `kantra` `--json-output` **plus** our
`execution_evidence` envelope (skill `scan-with-mta` →
`scripts/normalize-findings.py`).  
**Blocked on live re-measure** until a workspace has a working CLI (host 7.3
rulesets broken). Field list is from PROBE + Konveyor shape + Architect W2 §11.5.

## Envelope (ours)

| Field | Required | Notes |
|-------|----------|-------|
| `schema` | yes | `rhoai3.mta-findings/v1-provisional` |
| `execution_evidence.analyzer_ran` | yes | false → G-3 INCONCLUSIVE |
| `execution_evidence.cli` | yes | path/version string |
| `execution_evidence.rule_set` | yes | targets / label selector summary |
| `execution_evidence.input_digest` | recommended | `harvest_referent` sha256 |
| `execution_evidence.context_lines` | optional | `--context-lines` (default 100) |
| `violations` | yes | map keyed by rule id (tool shape) |

## Per-violation (tool)

| Field | Required | Notes |
|-------|----------|-------|
| `ruleID` | yes | |
| `category` | yes | mandatory / optional / potential / information |
| `effort` | yes when present upstream | story points |
| `description` | recommended | |
| `labels` | recommended | |
| `incidents[]` | yes (may be empty only if tool emits none) | |

## Per-incident (tool) — **codeSnip required in preserved model**

| Field | Required | Notes |
|-------|----------|-------|
| `uri` | yes | |
| `lineNumber` | yes | |
| `message` | yes | |
| `codeSnip` | **yes in our preserved model** | AD-003 gap closed; supporting code |

## Applicability vs deferral

Do **not** overload deferral. Tool-wrong cases use `mta-exception`
(`governance/schemas/mta-exception.md`) with `re_open_trigger`, counted in G-3.

## Validate

```bash
python3 .hermes/skills/analysis/scan-with-mta/scripts/normalize-findings.py evidence/mta-findings.json
python3 .hermes/skills/analysis/scan-with-mta/scripts/validate-findings-schema.py evidence/mta-findings.json
```
