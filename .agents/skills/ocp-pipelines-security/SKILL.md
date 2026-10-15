---
name: ocp-pipelines-security
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing the security posture of this demo's Tekton
  builds: non-root Buildah in a pod user namespace with the nested-container
  SCC bound only to the image-builder ServiceAccount, Git and registry
  credentials passed through workspaces and projected tokens, TLS and token
  validation of the per-project GitLab EventListener, and the open Tekton
  Chains signing gap. Do NOT use for Trusted Artifact Signer installation
  (Stage 070 pipelines README, signing/), operator install (use
  ocp-pipelines-install-config), general SCC administration (use
  ocp-security-rbac-scc), or pipeline authoring (use ocp-pipelines-cicd).
---

# OpenShift Pipelines security in this repo

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Pipelines 1.24 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-pipelines/README.md` ("Image builds",
"Credentials", Alignment table).

## When to use

- A change touches the build Task, project ServiceAccounts or SCC bindings
  under `gitops/stages/070-advanced-app-platform/070-pipelines/`.
- Someone proposes `privileged`, `anyuid`, a pipeline-wide SCC, or image signing.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Buildah runs as UID 1000 in a pod user namespace (`hostUsers: false`) with OCP's default `nested-container` SCC, not the guide's CRI-O annotation or custom-SCC method | `070-pipelines/project-pipeline/task-build-image.yaml`, `070-pipelines/gitlab/reconcile.py` (`taskRunSpecs`) | [Non-root Buildah][nonroot] (method differs; see Alignment in the README) |
| `use` on `nested-container` only through ClusterRole `pipeline-userns-builder`, bound only to SA `image-builder`; the task refuses a non-mapped `uid_map` | `070-pipelines/operators/image-builder-scc.yaml`, `070-pipelines/project-pipeline/rbac-image-build-scc.yaml` | [Custom SCC and SA for runs][custom-scc] |
| Operator RBAC auto-creation off (`createRbacResource=false`), so no namespace gets `pipelines-scc-rolebinding` | `070-pipelines/build/tektonconfig-affinity.yaml` | see `ocp-pipelines-install-config` |
| Git credentials as a Secret workspace (`basic-auth` ← `gitlab-read-source`, read-only deploy token); registry login with the TaskRun's projected SA token | `070-pipelines/project-pipeline/task-git-clone.yaml`, `task-build-image.yaml` | [Secrets using workspaces][ws-secrets] |
| Webhook: Route `gitlab-webhook` edge TLS with redirect; `gitlab` interceptor checks the `gitlab-webhook` token before CEL filtering | `070-pipelines/gitlab/reconcile.py` | [Secure connection with routes][el-tls] |
| Pushes only to its own project's internal-registry path, full commit tag, digest returned; no external registry fallback | `070-pipelines/project-pipeline/task-build-image.yaml`, `registry-policy.yaml` | — (repo policy) |
| Tekton Chains signing not wired into `app-push` (Gap; TAS `Securesign` exists for later use) | `070-pipelines/signing/securesign.yaml`; `BACKLOG.md` | [Tekton Chains][chains], [Sign image and provenance][chains-sign] |

## Procedure

1. Keep the SCC binding per ServiceAccount; never bind an SCC to all project SAs.
2. Static and live checks:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static   # security-boundaries.test.py: builder SCC, cross-namespace reads
   ./stages/070-advanced-app-platform/validate.sh            # "Pipeline may push its own images", "... cannot push another project image"
   ```

3. Read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get rolebinding pipeline-userns-builder -n <project>-dev -o jsonpath='{.subjects}{"\n"}'
   oc get pod -n <project>-dev -l tekton.dev/pipelineTask=build-and-push \
     -o jsonpath='{.items[*].metadata.annotations.openshift\.io/scc}{"\n"}'
   ```

## Pitfalls

- The 1.24 guide's user-namespace methods use CRI-O annotations; the repo
  uses `hostUsers: false` plus `nested-container`. Do not "fix" the Task to
  the annotation form without qualifying it on OpenShift 4.22.
- Authentication or SCC errors in the build need installed-version
  qualification: `docs/TROUBLESHOOTING.md#stage-070-internal-registry-build-refuses`.
- Never add Quay or other external registry credentials to bypass a refusal.
- Enabling Chains also needs signing secrets ([cosign key pair][cosign]); the
  backlog item still names the old pipeline `app-platform-push` (now `app-push`).

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Supply chain | [Tekton Chains][chains], [Signing secrets][chains-secrets], [Sign image and provenance][chains-sign], [Cosign key in TektonConfig][cosign] |
| Pod security | [Security context for pods][scc], [Custom SCC and SA][custom-scc] |
| Non-root builds | [Non-root Buildah][nonroot], [User namespaces][userns], [Limitations][limits], [buildah-ns task][buildah-ns] |
| Webhooks and credentials | [Secure event listeners][el-sec], [Secure connection with routes][el-tls], [Repository secrets][repo-secrets], [Secrets using workspaces][ws-secrets] |

## Related skills

`ocp-pipelines-install-config`, `ocp-pipelines-cicd`, `ocp-security-rbac-scc`,
`ocp-image-registry-and-mirroring`.

[chains]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#using-tekton-chains-for-openshift-pipelines-supply-chain-security
[chains-secrets]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#signing-secrets-in-tekton-chains_using-tekton-chains-for-openshift-pipelines-supply-chain-security
[chains-sign]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#using-tekton-chains-to-sign-and-verify-image-and-provenance_using-tekton-chains-for-openshift-pipelines-supply-chain-security
[cosign]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-generating-cosign-key-pairs_customizing-configurations-in-the-tektonconfig-cr
[scc]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#configuring-security-context-for-pods
[custom-scc]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#op-running-pipeline-run-and-task-run-with-custom-scc-and-service-account_configuring-security-context-for-pods
[nonroot]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#unprivileged-building-of-container-images-using-buildah
[userns]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#nonroot-buildah-user-namespaces_unprivileged-building-of-container-images-using-buildah
[limits]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#limitations-of-unprivileged-builds_unprivileged-building-of-container-images-using-buildah
[buildah-ns]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#using-buildah-ns-tekton-task
[el-sec]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#securing-webhooks-with-event-listeners
[el-tls]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#op-providing-secure-connection_securing-webhooks-with-event-listeners
[repo-secrets]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#authenticating-pipelines-repos-using-secrets
[ws-secrets]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/securing_openshift_pipelines/index#providing-secrets-using-workspaces_authenticating-pipelines-repos-using-secrets
