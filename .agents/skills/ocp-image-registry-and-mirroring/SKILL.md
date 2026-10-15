---
name: ocp-image-registry-and-mirroring
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing how this repo uses the OpenShift internal image
  registry and image sources: the partial imageregistry Config that sets
  defaultRoute in Stage 010 rhoai-platform, the Stage 050 oci-export pusher
  ServiceAccount and registry Secret, the Stage 070 deploy.sh registry
  precondition, internal-registry image references and ImageStreams, pinned
  registry.redhat.io digests, or a question about mirroring and disconnected
  installs. Do NOT use for BuildConfig builds (use ocp-cicd-builds), Tekton
  image builds (use ocp-pipelines-cicd), or model images on GPU nodes (use
  rhoai-model-deployment).
---

# Image registry and mirroring

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed records:
`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md`
and `gitops/stages/050-model-evaluation/050-oci-export/README.md`.

## When to use

- A change touches `image-registry-default-route.yaml`, `050-oci-export/`, an
  ImageStream, or an image reference to the internal registry.
- A build or push to `image-registry.openshift-image-registry.svc:5000` fails.
- Someone proposes mirroring, an `ImageDigestMirrorSet` or a disconnected install.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The internal registry, its storage and Managed state belong to the provisioned cluster, not to Git | `docs/OPERATIONS.md` (environment baseline) | [Image Registry Operator][operator] |
| Only `spec.defaultRoute: true` is declared, as a partial Config with `Prune=false,Delete=false`; the operator owns the rest | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/image-registry-default-route.yaml` | [Exposing the registry][expose] |
| Stage 050 exports evaluation results to ImageStream `evaluated-models/evaluation-results` through the default route; pusher SA `evalhub-oci-pusher` bound to `system:image-builder`; a Sync hook composes the `kubernetes.io/dockerconfigjson` Secret `evalhub-oci-registry` | `gitops/stages/050-model-evaluation/050-oci-export/oci-export.yaml` | [Accessing the registry][access] |
| Stage 070 refuses to deploy unless the registry is Managed, Available and has persistent (not emptyDir) storage | `stages/070-advanced-app-platform/deploy.sh` | [Setting up and configuring the registry][setup] |
| Application images are built into the internal registry of their project and deployed by `@sha256:` digest; no external-registry fallback | `gitops/stages/070-advanced-app-platform/070-pipelines/project-pipeline/imagestream.yaml` | [Managing image streams][imagestreams] |
| Agent runtime images live in ImageStreams with `referencePolicy: Local`; pulls are granted per stream on `imagestreams/layers` | `gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime/images/` | [Using image streams with Kubernetes resources][is-k8s] |
| Red Hat images are pinned by tag or digest; `ose-cli` by digest because it publishes no `latest` | Stage 070 manifests, `docs/TROUBLESHOOTING.md#stage-070-jobs-cannot-pull-ose-cli-after-a-restart` | [Using images][using] |
| No mirroring: connected cluster, no `ImageDigestMirrorSet`, `ImageTagMirrorSet` or oc-mirror in Git | none | [About disconnected environments][disconnected] |

## Procedure

1. Declare only the fields the repo needs on operator-owned config objects,
   with `Prune=false,Delete=false`.
2. Keep credentials out of Git: registry Secrets are composed in cluster by
   hooks from ServiceAccount tokens.
3. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get configs.imageregistry.operator.openshift.io cluster -o jsonpath='{.spec.managementState} {.spec.defaultRoute}{"\n"}'
   oc get clusteroperator image-registry
   oc get route default-route -n openshift-image-registry
   ./stages/050-model-evaluation/validate.sh
   ```

## Pitfalls

- The default route serves the ingress certificate; that is why Stage 050 uses
  it (the evaluation sidecar trusts only public roots). In-cluster clients use
  the service address and the service CA.
- `evalhub-oci-pusher-token` is long-lived; rotate by deleting it and
  re-syncing Stage 050.
- A Healthy Application does not prove later Jobs can pull their images; an
  invalid tag hides behind node image caches until a node is replaced.
- A Red Hat registry outage stalls project provisioning
  (`docs/TROUBLESHOOTING.md#red-hat-registry-outage-starves-scaffolded-project-provisioning`).
- Build refusals in Stage 070: `docs/TROUBLESHOOTING.md#stage-070-internal-registry-build-refuses`.

## Official documentation (OCP 4.22)

| Topic | Section |
|---|---|
| Registry | [Registry overview][overview], [Image Registry Operator][operator], [Setting up and configuring][setup], [Accessing the registry][access], [Exposing the registry][expose] |
| Images | [Managing image streams][imagestreams], [Image streams with Kubernetes resources][is-k8s], [Image configuration][image-config], [Using images][using] |
| Mirroring | [About disconnected environments][disconnected], [Mirroring images for a disconnected installation][mirroring] |

## Related skills

`ocp-cicd-builds`, `ocp-pipelines-cicd`, `ocp-security-rbac-scc`, `rhoai-evaluation`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/registry/index#registry-overview
[operator]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/registry/index#configuring-registry-operator
[setup]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/registry/index#setting-up-and-configuring-the-registry
[access]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/registry/index#accessing-the-registry
[expose]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/registry/index#securing-exposing-registry
[imagestreams]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/images/index#managing-image-streams
[is-k8s]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/images/index#using-imagestreams-with-kube-resources
[image-config]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/images/index#image-configuration-classic
[using]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/images/index#using-images
[disconnected]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/disconnected_environments/index#about-disconnected-environments
[mirroring]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/disconnected_environments/index#installing-mirroring-disconnected
