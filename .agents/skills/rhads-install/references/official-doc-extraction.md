# Official Doc Extraction

Use this extraction to keep RHADS-SSC installation content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify
with `oc explain` or `oc get crd` before authoring GitOps manifests.

## Product Identity

Red Hat Advanced Developer Suite - software supply chain (RHADS-SSC) 1.9
installs "Red Hat Trusted Application Pipeline" on OpenShift. The `tssc` CLI
runs inside a container image and automates deployment and integration.

## Included Components

| Component | Purpose |
|-----------|---------|
| Red Hat Advanced Cluster Security (RHACS) | Artifact vulnerability scanning |
| Red Hat Developer Hub (RHDH) | Self-service developer portal |
| Conforma | Policy validation engine |
| OpenShift GitOps | Argo CD deployment management |
| OpenShift Pipelines | Tekton CI/CD automation |
| Red Hat Trusted Artifact Signer (RHTAS) | Artifact signing and verification |
| Red Hat Trusted Profile Analyzer (RHTPA) | SBOM analysis and security posture |
| Red Hat build of Keycloak | Identity and access management |

## Hardware Requirements

Minimum 3-node OpenShift Container Platform cluster:

| Role | Min CPU (cores) | Min RAM (GiB) | Rec. CPU (cores) | Rec. RAM (GiB) |
|------|-----------------|---------------|-------------------|-----------------|
| Control plane | 4 per node | 16 per node | 8 per node | 32 per node |
| Worker | 5 per node | 17 per node | 8 per node | 24 per node |

All components require a storage solution with a default storage class
capable of dynamic PV provisioning. Using Red Hat OpenShift Data Platform
requires a minimum of 6 nodes.

## Downloading The Installer

```shell
podman pull quay.io/redhat-tssc/cli:1.9.0
podman run -it --entrypoint bash --publish 8228:8228 --rm cli:1.9.0
```

Port 8228 is required for GitHub/GitLab App creation during integration.

## Creating config.yaml

Prerequisites: `cluster-admin` access, active `tssc` container session.

```shell
oc login https://api.<cluster-domain>:6443 \
  --username=cluster-admin --password=<your-password>
tssc config --create
```

This creates a `config.yaml` ConfigMap defining which components to deploy.
The default namespace is `tssc`; change with `--namespace` argument.

## Customizing config.yaml

### manageSubscription

- `true` (default): Installer manages and installs all Operator subscriptions.
- `false`: Installer skips subscription creation. Pre-existing Operators must
  have Update Approval set to Automatic.

### Product Toggles

Disable a product:

```yaml
- name: Advanced Cluster Security
  enabled: false
  namespace: tssc-acs
```

### IAM Provider

```yaml
- name: Developer Hub
  properties:
    authProvider: <github|gitlab>
```

### RBAC

```yaml
- name: Developer Hub
  properties:
    authProvider: <github|gitlab>
    RBAC:
      enabled: true
    # adminUsers:
    #   - <username>
    # orgs:
    #   - <github_org>
```

If `adminUsers` is omitted, defaults to the GitHub/GitLab credentials from
integration. The `orgs` list is only used with GitHub.

### Custom Software Catalog

```yaml
- name: Developer Hub
  properties:
    catalogURL: https://github.com/redhat-appstudio/tssc-sample-templates/blob/release-v1.9.x/all.yaml
```

### Namespace Prefixes

```yaml
- name: Developer Hub
  namespacePrefixes:
    - my_prefix1
    - my_prefix2
```

Each prefix generates: `<prefix>-app-ci`, `<prefix>-app-development`,
`<prefix>-app-stage`, `<prefix>-app-prod`.

## Service Integrations

### GitHub (PAT + GitHub App)

```shell
export GH_API_TOKEN=<api_token>
export GH_ORG_NAME="<github_org_name>"
export GH_APP_NAME="<github_app_name>"
tssc integration github-app \
  --create --token="$GH_API_TOKEN" --org="$GH_ORG_NAME" $GH_APP_NAME
```

