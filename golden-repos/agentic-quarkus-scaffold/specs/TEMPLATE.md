# Spec: <feature or service name>

## Goal

One paragraph: what this application/feature does and for whom.

## Behavior

Numbered, testable statements. Each becomes at least one test.

1. ...
2. ...

## API

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| GET | /api/... | — | ... | 404 when ... |

## Non-goals

What is explicitly out of scope for this spec.

## Acceptance

- `mvn -q test` passes with tests covering every Behavior statement.
- The platform pipeline (build + SonarQube gate) passes.
- README API table reflects the endpoints above.
