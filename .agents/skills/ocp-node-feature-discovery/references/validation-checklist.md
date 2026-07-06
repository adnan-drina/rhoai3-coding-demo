# Validation Checklist

Use this checklist when reviewing NFD documentation, GitOps manifests, or live
operations.

## Source And Baseline

- The task references the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
- The NFD behavior is traced to the official Specialized hardware and driver
  enablement documentation.
- Driver Toolkit and Kernel Module Management details are not mixed into this
  skill unless separate official-source skills are created.

## Manifest Review

- NFD Operator installation, namespace, subscription, and catalog choices are
  verified against the active cluster and official docs.
- GitOps layout is curated locally; no committed Kustomize resource points
  directly to `github.com/redhat-cop/gitops-catalog`.
- `NodeFeatureDiscovery` manifests use official API versions and fields.
- If `NodeFeatureDiscovery` is created manually by CLI, web console, or GitOps,
  `operand.image` is set explicitly from a verified source.
- `core.sources`, `core.sleepInterval`, `core.labelWhiteList`, and
  `core.noPublish` choices are intentional and documented.
- `core.noPublish` is not left enabled for real label publishing unless dry-run
  behavior is intentional.
- PCI, USB, kernel, CPU, and custom feature-source settings are limited to
  documented fields or fields verified from the active CRD.
- `NodeFeatureRule` labels use project-owned names and do not clash with
  Kubernetes, OpenShift, NFD, NVIDIA, or RHOAI labels.
- Any `NodeFeatureRule` taints are explicitly justified and paired with
  workload tolerations or scheduling documentation.
- Topology Updater is enabled only when topology-aware placement is required.
- `NodeResourceTopology` usage accounts for its documented
  `topology.node.k8s.io/v1alpha1` API version.
- For the NVIDIA-only demo path, the NFD overlay is reviewed against
  `references/gitops-catalog-nfd-pattern.md`; PCI class whitelist, vendor label
  publication, and topology updater posture are intentional.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get csv -A | grep -i feature
oc get subscription -A | grep -i feature
oc get subscription -n openshift-nfd nfd -o yaml
oc get nodefeaturediscovery -A
oc get nodefeaturerule -A
oc get noderesourcetopology -A
oc get pods -A | grep -i nfd
oc get nodes --show-labels
oc describe node <node-name>
```

For schema verification:

```bash
oc explain nodefeaturediscovery.spec
oc explain nodefeaturerule.spec
oc get crd | grep -E 'nodefeature|noderesourcetopology'
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, `NodeFeatureDiscovery` changes, `NodeFeatureRule`
  label or taint changes, and topology updater enablement have explicit user
  approval when run against a live environment.
- Scheduling effects are reviewed with `ocp-nodes` before labels or taints are
  consumed by workloads.
- GPU-specific readiness is handed off to `rhoai-nvidia-gpu-accelerators`.

## Fail Conditions

Stop and ask for verification if:

- the documentation version does not match `docs/PLATFORM_BASELINE.md`
- a manifest includes unverified NFD fields or guessed labels
- `operand.image` is missing from a manually created `NodeFeatureDiscovery`
  resource
- `NodeFeatureRule` adds taints without documented scheduling impact
- a task expects NFD to expose `nvidia.com/gpu` resource capacity by itself
