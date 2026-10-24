---
name: ocp-cicd-builds
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing OpenShift BuildConfig builds in this repo: the
  Stage 060 binary Docker builds opencode-runtime and hermes-runtime-api in
  ai-agents (and the older opencode-runtime in openshell), their ImageStream
  outputs and image-pull Roles (started by the Stage 060 task scripts
  images/build-opencode.sh and images/build-hermes.sh); or when choosing between BuildConfig, Shipwright and
  Tekton for a new image build. Do NOT use for Tekton pipelines, buildah Tasks
  or Stage 070 project pipelines (use ocp-pipelines-cicd), for registry
  exposure and image streams in general (use ocp-image-registry-and-mirroring),
  or for workspace images (stages/070-advanced-app-platform/workspace-image/).
---

# OpenShift builds (BuildConfig)

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed record:
`gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime/README.md`
(section on `images/`, `hermes-images/`).

## When to use

- A change touches a `buildconfig.yaml` or `imagestream.yaml` under
  `gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime/`.
- A sandbox cannot pull the built image.
- A new in-cluster image build is proposed.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Agent runtime images are built in cluster with BuildConfig, `source.type: Binary`, `strategy.type: Docker`, `runPolicy: Serial`, one kept build each, 600 s deadline and bounded resources | `gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime/images/buildconfig.yaml`, `.../hermes-images/buildconfig.yaml` | [Binary (local) source][binary], [Build strategies][strategies] |
| Output to a versioned ImageStreamTag (`opencode-runtime:1.18.16`, `hermes-runtime-api:0.20.5-api`); the tag is an output handle, consumers pin the build digest | same files, `.../images/imagestream.yaml` | [Managing build output][output] |
| ImageStreams carry `Delete=false,Prune=false` so a sync never removes built images; `referencePolicy: Local` | `.../images/imagestream.yaml`, `.../hermes-images/imagestream.yaml` | [Managing image streams][imagestreams] |
| Sandbox ServiceAccount `openshell-sandbox` gets `get` on `imagestreams/layers` for one named stream only | `.../images/image-pull-role.yaml`, `.../images/image-pull-rolebinding.yaml` | [Using RBAC][rbac] |
| Builds are started by hand, not by triggers: check the Application is Synced at the expected revision, fetch the release asset, verify its SHA-256, `oc start-build --from-dir`, wait, and read back the output digest. `stages/060-agent-runtime-and-agentops/images/build-opencode.sh` and `build-hermes.sh` do exactly this from their build contexts `images/opencode/` and `images/hermes-api/` | — | [Basic build operations][basic-ops] |
| Application images in Stage 070 are built by Tekton into the internal registry, not by BuildConfig; Shipwright is not used | `gitops/stages/070-advanced-app-platform/070-pipelines/` | [CI/CD overview][cicd] |

Paths starting with `...` are under `gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime/`.

## Procedure

1. Change the build context under `stages/060-agent-runtime-and-agentops/images/`
   (Dockerfile and release inputs) and, for a new version, the BuildConfig output
   tag in Git; commit and push first.
2. Sync the `060-openshell-runtime` Application at that revision with
   `stages/060-agent-runtime-and-agentops/deploy.sh --component 060-openshell-runtime`
   (it has no automated sync), then run `images/build-opencode.sh` or
   `images/build-hermes.sh` (published revision in
   `RHOAI_STAGE060_EXPECTED_REVISION`), which starts the build and prints the
   immutable output reference.
3. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get buildconfig,imagestream -n ai-agents
   oc get builds -n ai-agents --sort-by=.metadata.creationTimestamp
   ./stages/060-agent-runtime-and-agentops/validate.sh
   ```

## Pitfalls

- A Binary build has no source to rebuild from: a re-sync or `oc start-build`
  without `--from-dir` does not reproduce the image.
- The tag can move; read back the build's `imageDigest` and require
  the ImageStreamTag to point at it. Pin consumers to the digest.
- Builds need the internal registry Managed with persistent storage (Stage 070
  `deploy.sh` checks this); see `ocp-image-registry-and-mirroring`.
- Build pods run under the cluster's build SCC rules; do not grant privileged
  SCCs to make a Docker build pass ([Securing builds by strategy][securing]).

## Official documentation (OCP 4.22)

| Topic | Section |
|---|---|
| Overview | [CI/CD overview][cicd], [Understanding BuildConfigs][buildconfigs] |
| Inputs and strategies | [Binary (local) source][binary], [Build strategies][strategies] |
| Output and operations | [Managing build output][output], [Basic build operations][basic-ops], [Troubleshooting builds][troubleshooting] |
| Security | [Securing builds by strategy][securing] |
| Image streams | [Managing image streams][imagestreams] |
| Shipwright (not used) | [Builds using Shipwright][shipwright] |

## Related skills

`ocp-image-registry-and-mirroring`, `ocp-pipelines-cicd`, `ocp-security-rbac-scc`,
`ocp-gitops-operator`.

[cicd]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/cicd_overview/index#ci-cd-overview
[buildconfigs]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#understanding-buildconfigs
[binary]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#builds-binary-source_creating-build-inputs
[strategies]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#build-strategies
[output]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#managing-build-output
[basic-ops]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#basic-build-operations
[securing]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#securing-builds-by-strategy
[troubleshooting]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_buildconfig/index#troubleshooting-builds_build-configuration
[imagestreams]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/images/index#managing-image-streams
[rbac]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/authentication_and_authorization/index#using-rbac
[shipwright]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/builds_using_shipwright/index#overview-openshift-builds
