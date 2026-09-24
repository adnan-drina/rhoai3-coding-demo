---
name: paved-road-m5
description: >
  Pin on M5 PREFLIGHT, M5 DEPLOY, and M5 VALIDATE delivery cards after a
  closed M4 result. Index for bounded delivery: eligibility-checked start,
  release-candidate prepare, app-push observation, deployed-app assertion,
  live Route acceptance, composed M5 verdict. Use for the assisted
  continuation that publishes through the existing pipeline. Never for
  M1–M4, never to dest-dispatch from the M4 worker, never to invent
  release gates or waive coverage.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+; oc/tkn for M5 DEPLOY
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
# Paved road: M5 delivery (PREFLIGHT → DEPLOY → VALIDATE)

`steps.json` is the contract; `audit.json` is generated from it. Application
values (namespace, Route probes, swagger/openapi, CRUD body) live in the
project's `delivery.yaml`, filled from effective `quarkus.http.root-path`,
`quarkus.http.non-application-root-path`, Swagger/OpenAPI configuration, and
the measured application contract. Do not assume `/api`, `/q/health`,
`/q/swagger-ui`, or `/q/openapi`. This skill does not branch on a specimen name.

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
| M5 PREFLIGHT — release candidate | implementer | closed M4 card | 1h / 1 retry | `verification/delivery/`, `k8s/` |
| M5 DEPLOY — CI/CD and deployment | implementer | M5 PREFLIGHT | 3h / 1 retry | `verification/delivery/` |
| M5 VALIDATE — live acceptance and handover | implementer | M5 DEPLOY | 1h / 1 retry | `verification/delivery/`, `evidence/verdicts/m5-verdict.json` |

Native reviewer checks PREFLIGHT and VALIDATE. Implementer terminator is `kanban_request_review reviewer=reviewer`.

## Procedure by card

**M5 PREFLIGHT.** `python3 .hermes/skills/paved-road/paved-road-m5/scripts/prepare-release-candidate.py --root .`

Inspect current `git rev-parse HEAD` before reusing a reported identity. Bind
the closed M4 card, retained verdict, and original parity evidence (do not
overwrite M4 receipts). Record outstanding qualifications from
`release-blockers.json` / coverage account. M4 `ship: false` and its verdict
prose are historical context, not M5 release obligations. An empty work list
is not full release eligibility. Read the pinned G-1 kill-ratio result from
evidence; do not hardcode empty values or invent PASS. The pin must be the
output of `pin-kill-ratio-from-pit.py` after `--record-measurement` (XML digest
tied to the measured Git commit and `product_tree_sha256`; those identities
are not compared as strings. `--root` may resolve the expected delivery
commit but must not relabel an arbitrary `mutations.xml`). M5 consumption
requires that producer-written `pit-measurement.json` receipt and complete
candidate/tree/report bindings on both the receipt and the pin; missing
required fields are not PASS. An embedded digest string is not PASS. Do not decorate a pin after
measurement.
Conflicting candidate identities, non-integer or unordered counts (require
`0 <= killed <= attempted <= generated`), or stored evaluation that disagrees
with a recompute are not PASS. Historical coverage gaps close only through
`verification/delivery/coverage-discharge.json` that names the unique original
obligation identities recovered from preserved M4 evidence (verdict rows,
blocker `ids`, or the coverage snapshot bound to this M4 card — not a live
rewritten account, not another card's freeze, and not a count). The supporting `coverage-account.json` must bind this candidate.
Closed M4 bytes stay put. Do not silently waive gaps or add new gates. Prepare
only necessary build/deploy config (database
and credential **references**). KEEP `verification/delivery/candidate.json`.

**M5 DEPLOY.** Publish through the repository workflow that already triggers
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

**M5 VALIDATE.** Test the deployed Route, not workspace localhost:

```bash
python3 .hermes/skills/paved-road/paved-road-m5/scripts/live-acceptance.py --root .
python3 .hermes/skills/paved-road/paved-road-m5/scripts/compose-m5-verdict.py --root .
```

Swagger UI and OpenAPI must load and name application paths. Representative
reads and a disposable CRUD flow (create, read, delete its own row) must pass.
Auth and CORS must match the configured mode in `delivery.yaml` /
`decisions.yaml`. Do not change authentication to make tests pass. The composer
reports **deployment_status** separately from **verdict**. Full `ACCEPT` is the
existing release contract plus pinned kill-ratio PASS on this candidate, with
bound pipeline/deploy/live checks; it does **not** require M4 to have shipped.
A reachable app with genuine outstanding qualifications is `INCONCLUSIVE` /
`ship: false`. Duplicate coverage-account rows collapse to one; `not-shipped`
and `verdict-reason` are not re-opened. KEEP `evidence/verdicts/m5-verdict.json`
(prior copies archive under `verification/delivery/attempts/`).

Reviewer: `python3 .../assert-paved-road-audit.py --root . --steps steps-prepare.json`
(or `steps-push.json` / `steps-accept.json`) over the official kanban log.

## Failures

Name the failed stage (M5 PREFLIGHT / M5 DEPLOY / M5 VALIDATE), the exact
condition, evidence, owner, and the smallest bounded repair. Preserve failed
attempts. After a candidate SHA changes, revalidate pipeline, deployment, and
live evidence; do not reuse another revision's records. No identical retry, no
new monitoring agent, no parallel manual deploy path.

## Authoring validation

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔
audit.json sync, delivery step contracts, and the M5 delivery regression suite.
