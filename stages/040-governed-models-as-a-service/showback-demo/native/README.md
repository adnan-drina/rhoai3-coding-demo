# RHOAI 3.5.1 native showback preparation

This package binds the Loki and external-metering candidates to **installed
RHOAI 3.5.1 schemas and image source revisions**, rather than upstream main.
It enables neither feature. The renderer emits only two inert ConfigMaps
containing review data. There is no default Kustomization, activation command,
hook or workload, and no native controller consumes these ConfigMap names.

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
| Metering backend | Shipped HTTP contract and linked development source reviewed; no accessible immutable backend image verified | No backend deployed |

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

[backend-decision.json](backend-decision.json) records pinned reference source,
API/build prerequisites, alternatives and remaining image evidence. The
installed CSV has no identified metering-backend operand, and the shipped
example calls its linked service a development/testing backend. Registry
inspection of the referenced GHCR images and proposed PriceTag Quay image
returned authorization/denial errors: **unverified access, not proof of absence**.
An accessible approved image or a built/published pinned reference remains a
real prerequisite to a deployable backend. No image digest or Red Hat product
status is invented, and no replacement billing server is written.

Example backend prices and dollar views are not our accepted service contracts.
Keep the shell accountant as the local policy result and reconcile native and
provider amounts against it; do not count both as separate expenditure.

## Offline review

From this directory:

~~~bash
bash render-integration.sh
bash render-integration.sh --check manifests
bash test-native.sh
~~~

The renderer validates checked-in schema/artifact evidence by default.
--write DIRECTORY refreshes one inert ConfigMap per file. Optional
--schema-dir DIRECTORY --artifact-pins FILE checks another retained evidence
set using the same contract as evidence/artifacts.json. Checks are targeted
schema/metadata validation, not full admission/CEL or runtime certification.
Successful checks retain live_qualified=false and the backend image gap.

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
Schema/image/configuration inspection completed read-only. Loki operation,
metering delivery and inference were not validated live. GPU/model replicas
remained zero; no resource was deployed, changed or started.
