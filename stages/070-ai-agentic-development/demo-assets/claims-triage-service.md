# Spec: Claims triage service

## Goal

A small service that accepts incoming insurance claim summaries and triages
them into priority buckets so adjusters work the urgent ones first. Triage
uses the platform LLM (through MaaS) with a deterministic keyword fallback —
this demonstrates that the same governed gateway serving the developer's
coding assistant also serves the application's AI features.

## Behavior

1. `POST /api/claims/triage` accepts `{ "id": string, "summary": string }`
   and returns `{ "id", "priority", "reason", "source" }`.
2. `priority` is exactly one of `URGENT`, `STANDARD`, `LOW`.
3. Classification is LLM-first via the MaaS gateway (see the
   `llm-integration` skill); `source` is `llm` when the model classified,
   `fallback` when the keyword path did.
4. If the LLM call fails, times out, or returns anything outside the allowed
   priorities, the service falls back to keywords: summaries containing
   "injury", "fire", "flood", or "theft" are `URGENT`; containing "damage"
   or "accident" are `STANDARD`; otherwise `LOW`. A WARNING is logged.
5. `GET /api/claims/triage/stats` returns counts per priority and per
   source since startup (in-memory is fine).
6. Requests with a blank `summary` return 400 with an RFC-7807-style body.

## API

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | /api/claims/triage | `{id, summary}` | `{id, priority, reason, source}` | 400 blank summary |
| GET | /api/claims/triage/stats | — | `{URGENT: n, STANDARD: n, LOW: n, llm: n, fallback: n}` | — |

## Non-goals

Persistence, authentication, batch triage, and UI are out of scope.

## Acceptance

- `mvn -q test` passes; the fallback path is tested without a live LLM
  (tests must not require MaaS connectivity).
- The platform pipeline (build + SonarQube gate) passes.
- README API table reflects the endpoints above.
