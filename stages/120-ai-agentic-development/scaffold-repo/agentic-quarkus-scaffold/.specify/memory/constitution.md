# Coolstore Service Constitution

Non-negotiable principles for this service. Every `/speckit.*` command
consults this file; the plan's **Constitution Check must validate
against these articles by name** — a check that lists generic
principles instead is a failed check.

## I. The skills are law

`.opencode/skills/` is the corporate standard, binding in **every
phase** — specify, plan, tasks, and implement alike. Plans and data
models that contradict a skill are defects, not alternatives:
`quarkus-rest-conventions` (API shape, records, injection, errors,
money), `project-test-standards` (test style, mocking, assertions),
`spec-driven-workflow` (phase artifacts and completion rules),
`llm-integration` (MaaS wiring).

## II. Spec fidelity

Seed data, API paths, field names, **configuration property names**,
and thresholds stated in a spec are contracts, not examples. Never
round, substitute, or invent values. A spec-named config property is
the single override point — internal wiring (e.g. a REST client key)
maps to it, never replaces it.

## III. Response shapes are dedicated records

Never modify an existing record to add response fields — each distinct
response shape is its own projection record (see the skills). Existing
models are frozen unless the spec explicitly changes them.

## IV. Explicit dependencies

Every library the design relies on (runtime or test) is named with
exact coordinates in the plan's dependency list and added by an
explicit setup task. Test-scope libraries count: a framework named in
the plan's Testing section but absent from the dependency list fails
this article. "Or"-options in a plan are unresolved decisions —
resolve them before tasks.

## V. Simplicity (YAGNI)

Build only what the spec requires. Extra config classes, wrapper DTOs,
error taxonomies, abstraction layers, and pre-flight checks or health
probes of downstream services the spec does not demand are
complexity-tracking violations that need written justification. If the
spec says "degrade per request", failures are handled per request —
not predicted in advance.

## VI. Quality is an input

Tests are first-class tasks; the SonarQube gate fails on any new issue;
gate hygiene (no unused imports, no dead code, no field injection) is
part of "done", not cleanup for later.

## Governance

Any deviation from these articles must appear in the plan's Complexity
Tracking table with a justification — silent deviations are review
findings.
