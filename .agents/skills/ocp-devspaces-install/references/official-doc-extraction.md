# Official Doc Extraction

Use this extraction to keep OpenShift Dev Spaces installation content grounded
in official Red Hat sources. When implementation needs exact CR fields, verify
the active cluster schema with `oc explain checluster.spec` or
`oc get crd checlusters.org.eclipse.che -o yaml` before authoring GitOps
manifests.

## Installation Overview

OpenShift Dev Spaces deploys on OpenShift as an Operator that manages a
gateway, dashboard, server, and plug-in registry. The Operator manages the full
lifecycle of all server components. You deploy OpenShift Dev Spaces by
installing the Operator and creating a `CheCluster` custom resource.

Only one instance of OpenShift Dev Spaces can be deployed per cluster.

### Installation Methods

| Method | Description |
|--------|-------------|
| `dsc` CLI | Install and manage from the command line with full control over configuration options during deployment |
| OpenShift web console | Install from OperatorHub and create a `CheCluster` instance through the web console using the standard Operator workflow |

### Deployment Scenarios

| Scenario | Description |
|----------|-------------|
| Standard | Deploy on an OpenShift cluster with internet access; both CLI and web console methods available |
| Restricted environment | Deploy on an air-gapped or disconnected cluster; requires mirroring container images to a private registry |
| External identity provider | Deploy with Keycloak as external OIDC identity provider instead of default OpenShift OAuth |

## Prerequisites and Requirements

### Supported Platforms

OpenShift Dev Spaces 3.28 runs on OpenShift 4.16–4.22 on the following CPU
architectures:

- AMD64 and Intel 64 (`x86_64`)
- IBM Z (`s390x`)
- IBM Power (`ppc64le`)
- ARMv8 (`arm64`)

### Resource Requirements

OpenShift Dev Spaces Operator, Operands, and Dev Workspace Controller
defaults:

| Component | Pod | Memory limit | Memory request | CPU limit | CPU request |
|-----------|-----|-------------|---------------|----------|------------|
| Operator | `devspaces-operator` | 256 MiB | 64 MiB | 500 m | 100 m |
| Server | `devspaces` | 1 GiB | 512 MiB | 1000 m | 100 m |
| Dashboard | `devspaces-dashboard` | 256 MiB | 32 MiB | 500 m | 100 m |
| Gateway (traefik) | `devspaces-gateway` | 4 GiB | 128 MiB | 1000 m | 100 m |
| Gateway (configbump) | `devspaces-gateway` | 256 MiB | 64 MiB | 500 m | 50 m |
| Gateway (oauth-proxy) | `devspaces-gateway` | 512 MiB | 64 MiB | 500 m | 100 m |
| Gateway (kube-rbac-proxy) | `devspaces-gateway` | 512 MiB | 64 MiB | 500 m | 100 m |
| Plugin registry | `plugin-registry` | 256 MiB | 32 MiB | 500 m | 100 m |
| DW Controller | `devworkspace-controller-manager` | 5 GiB | 100 MiB | 3000 m | 250 m |
| DW Webhook Server | `devworkspace-webhook-server` | 300 MiB | 20 MiB | 200 m | 100 m |
| **Total** | | **12.3 GiB** | **1.1 GiB** | **8.2** | **1.1** |

Per-workspace resources depend on the devfile. Example with Code - OSS editor:

| Component | Memory limit | Memory request | CPU limit | CPU request |
|-----------|-------------|---------------|----------|------------|
| Developer tools | 6 GiB | 512 MiB | 4000 m | 1000 m |
| che-gateway | 256 MiB | 64 MiB | 500 m | 50 m |
| Code - OSS editor | 1024 MiB | 256 MiB | 500 m | 30 m |
| **Total** | **7.3 GiB** | **832 MiB** | **5000 m** | **1080 m** |

## dsc CLI Installation

Install `dsc`, the Red Hat OpenShift Dev Spaces CLI management tool:

1. Download the archive from
   https://developers.redhat.com/products/openshift-dev-spaces/download
