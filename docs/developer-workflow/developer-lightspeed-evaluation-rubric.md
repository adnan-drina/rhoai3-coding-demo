# Developer Lightspeed Evaluation Rubric

## Purpose

Evaluate Red Hat Developer Lightspeed for MTA suggestions as reviewable modernization drafts grounded in MTA findings, source context, and previous migration examples.

Developer Lightspeed for MTA is Technology Preview in the reviewed MTA 8.1 documentation. Treat suggestions as AI-assisted drafts that require human review, tests, and source evidence before acceptance.

## Required Context

Before requesting a suggestion, record:

- source repository and commit;
- MTA version;
- source and target technologies;
- selected MTA rule ID;
- finding description;
- affected file and line;
- model provider path and data classification;
- whether Solution Server or Agent AI mode is being used;
- whether any custom rules contributed to the finding.

## Evaluation Table

Score each criterion from 0 to 2.

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| MTA finding alignment | Suggestion does not address the selected finding | Partially addresses finding | Directly addresses finding and rule intent |
| Source grounding | Ignores affected code | References affected file but misses behavior | Uses affected code and surrounding behavior correctly |
| Minimality | Broad rewrite | Some unrelated edits | Focused diff |
| Compatibility | Breaks target runtime or dependencies | Needs manual compatibility work | Matches selected target technology |
| Testability | No test path | Vague test idea | Clear test or reference validation |
| Dependency discipline | Adds or changes dependencies without justification | Justifies dependency but not source or support | Avoids new dependency or uses approved path |
| Human reviewability | Diff is too large or opaque | Reviewable with effort | Small, explained, and tied to evidence |
| Regression risk | High and unmitigated | Some mitigation | Clear rollback or rejection path |

Recommended acceptance threshold:

```text
14/16 or higher, with no zero in MTA finding alignment, source grounding, testability, or human reviewability.
```

## Decision States

Use one of these outcomes:

- `accept`: the suggestion is focused, validated, and reviewed;
- `edit`: the suggestion is useful but requires human changes before use;
- `reject`: the suggestion is unsupported, broad, unsafe, or not tied to the finding;
- `defer`: more tests, standards context, or runtime evidence is needed.

## Evidence Record

| Field | Value |
| --- | --- |
| MTA finding | Pending |
| Developer Lightspeed mode | Pending |
| Model provider path | Pending |
| Suggestion summary | Pending |
| Diff reviewed by | Pending |
| Rubric score | Pending |
| Decision | Pending |
| Validation command | Pending |
| Validation result | Pending |
| Residual risk | Pending |

## Review Questions

- Does the suggestion preserve existing behavior?
- Does it solve the selected MTA rule, or does it only silence the symptom?
- Does it introduce unapproved dependencies, runtime assumptions, or external services?
- Does it require a custom MTA rule or standards clarification before acceptance?
- Can the team explain the change without relying on the model response?
