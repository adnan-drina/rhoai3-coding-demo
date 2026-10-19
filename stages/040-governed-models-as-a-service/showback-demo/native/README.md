# RHOAI 3.5.1 native showback preparation

This package binds the Loki and external-metering candidates to **installed
RHOAI 3.5.1 schemas and image source revisions**, rather than upstream main.
It enables neither feature. The renderer emits only two inert ConfigMaps
containing review data. Their canonical destination is
`gitops/stages/040-governed-models-as-a-service/040-showback-demo/native-inputs/`
(from the repository root), included by the optional manual-sync Application.
No native controller consumes these ConfigMap names. The Application provides
no native activation hook, LokiStack or metering workload; backend publication,
storage and shared MaaS/IPP field changes remain separately gated.

## Verified components

Guarded read-only inspection on 2026-10-16 confirmed RHOAI 3.5.1, installed
CRDs, image references and the existing IPP profile. Registry manifest/config
inspection bound images to source without downloading filesystem layers.
The earlier failed inspection was a network-sandbox access failure, not proof
of an invalid cluster login.

| Component | Verified contract | Deployment state |
|---|---|---|
| MaaS controller | Installed source 563117f178f04c8eac7058df481815a97694a88d; exported Config and tenant schemas | Existing component, unchanged |
| IPP | Installed source a98a2650e74f8b832ff75206f795cbb62b9cd688; both metering plugin types present | Existing processors; metering not enabled |
| AI Gateway operator | Installed source 2a490ec754c60d57794a19128c7038843e57ae24 | Existing component, unchanged |
| Loki Operator | Catalog stable-6.6, loki-operator.v6.6.1; image-bound application source 678e5e8f46311c6dd591e105117f4616a0cc82b1 | Selected candidate; operator/CRD not installed |
| Metering backend | Pinned Noyitz image built and tested locally; no published image or RHOAI integration qualified | Local test resources removed; no backend deployed |

[evidence/artifacts.json](evidence/artifacts.json) retains full index/architecture
digests, source origins, schema hashes and installed-versus-candidate status.
Loki's application source label differs from its dist-git/OCI revision; its
CRD is bound to the application source. These are artifact/schema facts, not
runtime acceptance.