2. Extract: `tar xvzf <archive>`
3. Add the extracted `/dsc/bin` subdirectory to `$PATH`

Verification:

```shell
dsc
```

### Key dsc Commands

| Command | Purpose |
|---------|---------|
| `dsc server:deploy --platform openshift` | Install Dev Spaces |
| `dsc server:deploy --che-operator-cr-patch-yaml=<file>` | Install with custom CheCluster patch |
| `dsc server:status` | Check instance status |
| `dsc server:delete` | Uninstall Dev Spaces |
| `dsc server:delete --delete-namespace` | Uninstall and remove namespace |
| `dsc server:delete --delete-all` | Uninstall including Dev Workspace Operator |
| `dsc dashboard:open` | Open the dashboard in a browser |

## RBAC Permissions

### CLI Installation Permissions (ClusterRole)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: devspaces-install-dsc
rules:
- apiGroups: ["org.eclipse.che"]
  resources: ["checlusters"]
  verbs: ["*"]
- apiGroups: ["project.openshift.io"]
  resources: ["projects"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list", "create"]
- apiGroups: [""]
  resources: ["pods", "configmaps"]
  verbs: ["get", "list"]
- apiGroups: ["route.openshift.io"]
  resources: ["routes"]
  verbs: ["get", "list"]
- apiGroups: ["operators.coreos.com"]
  resources: ["catalogsources", "subscriptions"]
  verbs: ["create", "get", "list", "watch"]
- apiGroups: ["operators.coreos.com"]
  resources: ["operatorgroups", "clusterserviceversions"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["operators.coreos.com"]
  resources: ["installplans"]
  verbs: ["patch", "get", "list", "watch"]
- apiGroups: ["packages.operators.coreos.com"]
  resources: ["packagemanifests"]
  verbs: ["get", "list"]
```

### Web Console Installation Permissions (ClusterRole)

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: devspaces-install-web-console
rules:
- apiGroups: ["org.eclipse.che"]
  resources: ["checlusters"]
  verbs: ["*"]
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list", "create"]
- apiGroups: ["project.openshift.io"]
  resources: ["projects"]
  verbs: ["get", "list", "create"]
- apiGroups: ["operators.coreos.com"]
  resources: ["subscriptions"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["operators.coreos.com"]
  resources: ["operatorgroups"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["operators.coreos.com"]
  resources: ["clusterserviceversions", "catalogsources", "installplans"]
  verbs: ["get", "list", "watch", "delete"]
- apiGroups: ["packages.operators.coreos.com"]
  resources: ["packagemanifests", "packagemanifests/icon"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["operator.openshift.io"]
  resources: ["cloudcredentials"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["config.openshift.io"]
  resources: ["infrastructures", "authentications"]
  verbs: ["get", "list", "watch"]
```

## CLI Installation

Prerequisites:

- OpenShift Container Platform 4.22 or later cluster
- Active `oc` session with administrative permissions
- `dsc` management tool installed

Procedure:

```shell
# Optional: remove a previous instance
dsc server:delete

# Install
dsc server:deploy --platform openshift
```

Verification:

```shell
dsc server:status
dsc dashboard:open
```

### ARM64 Post-Install Patch

On ARM64 (AArch64) clusters, override gateway sidecar images after install:

```shell
SUBSCRIPTION=$(oc get subscription -A \
  -o jsonpath='{.items[?(@.spec.name=="devspaces")]}')

SUBSCRIPTION_NAME=$(echo "$SUBSCRIPTION" | jq -r '.metadata.name')
SUBSCRIPTION_NAMESPACE=$(echo "$SUBSCRIPTION" | jq -r '.metadata.namespace')

oc patch subscription "$SUBSCRIPTION_NAME" \
  -n "$SUBSCRIPTION_NAMESPACE" \
  --type=merge \
  -p '{
    "spec": {
      "config": {
        "env": [
          {
            "name": "RELATED_IMAGE_gateway_authentication_sidecar",
            "value": "quay.io/openshift/origin-oauth-proxy:4.9"
          },
          {
            "name": "RELATED_IMAGE_gateway_authorization_sidecar",
            "value": "quay.io/openshift/origin-kube-rbac-proxy:4.9"
          }
        ]
      }
    }
  }'
```

## Web Console Installation

Prerequisites:

- OpenShift web console session as cluster administrator
- Active `oc` session with administrative permissions
- For repeat install: previous instance uninstalled

Procedure:

1. Navigate to Operators > OperatorHub and search for "Red Hat OpenShift Dev
   Spaces".
2. Install the Operator.
3. Create the `openshift-devspaces` namespace:
   ```shell
   oc create namespace openshift-devspaces
   ```
4. Go to Operators > Installed Operators > Red Hat OpenShift Dev Spaces
   instance Specification > Create CheCluster > YAML view.
5. Replace `namespace: openshift-operators` with
   `namespace: openshift-devspaces`.
6. Click Create.

Important notes:

- The Dev Spaces Operator depends on the Dev Workspace Operator. If installing
  to a non-default namespace, ensure both are in the same namespace.
- If using Web Terminal Operator, install it in the same namespace as the Dev
  Spaces Operator (both depend on the Dev Workspace Operator).

Verification:

1. In Red Hat OpenShift Dev Spaces instance Specification > devspaces > Details
   tab, check that Message shows "None".
2. Wait for the Red Hat OpenShift Dev Spaces URL to appear.
3. Check the Resources tab for deployment status.

## Restricted Environment Installation

Deploy on an air-gapped OpenShift cluster by mirroring images and Operator
catalogs to a private registry.

Prerequisites:

- OpenShift cluster with at least 64 GB disk space
- Cluster ready for restricted network operation
- Active `oc` session with administrative permissions
- Active `oc registry` session to `registry.redhat.io`
- `opm` installed
- `jq` installed
- `podman` installed
- `skopeo` version 1.6+ installed
- Active `skopeo` session with admin access to private Docker registry
- `dsc` for Dev Spaces 3.28 installed

Procedure:

1. Mirror images with the mirroring script:

```shell
bash prepare-restricted-environment.sh \
  --devworkspace_operator_index registry.redhat.io/redhat/redhat-operator-index:v4.22 \
  --devworkspace_operator_version "v0.41.0" \
  --prod_operator_index "registry.redhat.io/redhat/redhat-operator-index:v4.22" \
  --prod_operator_package_name "devspaces" \
  --prod_operator_bundle_name "devspacesoperator" \
  --prod_operator_version "v3.28.0" \
  --my_registry "<my_registry>"
```

2. Install with the generated patch:

```shell
dsc server:deploy \
  --platform=openshift \
  --olm-channel stable \
  --catalog-source-name=devspaces-disconnected-install \
  --catalog-source-namespace=openshift-marketplace \
  --skip-devworkspace-operator \
  --che-operator-cr-patch-yaml=che-operator-cr-patch.yaml
```

3. Allow incoming traffic from the `openshift-devspaces` namespace to all pods
   in user projects via network policies.

## External Identity Provider (Keycloak)

Install Dev Spaces with Keycloak as external OIDC provider instead of default
OpenShift OAuth.

CheCluster patch for Keycloak integration:

```yaml
kind: CheCluster
apiVersion: org.eclipse.che/v2
spec:
  networking:
    auth:
      oAuthClientName: devspaces
      oAuthSecret: oauth-secret
      identityProviderURL: "<KEYCLOAK_URL>/realms/<REALM>"
      gateway:
        oAuthProxy:
          cookieExpireSeconds: 300
        deployment:
          containers:
            - name: oauth-proxy
              env:
                - name: OAUTH2_PROXY_CODE_CHALLENGE_METHOD
                  value: S256
                - name: OAUTH2_PROXY_BACKEND_LOGOUT_URL
                  value: "<KEYCLOAK_URL>/realms/<REALM>/protocol/openid-connect/logout?id_token_hint={id_token}"
  components:
    cheServer:
      extraProperties:
        CHE_OIDC_GROUPS__CLAIM: '<GROUPS_CLAIM>'
        CHE_OIDC_GROUPS__PREFIX: '<GROUPS_PREFIX>'
        CHE_OIDC_USERNAME__CLAIM: '<USERNAME_CLAIM>'
        CHE_OIDC_USERNAME__PREFIX: '<USERNAME_PREFIX>'
```

Key steps:

1. Create a `devspaces` client in Keycloak with Client authentication enabled.
2. Add `devspaces` to the audiences in OpenShift authentication config:
   ```shell
   oc patch authentication.config/cluster \
     --type='json' \
     -p='[{"op":"add","path":"/spec/oidcProviders/0/issuer/audiences/-","value":"devspaces"}]'
   ```
3. Wait for `kube-apiserver` Operator rollout.
4. Create `openshift-devspaces` project.
5. Create the OAuth client secret in the namespace.
6. Optional: Create ConfigMap with Keycloak CA certificate.
7. Deploy with `dsc server:deploy --che-operator-cr-patch-yaml che-patch.yaml`.
8. Update the `devspaces` Keycloak client with redirect URI and web origin.

## CheCluster CR Patching During Install

Configure the CheCluster CR at install time by providing a patch file:

```yaml
spec:
  <component>:
    <property_to_configure>: <value>
```

Deploy with patch:

```shell
dsc server:deploy \
  --che-operator-cr-patch-yaml=che-operator-cr-patch.yaml \
  --platform openshift
```

Verify configured properties:

```shell
oc get configmap che -o jsonpath='{.data.<configured_property>}' \
  -n openshift-devspaces
```

## Scalability Considerations

- Default etcd size is 2 GB; recommended maximum is 8 GB.
- Load testing showed ~2.5 GB etcd consumption for 6,000 DevWorkspace objects.
- Each user gets a namespace; for >10,000 users consider multi-cluster.
- Only one Dev Spaces instance per cluster.
- Disable Copied CSVs for large clusters:
  ```yaml
  apiVersion: operators.coreos.com/v1
  kind: OLMConfig
  metadata:
    name: cluster
  spec:
    features:
      disableCopiedCSVs: true
  ```
- Disable CA bundle mount for large deployments:
  ```yaml
  spec:
    devEnvironments:
      trustedCerts:
        disableWorkspaceCaBundleMount: true
  ```
- Configure DevWorkspace pruner for automatic cleanup:
  ```yaml
  apiVersion: controller.devfile.io/v1alpha1
  kind: DevWorkspaceOperatorConfig
  metadata:
    name: devworkspace-operator-config
    namespace: crw
  config:
    workspace:
      cleanupCronJob:
        enabled: true
        dryRun: false
        retainTime: 2592000
        schedule: "0 0 1 * *"
  ```

## Installation Verification

```shell
# Verify Operator pod is running
oc get pods -n openshift-devspaces \
  -l app.kubernetes.io/component=devspaces-operator

# Verify CheCluster status (expect "Active")
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.status.chePhase}'

# Retrieve dashboard URL
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.status.cheURL}'
```

The dashboard should load and display the Create Workspace page.

## Uninstallation

Remove Dev Spaces and all related user data:

```shell
# Remove the instance
dsc server:delete

# Optional: also remove the namespace
dsc server:delete --delete-namespace

# Optional: also remove the Dev Workspace Operator
dsc server:delete --delete-all
```

Verification:

```shell
# Expect "NotFound"
oc get namespace openshift-devspaces
```

Standard operating procedure for removing the Dev Workspace Operator manually
without `dsc` is available in the OpenShift Container Platform official
documentation.

## FQDN Retrieval

```shell
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.status.cheURL}'
```

Alternative: In the Administrator view of the OpenShift web console, navigate
to Operators > Installed Operators > Red Hat OpenShift Dev Spaces instance
Specification > devspaces > Red Hat OpenShift Dev Spaces URL.
