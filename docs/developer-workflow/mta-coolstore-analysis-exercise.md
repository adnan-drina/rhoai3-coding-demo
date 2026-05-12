# MTA Coolstore Analysis Exercise

## Purpose

Run or review a Migration Toolkit for Applications analysis of `rhpds/mca-coolstore` and capture the evidence needed before using Developer Lightspeed for MTA or drafting custom rules.

This is a planned Stage 160 exercise. It is documentation-only until a live workspace has MTA, Developer Lightspeed for MTA, and a checked-out Coolstore source tree.

## Source Application

Primary brownfield source:

```text
https://github.com/rhpds/mca-coolstore
```

Use the [`mca-coolstore` candidate assessment](mca-coolstore-candidate-assessment.md) as the current source-selection baseline. Record the exact commit used for any live run because MTA findings are only meaningful when tied to a source revision.

## Preconditions

- Stage 080 MTA and Developer Lightspeed for MTA platform foundation is available, or the MTA CLI is installed locally.
- The developer workspace can access the Coolstore repository and required Maven dependencies.
- The model path for modernization context is approved for source-code analysis.
- The MTA source and target technologies are selected and recorded.
- Any custom rules used in the run are reviewed and versioned.

## Analysis Inputs To Record

| Field | Value |
| --- | --- |
| Repository URL | `https://github.com/rhpds/mca-coolstore` |
| Source commit | Pending live run |
| MTA version | Pending live run |
| MTA execution path | Pending: UI, VS Code extension, or CLI |
| Source technologies | Pending live run |
| Target technologies | Pending live run |
| Rulesets | Pending live run |
| Custom rules | Pending live run |
| Maven settings or offline mode | Pending live run |
| Model path for Developer Lightspeed | Pending live run |

## CLI-Oriented Dry Run

Confirm the exact source and target labels before running analysis:

```bash
mta-cli analyze --list-sources
mta-cli analyze --list-targets
```

Then run the analysis with recorded source and target values:

```bash
mta-cli analyze \
  --input /path/to/mca-coolstore \
  --output /path/to/mta-output/mca-coolstore \
  --source <source-technology> \
  --target <target-technology>
```

If custom rules are part of the exercise, add them only after review:

```bash
mta-cli analyze \
  --input /path/to/mca-coolstore \
  --output /path/to/mta-output/mca-coolstore-with-custom-rules \
  --source <source-technology> \
  --target <target-technology> \
  --rules /path/to/reviewed-rules
```

## Evidence To Capture

The MTA CLI can produce report artifacts such as:

- `analysis.log`;
- `dependencies.yaml`;
- `output.yaml`;
- `shim.log`;
- `static-report/`;
- `static-report.log`.

Capture a summary record instead of committing raw generated reports in this planning branch:

| Evidence | Value |
| --- | --- |
| Analysis command | Pending live run |
| Report path or URL | Pending live run |
| Finding count | Pending live run |
| Selected finding | Pending live run |
| File and line reference | Pending live run |
| Rule ID | Pending live run |
| Category and effort | Pending live run |
| Proposed remediation source | Pending: human, Developer Lightspeed, or custom rule |
| Human decision | Pending |

## Finding Selection

Choose a finding that is narrow enough for review:

- related to a single class, dependency, API, or configuration pattern;
- backed by a clear MTA rule and source location;
- reviewable with tests, reference behavior, or documented runtime assumptions;
- not a broad Java EE to Quarkus rewrite.

Good first candidates from the candidate assessment:

- audit-library migration findings;
- local system-scoped dependency review;
- missing OpenShift profile or deployment readiness;
- characterization-test need around a deterministic utility class.

## Review Gate

Do not request or accept a Developer Lightspeed suggestion until the selected finding has:

- source commit;
- MTA version and command or UI path;
- source and target technology values;
- rule ID and description;
- affected file and line;
- expected behavior or test strategy;
- human reviewer.

## Output

After a live run, produce a short modernization evidence note with:

- the analysis inputs;
- top findings summary;
- selected finding;
- Developer Lightspeed request and response link or summary;
- accepted, edited, or rejected decision;
- test or reference behavior used for review;
- follow-up rule or standards work.