Primary sources: shipped
[MaaS](https://github.com/red-hat-data-services/models-as-a-service/tree/563117f178f04c8eac7058df481815a97694a88d),
[IPP](https://github.com/red-hat-data-services/ai-gateway-payload-processing/tree/a98a2650e74f8b832ff75206f795cbb62b9cd688)
and [Loki CRD](https://github.com/openshift/loki/blob/678e5e8f46311c6dd591e105117f4616a0cc82b1/operator/bundle/openshift/manifests/loki.grafana.com_lokistacks.yaml).
[RHOAI 3.5 TP notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes)
cover Loki showback; the
[DP notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes)
cover external metering. They do not supply a backend image installation recipe
or establish that the separately described BBR webhook is this IPP contract.

## Correct Loki configuration

**Config/default.spec.usageLogging is an enable switch in the installed
3.5.1 build**, currently false. Its controller creates/removes owned usage
collector, proxy, dashboard/RBAC and gateway-filter resources with that switch.
It does not remove the separately owned LokiStack or stop its storage charges.
The old draft's collector-selector warning applied to newer upstream main,
not this release. Do not add telemetry.logs.captureUser: the installed
MaasTenantConfig has only telemetry metrics fields. The structured-log filter
emits identity attributes itself. Neither installed DSCI version has a
monitoring logging field; no DSCI logging patch belongs in this recipe.

The separate store is LokiStack/usage in redhat-ods-monitoring, matching the
shipped collector target:
https://usage-gateway-http.redhat-ods-monitoring.svc:8080/api/logs/v1/application/otlp.
The candidate uses v13, openshift-logging tenancy, source-backed OTLP mappings,
required storageClassName gp3-csi, and explicit limits.global.retention.days 30.
Omitted retention does not establish a 30-day policy. The 1x.demo size is a
demonstration choice, not a production availability or throughput claim.

Loki Operator uses openshift-operators-redhat, a global OperatorGroup,
redhat-operators and stable-6.6. Its selected 6.6.1 bundle targets OCP 4.22.
The full Cluster Logging/Vector collection stack is not required merely to use
MaaS's collector. See
[operator installation](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/install/install-the-loki-operator)
and [OTLP configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/configure/configure-lokistack-otlp).

Object storage remains a provision-time input. The candidate names
showback-native-loki-objectstorage but creates no bucket or credentials.
Static S3 Secret keys are bucketnames, endpoint, access_key_id and
access_key_secret, in the LokiStack namespace. For the existing NooBaa pattern,
map OBC ConfigMap BUCKET_NAME and BUCKET_HOST/BUCKET_PORT, plus Secret
AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY, to those values. Use an HTTPS endpoint
without a bucket path and forcepathstyle true; omit AWS region for NooBaa.
Do not put credentials in Git or command arguments. A storage CA ConfigMap is
referenced by spec.storage.tls.caName/caKey in the same namespace. Review store
ownership, endpoint/TLS, lifecycle and capacity before activation; 30-day logs
do not replace the separate 400-day evidence archive.
[Object storage preparation](https://docs.redhat.com/en/documentation/red_hat_openshift_logging/6.6/html/install/prepare-object-storage-for-lokistack).

## External metering and backend boundary

The installed profile is openshift-ingress/payload-processing-plugins, with
custom-ipp-config.yaml and custom-pre-processing-ipp-config.yaml keys.
The shipped MaaS controller deliberately annotates post-bootstrap plugin
ConfigMaps opendatahub.io/managed=false to preserve customization. Do not seed
that annotation before bootstrap or restore true unless resetting defaults is
intended. A later reviewed edit requires a controlled payload-processing
restart to reload. No edit/restart is performed here. The stale example's
upstreamBbr Helm key is not this installed customization interface.

The inert profile preserves the trusted header guard and existing request,
routing and credential plugins, plus the pre-processing profile. Full-body and
chunk response processors cannot share a response chain. For current
OpenAI-compatible paths, external-metering-streaming is the candidate for SSE
and non-streaming JSON. Do not enable both variants on one response or combine
it with full-body response translation; provider-format changes require
separate qualification.

The verified balance GET returns 200 with hasAccess, balance, usage and overage;
the event POST takes JSON CloudEvents and accepts 200 or 204. Exact paths are
in integration.json. The client has no bearer-auth configuration. Fail-open
controls backend failures, not whether a successful balance denial is enforced.
Concurrent admissions can overshoot; failed event delivery is not a durable
queue. Runtime reload, reconciliation and delivery have not been tested.

[backend-decision.json](backend-decision.json) now records the upstream backend
reference and image acquisition path, as well as the official-documentation
gap. The [example shipped with our IPP source](https://github.com/red-hat-data-services/ai-gateway-payload-processing/blob/a98a2650e74f8b832ff75206f795cbb62b9cd688/deploy/examples/external-metering/README.md)
names **OpenMeter or a compatible service** and explicitly links
**noyitz/ai-gateway-metering-service** for development testing. That repository,
pinned at f9a56b1769b0933e3fe7454a174b1f42a229f07a, is the reference candidate
for this demo's local evaluation. It is not a verified Red Hat backend operand.

Its deployment example names
ghcr.io/noyitz/ai-gateway-metering-service:latest, but no accessible digest or
image-publishing workflow was established. Registry authorization failures are
**unverified access, not proof of absence**. We completed a local source build
as the alternative: its Dockerfile produces a Linux amd64 binary and UBI 9 image.
The upstream Go 1.25 builder automatically downloads the Go 1.26 toolchain
required by go.mod. The successful build used a derived Containerfile with both
Linux amd64 base digests pinned and explicit Go 1.26.0. Bounded local API/database
checks passed, with billing limitations retained separately. See [the obtain/build procedure](../OPERATIONS.md#obtain-or-build-the-reference-backend-image)
and the local evidence below.

PriceTag preserves Noyitz's history in a separate development project with its
own build/release process; the installed IPP example still links Noyitz. Its intended Quay repository does
not establish a published version or digest. The locally built Noyitz image has
not been published, selected for cluster deployment or connected to MaaS.
OpenMeter likewise needs explicit API,
authentication, meter and entitlement qualification; an example link alone
does not prove a working integration with this installed plugin.

The 2026-10-18 official-documentation review covered the Developer Preview
notes, complete MaaS guide, installation/model-serving chapters and linked
companion instructions. It found no backend image or installation procedure.
The [MaaS guide's PostgreSQL setup](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service)
serves API-key lifecycle management; it is not the metering database recipe.
This documentation gap remains, but the upstream source investigation supplies
the development reference and build route. The local source-bound image has
runtime evidence; gateway integration and any registry publication remain
separate qualification steps.
No maintainer message was sent.

Example backend prices and dollar views are not our accepted service contracts.
Keep the shell accountant as the local policy result and reconcile native and
provider amounts against it; do not count both as separate expenditure.
The inspected backend sources substitute fallback prices for missing models
and apply a provider-independent cache subtraction that does not match all
Anthropic usage categories. Their cost totals cannot replace our unknown-price
and provider-category rules. Quota defaults and durable event export also need
explicit review before connecting the gateway.

## Local backend build and validation

The [original 2026-10-18 evidence](evidence/noyitz-local-20261018/README.md) records
unmodified Noyitz revision `f9a56b1769b0933e3fe7454a174b1f42a229f07a`, including
its replay, missing-usage and database-health failures. That historical record
is preserved unchanged.

The [local correction patch and build helper](backend/README.md) retain that
source pin and the original base/toolchain pins. Source-plus-ID uniqueness,
JSONB content comparison and a single ledger/rollup transaction suppress identical
replays, including concurrency and restart. Conflicting payloads return 409.
Successful events require explicit valid usage; native errors without usage remain
marked incomplete with NULL cost. The health endpoints query the primary database
and return 503 during an outage. Legacy duplicate history blocks migration rather
than being deleted; legacy completeness remains unknown. PostgreSQL 15+ is required
by the new index; PostgreSQL 16 is the local test target.

[test-backend-local.sh](test-backend-local.sh) requires an already running isolated
backend/database, an explicit local Podman connection and container names, a loopback
URL and an empty evidence directory. It binds the image to the exact patch SHA,
inserts synthetic events, restarts the backend and temporarily stops/starts the
named disposable database. Its exit trap attempts database recovery on failure.
It retains raw captures, its own source/hash, positive assertions and known limitations.
The patched Go tests also exercise actual database uniqueness, concurrent conflicts,
rollback/retry, legacy migrations and backfill behavior.

The [2026-10-19 correction evidence](evidence/noyitz-local-20261019/README.md) records
115 top-level Go tests (201 including subtests), 93 passing runtime checks and two
observed limitations, with no failed or skipped tests. All owned local test resources
were removed and the Podman VM restored to stopped. The first failed build is retained.

The original image and the corrected image remain distinct local artifacts.
Local image/config IDs and exported OCI manifest digests are not published registry
digests. Native activation remains false. These tests do not qualify IPP delivery,
model inference, financial completeness or an OpenShift deployment. The native
numeric dashboard still omits completeness; consult the raw flag and use the
fail-closed showback accountant for financial reports.

## Offline review

From this directory:

~~~bash
bash render-integration.sh
bash render-integration.sh --check ../../../../gitops/stages/040-governed-models-as-a-service/040-showback-demo/native-inputs
bash test-native.sh
~~~

The renderer validates checked-in schema/artifact evidence by default.
--write DIRECTORY refreshes one inert ConfigMap per file. Optional
--schema-dir DIRECTORY --artifact-pins FILE checks another retained evidence
set using the same contract as evidence/artifacts.json. Checks are targeted
schema/metadata validation, not full admission/CEL or runtime certification.
Successful checks retain live_qualified=false. They do not validate the separately
built local backend or establish a published backend image.

## Import captured native usage

The importer takes saved IPP CloudEvents JSONL, a capture manifest and an offer
input with an empty events array:

~~~bash
bash import-events.sh \
  --events /absolute/path/to/events.jsonl \
  --capture /absolute/path/to/capture.json \
  --offers /absolute/path/to/month-with-empty-events.json \
  --output /absolute/path/to/new-native-month.json
bash ../offers/service-report.sh \
  --input /absolute/path/to/new-native-month.json \
  --output /absolute/path/to/new-statement.json
~~~

Each input is snapshotted once; validation, hashes and calculation use those
same bytes. Capture binds the event hash and installed downstream source/image
contract, provider/model-to-agreement mapping, interval and independent
completion evidence. It does not manufacture those assertions. The examples
remain synthetic and do not provision their fixture identities.

- Identical source/ID replays collapse; conflicting copies fail. Unknown or
  ambiguous identity/model mappings are quarantined.
- Complete billing requires independently verified final usage/categories;
  streaming also requires completion. Missing events or token fields cannot
  establish zero usage or a complete month.
- OpenAI cache reads are subtracted from input; reasoning already included in
  output is not added twice. Anthropic input/cache categories remain separate.
  Cache writes need a confirmed pricing category; mixed durations are unsupported.
- Native event IDs are new UUIDs, not gateway request IDs. No automatic join to
  workload receipts or accepted-task evidence is claimed.
- Loki bodies are status/path; token/identity values are OTLP structured metadata.
  Missing/parsing-failed values can default to zero. No guessed Loki JSON-body
  billing parser is supplied.

Before later authorized activation, qualify object-store durability, consumer
isolation/admin access, trusted identity, streaming/provider categories,
loss/replay recovery, balance failures, invoice reconciliation and rendering.
Schema/image/configuration inspection completed read-only on 2026-10-16, when
GPU/model replicas were zero. A bounded metadata refresh on 2026-10-18 timed
out at the cluster guard before a resource read. Loki operation, metering
delivery and inference were not validated live. No OpenShift resource was deployed,
changed or started.
