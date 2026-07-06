# Official Grafana Operator Documentation

Use this reference before validating or changing Grafana Operator resources in
the rhoai3-demo GitOps tree.

## Official Sources

| Source | Role |
|--------|------|
| https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/ | Grafana documentation entry point for the Grafana Operator. Confirms the operator manages Grafana instances and resources as Kubernetes custom resources in Kubernetes or OpenShift. |
| https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/operator-dashboards-folders-datasources/ | Official examples for `Grafana`, `GrafanaDatasource`, and `GrafanaDashboard` resources. Confirms `instanceSelector`, datasource shape, dashboard `json`, and folder assignment patterns. |
| https://grafana.com/docs/grafana/latest/as-code/infrastructure-as-code/grafana-operator/manage-dashboards-argocd/ | Official Argo CD dashboard GitOps workflow. Confirms dashboard CRs can live in Git, Argo CD syncs the CRs, and the operator reconciles dashboard updates into Grafana. |
| https://grafana.github.io/grafana-operator/docs/installation/kustomize/ | Official Kustomize installation path. Confirms cluster-scoped and namespace-scoped Kustomize release artifacts and warns that `kubectl apply -f` can hit annotation-size errors where `kubectl create -f` is used in the docs. |
| https://grafana.github.io/grafana-operator/docs/api/ | Official Grafana Operator API reference. Use for `grafana.integreatly.org/v1beta1` fields and immutable-field behavior. |

## Authority Boundaries

- Official Grafana docs are authority for Grafana Operator resource behavior,
  CRD field names, and operator-managed Grafana resources.
- Official Grafana docs show Helm and Kustomize installation methods. The
  rhoai3-demo uses OpenShift OLM with `community-operators`; verify package,
  channel, CSV, install mode, and support posture from the active OpenShift
  catalog.
- The Red Hat CoP GitOps catalog remains only a layout and OpenShift pattern
  source. Do not treat it as Grafana API authority.
- OpenShift OAuth proxy, Route reencrypt TLS, service serving certificates,
  injected CA bundles, TokenReview, SubjectAccessReview, and
  `cluster-monitoring-view` RBAC are OpenShift-specific adaptations. Validate
  them with OCP docs and active cluster resources, not only Grafana docs.

## Official CR Model

The official API reference exposes `grafana.integreatly.org/v1beta1` resource
types including:

- `Grafana`
- `GrafanaDatasource`
- `GrafanaDashboard`
- `GrafanaFolder`
- alerting and notification resources
- `GrafanaServiceAccount`

For this demo, the active GitOps setup uses:

| Resource | Required official field checks |
|----------|--------------------------------|
| `Grafana` | `spec.route`, `spec.service`, `spec.serviceAccount`, `spec.deployment`, `spec.config`, and `spec.client` must exist in the installed CRD before use. |
| `GrafanaDatasource` | `spec.datasource` and `spec.instanceSelector` are required. `spec.uid`, `spec.valuesFrom`, `spec.resyncPeriod`, and `spec.allowCrossNamespaceImport` are optional fields to verify before use. Use `spec.valuesFrom` when a Secret or ConfigMap value must be substituted into a datasource field such as `secureJsonData.httpHeaderValue1`. |
| `GrafanaDashboard` | `spec.instanceSelector` is required. Dashboard content can come from `spec.json`, `spec.configMapRef`, `spec.grafanaCom`, `spec.url`, `spec.oci`, `spec.gzipJson`, or `spec.jsonnet`; verify the chosen source field before use. |

## Argo CD Dashboard GitOps Pattern

The official Argo CD guide establishes this flow:

1. Store dashboard CR YAML in Git.
2. Configure an Argo CD Application to sync the repository path.
3. Use automatic sync when desired, with prune and self-heal where appropriate.
4. Commit dashboard JSON changes to Git.
5. Argo CD updates the Kubernetes `GrafanaDashboard` custom resource.
6. The Grafana Operator syncs the custom resource into the selected Grafana
   instance.

For this repo:

- Use Kustomize through the stage Argo CD Application instead of the guide's
  plain directory-recursion example.
