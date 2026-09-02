# Observability (cards)

Paraphrased public API names. Prefer living Full-path from
`quarkusio/skills` `migrate-spring-to-quarkus` when present.

## Source

- Primary living map: quarkusio/skills (Apache-2.0)
- Pedagogical locus: Deandrea et al., *Quarkus for Spring Developers*, 2021,
  Ch. 6 "Building Applications for the Cloud", pp. 122–146 (cite only; not
  verbatim)
- **Harness:** factory provisions the Micrometer/Prometheus registry; GitOps
  owns manifest generation

## Cards

| id | Spring | Quarkus (SmallRye Health / Micrometer) | status | note |
|----|--------|----------------------------------------|--------|------|
| obs-health-iface | `HealthIndicator` interface, `health()` method | `HealthCheck` interface, `call()` method | ADOPT | Same conceptual shape; interface and method both rename |
| obs-health-register | `@Component` on the indicator bean | `@Liveness` **or** `@Readiness` on the check bean, plus an explicit CDI scope (`@ApplicationScoped`) | ADOPT | Quarkus forces a probe-type choice Spring does not |
| obs-health-response | `Health.up()…build()` | `HealthCheckResponse` via `.up()` / `.named(...)` | ADOPT | Builder shape carries over; type and entry point rename |
| obs-health-dep | One indicator kind regardless of what it touches | A check that queries a dependency (database, remote service) belongs on **`@Readiness`** | ADOPT | Liveness failure **restarts the pod**; readiness failure only removes traffic — miscategorising turns a slow dependency into a restart loop |
| obs-health-endpoint | Actuator probe paths (configurable) | **Fixed** `/q/health`, `/q/health/live`, `/q/health/ready` | ADOPT | Not user-configurable — do not carry over Actuator's path-configuration habit |
| obs-metrics | Actuator starter wiring Micrometer | Micrometer extension | ADOPT | Same underlying library; several extensions instrument automatically once included |
| obs-manifest | Manual manifest probe blocks, or a generator tool | Auto-generated probe blocks pointing at the fixed health paths | REJECT in-story | Platform/GitOps owns manifest generation in this harness — informational only, never a worker edit |
| obs-tracing | Tracing starter | OpenTelemetry extension | REJECT in-story | Not in current cart scope; do not add tracing dependencies opportunistically |

**REJECT:** hand-authored container-build or deployment configuration —
image build and manifest generation are factory/GitOps territory.

## Binding

1. **Choose the probe type deliberately.** Map each legacy indicator to
   Liveness or Readiness by asking what should happen when it fails: restart
   the process, or stop sending it traffic. Default to Readiness for anything
   that reaches outside the JVM.
2. **Do not reconfigure health paths.** The fixed `/q/health/*` paths are the
   contract; smoke checks and manifests both assume them.
3. **Stay inside the application boundary.** Metrics registry provisioning,
   probe manifest wiring, and image build are already owned by the platform —
   a story that edits them is out of scope, not thorough.
4. **Health endpoint responding is not health parity.** `/q/health` returning
   200 proves the extension is present, not that the legacy indicators were
   migrated. Assert each named check appears in the payload.

## Verification

`/q/health` returns 200 and its payload names **every** check migrated from a
legacy indicator; `/q/health/live` and `/q/health/ready` each resolve; a
dependency-backed check reports DOWN under readiness (not liveness) when its
dependency is stopped.

## Agent text

Map Spring Boot Actuator health to SmallRye Health: `HealthIndicator.health()`
becomes `HealthCheck.call()` on a CDI-scoped class annotated `@Liveness` or
`@Readiness` — pick by failure semantics, dependency checks go on Readiness.
Health paths are fixed at `/q/health*`; do not configure them. Metrics stay on
Micrometer. Manifests, probes wiring, and image build belong to the platform —
do not edit them from a story.
