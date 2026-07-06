# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Scope

OpenShift AI can be installed as self-managed software on an OpenShift cluster
on-premises or in a public cloud. This project uses the self-managed path on an
existing AWS-hosted OpenShift environment.

The official high-level installation tasks are:

1. Confirm cluster requirements.
2. Install the Red Hat OpenShift AI Operator.
3. Install OpenShift AI components.
4. Complete component-specific configuration.
5. Configure user and administrator groups.
6. Access the OpenShift AI dashboard.

## Platform Requirements

Before installing:

- A Red Hat OpenShift AI Self-Managed subscription is required.
- Cluster administrator access is required.
- The cluster must meet supported OpenShift version requirements for the active
  RHOAI baseline.
- The cluster must have a dynamically provisioned default storage class.
- An identity provider must be configured.
- Installation must use a user with `cluster-admin`; `kubeadmin` is not allowed.
- Internet access must allow required Red Hat registry/subscription domains.
- Open Data Hub must not already be installed.
- Object storage is required for single-model serving and AI pipelines, and is
  also useful for workbenches, Kueue workloads, and pipeline code.

The chapter lists OpenShift Container Platform 4.19 to 4.20 for the RHOAI 3.4
install page, and notes that Distributed Inference with llm-d requires 4.20 or
later. Always compare this with `docs/PLATFORM_BASELINE.md` before committing
GitOps.

## Component Requirements

Capture component prerequisites before enabling components in
`DataScienceCluster`:

| Component | Official prerequisite highlights |
|-----------|----------------------------------|
| `workbenches` | Custom workbench namespace must exist before installing the Operator |
| `aipipelines` | S3-compatible object storage access for pipeline artifacts; FIPS custom pipeline images must be UBI 9 or RHEL 9 based |
| `kueue`, `ray`, `trainingoperator` | Red Hat build of Kueue Operator and cert-manager Operator |
| `kserve` | cert-manager Operator |
| advanced `kserve` / llm-d | cert-manager, Red Hat Connectivity Link, Red Hat Leader Worker Set |
| `llamastackoperator` | Llama Stack Operator, Service Mesh Operator 3.x, cert-manager, GPU nodes, NFD, NVIDIA GPU Operator, object storage access |
| `modelregistry` | External MySQL database 5.x or later, 8.x recommended; S3-compatible object storage |

## Namespace Model

Default predefined namespaces:

- `redhat-ods-operator`: Red Hat OpenShift AI Operator.
- `redhat-ods-applications`: dashboard and required OpenShift AI components.
- `rhods-notebooks`: default basic workbench namespace.

Custom namespaces must be created before installing the Operator. Custom
application namespaces require the label:

```yaml
opendatahub.io/application-namespace: "true"
```

Do not rename OpenShift AI system namespaces because they are required for
OpenShift AI to function properly.

## Operator Installation Objects

The official CLI flow creates:

- `Namespace` for `redhat-ods-operator` or a custom operator namespace.
- `OperatorGroup` named `rhods-operator` in the operator namespace.
- `Subscription` named `rhods-operator` in the operator namespace.

The Subscription fields shown by the chapter:

- `spec.name: rhods-operator`
- `spec.channel: <channel>`
- `spec.source: redhat-operators`
- `spec.sourceNamespace: openshift-marketplace`
- optional `spec.startingCSV`

If `startingCSV` is omitted, the Subscription defaults to the latest operator
version in the selected channel. This project normally omits `startingCSV` to
install the latest available RHOAI in the verified channel.

## Component Installation Object

The official CLI flow creates a `DataScienceCluster` named `default-dsc` with:

```yaml
apiVersion: datasciencecluster.opendatahub.io/v2
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    <component>:
      managementState: Managed | Removed
```

`Managed` means the Operator manages, installs, keeps active, and safely
upgrades the component. `Removed` means the Operator manages but does not
install it, and tries to remove it if already installed.

If a component appears as `component-name: {}` in `spec.components`, it is not
installed.

## Verification Signals

Verify:

- the RHOAI Operator reaches `Succeeded`
- at least one running pod exists for each installed component in
  `redhat-ods-applications` or the custom applications namespace
- `DataScienceCluster/default-dsc` reaches `Phase: Ready`
- `status.installedComponents` shows `true` for installed components
- the dashboard About page lists installed OpenShift AI components and upstream
  component versions

The chapter notes that the dashboard might be reachable before all components
are ready.

## Unresolved Items

This chapter does not define:

- final demo component selection
- ArgoCD Application structure
- exact RHOAI channel policy beyond the Subscription `channel` field
- user/group RBAC configuration details
- component-specific post-install configuration

Use the relevant component skills and official docs before implementing those
areas.