- Keep `SkipDryRunOnMissingResource=true` where the same Application may render
  CRs before CRDs are established.
- Use `instanceSelector.matchLabels` that matches the target `Grafana`
  resource labels.
- Prefer same-namespace dashboards and datasources. Use
  `allowCrossNamespaceImport` only when cross-namespace ownership is
  intentional and documented.

## Validated Stage 210 Mapping

Validated on the active demo cluster on 2026-06-12:

| Item | Evidence |
|------|----------|
| OLM package | `grafana-operator` is available from `community-operators` in `openshift-marketplace`. |
| Channel | Active channel `v5`; installed CSV `grafana-operator.v5.24.0` is `Succeeded`. |
| CRD versions | `grafanas`, `grafanadatasources`, and `grafanadashboards` serve and store `v1beta1`. |
| `Grafana` | `grafana/grafana` status condition `GrafanaReady=True`. |
| Datasource | `grafanadatasource/prometheus` status condition `DatasourceSynchronized=True`; `uid: Prometheus`; `instanceSelector.matchLabels.instance: rhoai-demo-grafana`; `valuesFrom` substitutes the `grafana-auth-secret` service-account token into `secureJsonData.httpHeaderValue1`; `resyncPeriod: 30s` keeps live demos responsive after Grafana pod replacement. |
| Dashboards | `vllm-model-serving-baseline` and `llm-performance` status condition `DashboardSynchronized=True`; both select `instance: rhoai-demo-grafana`, use `spec.json`, and set `resyncPeriod: 30s`. |
| Argo CD | `stage-210-model-serving-foundation` uses automated sync, prune, self-heal, Kustomize path `gitops/stage-210-model-serving-foundation`, and `SkipDryRunOnMissingResource=true`. |

## Required Validation Commands

Run these before claiming the Grafana setup is source-grounded:

```bash
oc get packagemanifest grafana-operator -n openshift-marketplace \
  -o jsonpath='{.status.catalogSource}{" "}{.status.catalogSourceNamespace}{"\n"}{range .status.channels[*]}{.name}{"\n"}{end}'
oc get subscription grafana -n rhoai-demo-grafana \
  -o jsonpath='{.spec.name}{" "}{.spec.channel}{" "}{.spec.source}{" "}{.spec.sourceNamespace}{" "}{.spec.installPlanApproval}{"\n"}{.status.installedCSV}{"\n"}{.status.state}{"\n"}'
oc get crd grafanas.grafana.integreatly.org grafanadatasources.grafana.integreatly.org grafanadashboards.grafana.integreatly.org \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{range .spec.versions[*]}{.name}{":"}{.served}{":"}{.storage}{" "}{end}{"\n"}{end}'
oc explain grafana.spec --api-version=grafana.integreatly.org/v1beta1
oc explain grafanadatasource.spec --api-version=grafana.integreatly.org/v1beta1
oc explain grafanadashboard.spec --api-version=grafana.integreatly.org/v1beta1
oc get grafana grafana -n rhoai-demo-grafana -o jsonpath='{.status.conditions}'
oc get grafanadatasource prometheus -n rhoai-demo-grafana -o jsonpath='{.status.conditions}'
oc get grafanadashboard -n rhoai-demo-grafana -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditions}{"\n"}{end}'
```

Also render local GitOps before committing:

```bash
kustomize build gitops/stage-210-model-serving-foundation/grafana/aggregate/overlays/demo >/tmp/stage210-grafana.yaml
```

## Review Rules

- Do not invent `grafana.integreatly.org` fields. Check the API reference and
  active `oc explain`.
- Do not assume the Grafana docs' Helm or direct Kustomize install command is
  the desired OpenShift install path for this repo. The repo uses OLM through
  GitOps.
- Do not use `allowCrossNamespaceImport: true` unless a dashboard or datasource
  must select a Grafana instance outside its namespace.
- Do not store API tokens, bearer tokens, or session secrets in Git. If a
  service-account-token Secret is GitOps-managed, ignore generated `.data` and
  service-account UID drift in Argo CD.
- Do not claim dashboard synchronization from YAML alone; require
  `DashboardSynchronized=True`.
