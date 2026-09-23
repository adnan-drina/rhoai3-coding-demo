---
name: paved-road-m5
description: >
  Pin on M5-A/B/C delivery cards after a closed M4 result. Index for
  bounded delivery: eligibility-checked start, release-candidate prepare,
  app-push observation, deployed-app assertion, live Route acceptance,
  composed M5 verdict. Use for the assisted continuation that publishes
  through the existing pipeline. Never for M1–M4, never to dest-dispatch
  from the M4 worker, never to invent release gates or waive coverage.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+; oc/tkn for M5-B
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - paved-road
    - m5
    category: paved-road
    kind: guidance
---
# Paved road: M5 delivery (prepare → pipeline → live)

`steps.json` is the contract; `audit.json` is generated from it. Application
values (namespace, Route probes, CRUD body) live in the project's
`delivery.yaml`. This skill does not branch on a specimen name.

M4 close is not ship. Delivery is an assisted continuation with a **separate
budget**. The M4 terminator remains: never dest-dispatch M5 from that card.
Start or resume with:

```bash
python3 .hermes/skills/paved-road/paved-road-m5/scripts/start-m5-delivery.py --root . --exec
```

Repeated invocation reuses idempotency keys `m5:<stage>:<close_card>:<candidate16>`
and does not mint a second DAG or start a second PipelineRun.

## Cards (defined together)

| Card | Assignee | Parent | Runtime | Writes |
|------|----------|--------|---------|--------|
| M5-A prepare release candidate | implementer | closed M4 card | 1h / 1 retry | `verification/delivery/`, `k8s/` |
| M5-B execute CI/CD and verify deployment | implementer | M5-A | 3h / 1 retry | `verification/delivery/` |
| M5-C live acceptance and handover | implementer | M5-B | 1h / 1 retry | `verification/delivery/`, `evidence/verdicts/m5-verdict.json` |

Native reviewer checks A and C. Implementer terminator is `kanban_request_review reviewer=reviewer`.

## Procedure by card

**M5-A.** `python3 .hermes/skills/paved-road/paved-road-m5/scripts/prepare-release-candidate.py --root .`

Inspect current `git rev-parse HEAD` before reusing a reported identity. Bind
the closed M4 card, retained verdict, and original parity evidence (do not
overwrite M4 receipts). Record outstanding qualifications from
`release-blockers.json` / coverage account. An empty work list is not full
release eligibility. Do not silently waive gaps or add new gates. Prepare only
necessary build/deploy config (database and credential **references**). KEEP
`verification/delivery/candidate.json`.

**M5-B.** Publish through the repository workflow that already triggers
`app-push`. Then:

```bash
python3 .hermes/skills/paved-road/paved-road-m5/scripts/observe-app-push.py --root .
python3 .hermes/skills/paved-road/paved-road-m5/scripts/assert-deployed-app.py --root .
```

Record candidate → PipelineRun → image **digest** → deployed image → Route.
The digest is `IMAGE_DIGEST` on the build TaskRun (`status.results`); a
PipelineRun may succeed with empty `pipelineResults`. `assert-deployed-app.py`
reads the Deployment when allowed, otherwise ready app pods plus Route (the
implementer seat may be fenced from `deployments.apps`). Reuse a matching
successful run only when its revision and digest still apply. Do not `tkn
pipeline start` when that run exists. A green PipelineRun is not enough:
`deploy-app` can exit 0 with no Deployment. Refuse wrong revision, missing
digest, image mismatch, missing Service endpoints, or a non-HTTPS Route. OpenShift may leave
`spec.host` empty when `spec.subdomain` is set; use `status.ingress[].host`.
Hermes 0.20.5 `--initial-status` accepts only `blocked|running`; mint omits
`todo` so the board default applies. Edge Routes may return an `http://`
Location; rewrite it to `https://` before CRUD read/delete.

**M5-C.** Test the deployed Route, not workspace localhost:

```bash
python3 .hermes/skills/paved-road/paved-road-m5/scripts/live-acceptance.py --root .
python3 .hermes/skills/paved-road/paved-road-m5/scripts/compose-m5-verdict.py --root .
```

Swagger UI and OpenAPI must load and name application paths. Representative
reads and a disposable CRUD flow (create, read, delete its own row) must pass.
Auth and CORS must match the configured mode in `delivery.yaml` /
`decisions.yaml`. Do not change authentication to make tests pass. The composer
reports **deployment_status** separately from **verdict**; a reachable app with
outstanding qualifications is `INCONCLUSIVE` / `ship: false`, never a full
`ACCEPT`. KEEP `evidence/verdicts/m5-verdict.json`.

Reviewer: `python3 .../assert-paved-road-audit.py --root . --steps steps-prepare.json`
(or `steps-push.json` / `steps-accept.json`) over the official kanban log.

## Failures

Name the failed stage (M5-A / M5-B / M5-C), the exact condition, evidence,
owner, and the smallest bounded repair. Preserve failed attempts. After a
candidate SHA changes, revalidate pipeline, deployment, and live evidence;
do not reuse another revision's records. No identical retry, no new
monitoring agent, no parallel manual deploy path.