A PAT is recommended but no longer strictly required for GitHub App
integration. Select "All repositories" when prompted.

### GitLab

```shell
tssc integration gitlab \
  --token="$GL_API_TOKEN" --host="$GL_URL" --group $GL_GROUP \
  --app-id $GL_APP_ID --app-secret $GL_APP_SECRET --insecure
```

### Quay (required — one registry must be integrated)

```shell
tssc integration quay \
  --dockerconfigjson='{"auths":{"quay.io":{"auth":"<write_token>","email":""}}}' \
  --dockerconfigjsonreadonly='{"auths":{"quay.io":{"auth":"<read_token>","email":""}}}' \
  --token="<quay_access_token>" --url="https://quay.io"
```

Requires two robot accounts: one with write, one with read permission.

### JFrog Artifactory

```shell
tssc integration artifactory \
  --url="$AF_URL" --dockerconfigjson='$AF_DOCKERCONFIGJSON' \
  --token="$AF_API_TOKEN"
```

### Sonatype Nexus

```shell
podman login --authfile="${AUTHFILE}" "${REGISTRY_URL}"
tssc integration nexus --url="${REGISTRY_URL}" \
  --dockerconfigjson="$(cat ${AUTHFILE})"
rm "${AUTHFILE}"
```

### RHACS (pre-existing instance)

```shell
tssc integration acs --endpoint="$ACS_ENDPOINT" --token="$ACS_TOKEN"
```

### RHTAS (pre-existing instance)

```shell
tssc integration trusted-artifact-signer \
  --rekor-url="$REKOR_URL" --tuf-url="$TUF_URL"
```

### RHTPA (pre-existing instance)

Two commands required:

```shell
tssc integration trustificationauth \
  --oidc-client-id="$OIDC_CLIENT_ID" \
  --oidc-client-secret="$OIDC_CLIENT_SECRET" \
  --oidc-issuer-url="$OIDC_ISSUER_URL"

tssc integration trustification \
  --bombastic-api-url="$BOMBASTIC_API_URL" \
  --supported-cyclonedx-version="$SUPPORTED_CYCLONEDX_VERSION"
```

### Bitbucket Cloud

Not officially supported/tested for RHADS-SSC 1.9. May work with app
password configuration.

```shell
tssc integration bitbucket \
  --username="$BB_USERNAME" --app-password="$BB_TOKEN" --host="$BB_URL"
```

### Jenkins

```shell
tssc integration jenkins \
  --token="$JK_API_TOKEN" --url="$JK_URL" --username="$JK_USERNAME"
```

### Azure Pipelines (Technology Preview)

```shell
tssc integration azure \
  --organization="$AZURE_ORGANIZATION" --host="$AZURE_HOST_URL" \
  --token="$AZURE_API_TOKEN"
```

### GitHub Actions

No additional configuration required. The GitHub App created during GitHub
integration enables GitHub Actions.

## CI Provider SLSA Levels

| Provider | SLSA Build Level |
|----------|------------------|
| Tekton | Level 3 |
| Jenkins, GitHub Actions, GitLab CI, Azure Pipelines | Level 2 |

## Deploying

```shell
tssc deploy
```

- Typical deployment takes ~1 hour.
- ACS checks can take up to 45 minutes and may timeout.
- Re-run `tssc deploy` on failure before contacting support.
- Running the installer multiple times is safe; manually changing product
  config between runs may cause unpredictable results.

Output includes Developer Hub URL, ACS dashboards, and component status. The
Developer Hub URL follows the pattern:

```
https://backstage-developer-hub-tssc-dh.apps.<cluster_name>.<base_domain>
```

## Upgrade Posture

The installer is not a package manager and does not support upgrades.
Upgrade components individually after initial deployment:

