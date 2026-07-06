# Official Doc Extraction

Use this extraction to keep RHADS-SSC customization content grounded in official
Red Hat sources. When implementation needs exact property names or script
behavior, verify against the forked `tssc-sample-templates` repository.

## Software Template Properties

The `properties` file in the `tssc-sample-templates` repo root controls default
values injected into all templates. Key properties:

| Property | Default | Purpose |
|----------|---------|---------|
| `GITHUB__DEFAULT__HOST` | `github.com` | On-premise GitHub FQDN |
| `GITLAB__DEFAULT__HOST` | `gitlab.com` | On-premise GitLab FQDN |
| `BITBUCKET__DEFAULT__HOST` | `bitbucket.org` | On-premise Bitbucket FQDN |
| `QUAY__DEFAULT__HOST` | `quay.io` | On-premise Quay FQDN |
| `GITHUB__DEFAULT__ORG` | (empty) | Default GitHub organization |
| `GITLAB__DEFAULT__ORG` | (empty) | Default GitLab organization |
| `QUAY__DEFAULT__ORG` | (empty) | Default Quay organization |
| `PIPELINE__REPO__URL` | `https://github.com/redhat-appstudio/tssc-sample-pipelines` | Forked pipelines repo |
| `PIPELINE__REPO__BRANCH` | `main` | Pipelines repo branch |
| `DEFAULT__DEPLOYMENT__NAMESPACE__PREFIX` | `tssc-app` | Deployment namespace prefix |
| `RHTAP__DEFAULT__NAMESPACE` | `tssc` | RHADS-SSC namespace |
| `ARGOCD__DEFAULT__NAMESPACE` | `tssc-gitops` | ArgoCD namespace |
| `ARGOCD__DEFAULT__INSTANCE` | `default` | ArgoCD instance |
| `ARGOCD__DEFAULT__PROJECT` | `default` | ArgoCD project |
| `GIT__SECRET__DEFAULT__KEY` | `password` | Git secret key name |
| `WEBHOOK__SECRET__DEFAULT__NAME` | `pipelines-secret` | Webhook secret name |
| `WEBHOOK__SECRET__DEFAULT__KEY` | `webhook.secret` | Webhook secret key |

After editing, run from the repository root:

```shell
./generate.sh
```

If `developerHub: namespacePrefixes` was modified during installation, update
`DEFAULT__DEPLOYMENT__NAMESPACE__PREFIX` to match.

## Sample Pipelines Repository Structure

| Directory | Purpose |
|-----------|---------|
| `gitops-repo` | Pipeline definitions for GitOps PR validation; triggers `gitops-pull-request` pipeline for promotion workflows |
| `pipelines` | Build and validation pipeline implementations referenced by event handlers |
| `source-repo` | Dockerfile-based secure builds; clones source, generates and signs `.sig`, `.att`, `.sbom` artifacts |
| `tasks` | Reusable Tekton tasks (ACS checks, custom integrations) |

## Customizing Pipeline as Code URLs

Prerequisites: forked and cloned `tssc-sample-pipelines` and
`tssc-sample-templates`.

```shell
./scripts/update-tekton-definition {fork_url} {branch_name}
```

Example:

```shell
./scripts/update-tekton-definition \
  https://github.com/myusername/tssc-sample-pipelines main
```

Review, commit, and push changes to the forked `tssc-sample-templates`.

## GitLab Pipeline Image Customization

Prerequisites: `podman` installed, Quay.io credentials, forked
`tssc-sample-templates` synced with upstream.

### Extract existing pipeline files

```shell
mkdir rebuild-image
less ../tssc-sample-templates/skeleton/ci/source-repo/gitlabci/.gitlab-ci.yml
# Copy the container image URL from the `image:` field
podman run -v $(pwd):/pwd:z <image_url> cp -r /work/tssc /pwd
```

Remove `:z` option if not on SELinux-enabled system (Fedora, RHEL, CentOS).

### Build and push custom image

Create a `Dockerfile`:

```dockerfile
FROM quay.io/redhat-tssc/task-runner:1.9

COPY ./tssc /work/tssc

RUN microdnf -y install make
```

Build and push:

```shell
podman build -f Dockerfile -t quay.io/<namespace>/<new_image_name> .
podman login quay.io
podman push quay.io/<namespace>/<new_image_name>
```

### Apply custom image

**Platform engineers** (all future components): update
`tssc-sample-templates/skeleton/ci/source-repo/gitlabci/.gitlab-ci.yml`:

```yaml
image: quay.io/<namespace>/<new_image_name>
```

**Developers** (single repository): update the source repo
`.gitlab-ci.yaml` directly.

## Jenkins External Cluster Configuration

When Jenkins runs outside the OCP cluster hosting RHADS-SSC, update
`REKOR_HOST` and `TUF_MIRROR` in two `env.sh` files:

- `skeleton/ci/gitops-template/jenkins/tssc/env.sh`
- `skeleton/ci/source-repo/jenkins/tssc/env.sh`

Default values:

```shell
REKOR_HOST=http://rekor-server.tssc-tas.svc
TUF_MIRROR=http://tuf.tssc-tas.svc
```

Replace `.svc` with the OCP cluster route. Retrieve correct routes:

```shell
oc get routes -n tssc-tas
```

These can also be configured as Jenkins environment variables or secrets.

## Image Registry Detection in RHDH

RHADS-SSC detects Quay and JFrog Artifactory registries by analyzing the image
URL for `quay`, `jfrog`, or `artifactory` substrings.

### Enable for an existing component

Add the annotation to `catalog-info.yaml` `metadata.annotations`:

For Quay:

```yaml
'quay.io/repository-slug': '<ORGANIZATION>/<REPOSITORY>'
```

For JFrog Artifactory:

```yaml
'jfrog-artifactory/image-name': '<IMAGE-NAME>'
```

### Enable for all future components

In the forked `tssc-sample-templates`, locate the detection logic in
`catalog-info.yaml` templates:

```yaml
{%- if "quay" in values.image %}
  quay.io/repository-slug: ${{ values.repoSlug }}
{%- elif "jfrog" in values.image or "artifactory" in values.image %}
  jfrog-artifactory/image-name: ${{ values.imageName }}
```

Replace `"quay"`, `"jfrog"`, or `"artifactory"` with the unique substring of
your custom registry URL.

## Template Import Methods

**Option A** — Use `generate.sh` then commit/push; templates auto-refresh in
RHDH.

**Option B** — Manual import:
- Single template: copy URL of `templates/<name>/template.yaml` from the fork.
- All templates: copy URL of `all.yaml` from the fork.
- In RHDH: select Analyze, then Import.

## Boundaries

- This extraction covers customization workflows only.
- RHADS-SSC installation and initial setup are not covered.
- SBOM inspection belongs in `rhads-sbom`.
- Conforma compliance and container signing belong in `rhads-compliance`.
