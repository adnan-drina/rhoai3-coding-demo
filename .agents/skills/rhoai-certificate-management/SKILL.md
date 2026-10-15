---
name: rhoai-certificate-management
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing how OpenShift AI trusts certificates in this
  repo: DSCInitialization default-dsci spec.trustedCABundle (Managed, empty
  customCABundle), the odh-trusted-ca-bundle ConfigMap in project namespaces,
  the OpenShift service-CA ConfigMaps components use for in-cluster TLS
  (mlflow-service-ca, authorino-service-ca, pipeline-tasks-service-ca,
  candidate-model-service-ca), S3 or OGX CA trust, workbench restarts after a
  CA change, or x509 "unknown authority" errors between RHOAI components.
  Do NOT use for ingress or Gateway certificates (use ocp-ingress-gateway-routes),
  MaaS Gateway and Authorino TLS (use rhoai-maas-governance), Developer Hub
  Kubernetes-plugin TLS (use rhdh-configure), or PKI and cert-manager design
  (out of scope for this demo).
---

# RHOAI Certificate Management

Thin skill: this repo's trust decisions, with product behavior in the linked
OpenShift AI 3.5 "Work with certificates" chapter. Demo posture: self-signed
certificates and skipped TLS verification in scripts are accepted
(`.agents/rules/env.md`, Security Posture); do not add PKI or rotation tooling.

## When to use

- A component fails TLS to S3, MLflow, a model endpoint or the MaaS gateway.
- A change touches `trustedCABundle` in `rhoai-platform/dsc-init.yaml`.
- A new component needs to trust an in-cluster service.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `trustedCABundle.managementState: Managed` with an empty `customCABundle`; no custom CA is injected | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/dsc-init.yaml` | [Understanding certificates][understand]; [Custom CA bundle][custom] |
| Cluster-wide trust (proxy trusted CA) is the provisioner's, not changed by this repo | `docs/OPERATIONS.md` (Observed inventory: Proxy / trust) | [Cluster-wide CA bundle][cluster] |
| In-cluster TLS uses OpenShift service-CA ConfigMaps (`service.beta.openshift.io/inject-cabundle: "true"`) per component, not the custom bundle | `gitops/stages/050-model-evaluation/mlflow/service-ca.yaml` (MLflow `caBundleConfigMap`), `gitops/stages/040-governed-models-as-a-service/gateway-governance/governance/authorino-service-ca.yaml`, `gitops/stages/050-model-evaluation/model-qualification/pipeline-server.yaml`, `.../model-qualification/candidate-model-auth.yaml` | [Self-signed certificates with components][selfsigned] |
| S3 endpoint `https://s3.openshift-storage.svc:443` is signed by the service CA; no CA configuration is added for it (recorded gap) | `gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/README.md` (Alignment table, TLS row) | [S3 with self-signed certificates][s3] |
| KServe ingress gateway keeps its default certificate; DSC `kserve` sets no certificate secret | `gitops/stages/030-private-model-serving/private-model-serving/dsc-enablement/` | [Cluster CA bundle for model serving][serving] |
| Validate and deploy scripts call `oc` with `--insecure-skip-tls-verify=true` | `stages/010-openshift-ai-platform-foundation/validate.sh` | — (demo posture, `.agents/rules/env.md`) |

## Procedure

1. Decide where the trust belongs: an in-cluster service signed by the service
   CA gets a component service-CA ConfigMap (follow the MLflow pattern); an
   external private CA goes into `customCABundle` in `dsc-init.yaml`.
2. Change Git only; `010-rhoai-platform` self-heals the DSCI.
3. Deploy and validate the owning stage, for example
   `./stages/010-openshift-ai-platform-foundation/deploy.sh` then `validate.sh`.
4. Check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get dsci default-dsci -o jsonpath='{.spec.trustedCABundle.managementState}{"\n"}'
   oc get configmap odh-trusted-ca-bundle -n demo-sandbox -o jsonpath='{.data}' | head -c 300
   oc get configmap mlflow-service-ca -n redhat-ods-applications -o jsonpath='{.data}' | head -c 120
   ```

5. Restart running workbenches after a bundle change; new ones pick it up.

## Pitfalls

- `Removed` deletes `odh-trusted-ca-bundle` from existing namespaces; do not use
  it to "clean up" ([Remove the CA bundle][remove-all]).
- Reserved namespaces (`default`, `openshift-*`, `kube-*`) never get the bundle;
  a component there needs its own trust.
- Opting one namespace out uses the annotation
  `security.opendatahub.io/inject-trusted-ca-bundle=false` ([single namespace][remove-one]).
- OGX: the 3.5 chapter names `spec.server.tlsConfig.caBundle` in text and
  shows a different path in its example; run
  `oc explain ogxserver.spec --recursive | grep -i cabundle` before writing it.
- Pipelines: tasks trust the service CA through the ConfigMap in
  `model-qualification/pipeline-server.yaml`; the DSPA CA field is separate
  ([Certificate for pipelines][pipelines]).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter and model | [Work with certificates][chapter], [Understanding certificates][understand], [Adding certificates][adding] |
| Bundles | [Cluster-wide CA bundle][cluster], [Custom CA bundle][custom], [Without the Operator][unmanaged] |
| Components | [S3][s3], [Pipelines][pipelines], [Workbenches][workbenches], [Model serving][serving], [OGX CA bundle][ogx] |
| Removal | [Remove from all namespaces][remove-all], [Remove from one namespace][remove-one] |

## Related skills

`rhoai-dsci-dsc-configuration`, `rhoai-s3-object-storage-data`, `rhoai-mlflow`,
`rhoai-maas-governance`, `ocp-ingress-gateway-routes`, `rhoai-troubleshoot`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#working-with-certificates_certs
[understand]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#understanding-certificates_certs
[adding]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#adding_certificates
[cluster]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#adding-certificates-to-a-cluster-ca-bundle_certs
[custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#adding-certificates-to-a-custom-ca-bundle_certs
[selfsigned]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#using_self_signed_certificates_with_openshift_ai_components
[s3]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#accessing-s3-compatible-object-storage-with-self-signed-certificates_certs
[pipelines]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-a-certificate-for-pipelines_certs
[workbenches]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-a-certificate-for-workbenches_certs
[serving]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#using-the-cluster-CA-bundle-for-model-serving_certs
[ogx]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-a-ca-bundle-for-ogx_certs
[unmanaged]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#managing-certificates-without-the-operator_certs
[remove-all]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#removing-the-ca-bundle-from-all-namespaces_certs
[remove-one]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#removing-the-ca-bundle-from-a-single-namespace_certs