| Component | RHADS-SSC 1.9 target version | Upgrade method |
|-----------|------------------------------|----------------|
| RHDH | Operator 1.9 | Operator upgrade |
| RHACS | Operator 4.10 | Operator upgrade |
| RHTPA | 2.2 | Helm chart migration |
| RHTAS | Operator 2.2 | OLM upgrade |
| OpenShift Pipelines | Operator 1.21 | OLM upgrade |

## Credentials Reference

### RHACS

| Property | Value |
|----------|-------|
| Namespace | `tssc-acs` |
| Login | `admin` |
| Secret | `central-htpasswd` |
| Password | `oc -n tssc-acs get secret central-htpasswd -o go-template='{{index .data "password" \| base64decode}}'` |
| Endpoint | `https://central-tssc-acs.apps.<cluster>.<domain>` |

### OpenShift GitOps (Argo CD)

| Property | Value |
|----------|-------|
| Namespace | `tssc-gitops` |
| Login | `admin` |
| Admin secret | `tssc-gitops-cluster` |
| Admin password | `oc -n tssc-gitops get secret tssc-gitops-cluster -o go-template='{{index .data "admin.password" \| base64decode}}'` |
| Integration secret | `tssc-argocd-integration` |
| Endpoint | `https://tssc-gitops-server-tssc-gitops.apps.<cluster>.<domain>` |

### Red Hat build of Keycloak

| Property | Value |
|----------|-------|
| Namespace | `tssc-keycloak` |
| Login | `admin` |
| Secret | `keycloak-initial-admin` |
| Password | `oc -n tssc-keycloak get secret keycloak-initial-admin -o go-template='{{index .data "password" \| base64decode}}'` |
| Endpoint | `https://sso.apps.<cluster>.<domain>` |

### RHTAS

| Property | Value |
|----------|-------|
| Namespace | `tssc-tas` |
| Login | Via Keycloak realm `trusted-artifact-signer` |
| Secret | `trusted-artifact-signer-user` |
| Password | `oc -n tssc-tas get secret trusted-artifact-signer-user -o go-template='{{index .data "password" \| base64decode}}'` |
| Endpoint | `https://sso.apps.<cluster>.<domain>/realms/trusted-artifact-signer/account/` |

### RHTPA

| Property | Value |
|----------|-------|
| Namespace | `tssc-tpa` |
| Login | `admin` (chicken realm) |
| Secret | `tpa-realm-chicken-admin` |
| Password | `oc -n tssc-tpa get secret tpa-realm-chicken-admin -o go-template='{{index .data "password" \| base64decode}}'` |
| Bombastic API | `sbom-tssc-tpa.apps.<cluster>.<domain>` |
| Docs | `https://docs-tssc-tpa.apps.<cluster>.<domain>` |

### RHDH

| Property | Value |
|----------|-------|
| Namespace | `tssc-dh` |
| Login | `admin` |
| Secret | `oc get secrets -n tssc-dh \| grep admin` |
| Endpoint | `https://backstage-developer-hub-tssc-dh.apps.<cluster>.<domain>` |

## Default And Alternative Providers

| Category | Default | Supported alternatives |
|----------|---------|------------------------|
| Source code | GitHub | GitLab, Bitbucket Cloud |
| CI engine | Tekton | Jenkins, GitHub Actions, GitLab CI, Azure Pipelines (TP) |
| Registry | — (must integrate) | Quay, JFrog Artifactory, Sonatype Nexus |

Replacing default Git, CI, or registry providers installs corresponding RHDH
plugins, many of which are Technology Preview or community-maintained. Not
recommended for production.

## Important Notes

- RHADS-SSC does not install Quay by default; a registry integration is
  mandatory.
- The `--insecure` flag on GitLab integration skips TLS verification.
- Persistent storage with a default StorageClass is required for all
  components.
- When `manageSubscription: false`, pre-existing Operators must use Automatic
  Update Approval or installation may timeout.
- After pushing config changes, use `tssc config --create --force` then
  `tssc deploy` to re-apply.
