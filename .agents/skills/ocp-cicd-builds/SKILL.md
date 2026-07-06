---
name: ocp-cicd-builds
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  CI/CD build guidance from official OCP documentation: CI/CD overview,
  OpenShift Builds, Builds using Shipwright, Builds using BuildConfig,
  BuildConfig, Build, BuildRequest, BuildLog, Docker, Source-to-Image, custom
  and pipeline build strategies, build inputs, outputs, triggers, hooks, logs,
  resources, duration limits, node assignment, chained builds, pruning,
  strategy RBAC, registry credentials, image streams, and subscription
  entitlement build secrets. Do NOT use for Tekton/OpenShift Pipelines,
  OpenShift GitOps/Argo CD, Jenkins, or live build execution without the env
  safety guard and explicit approval.
---

# OCP CI/CD Builds

Use this skill to ground OpenShift Container Platform CI/CD build guidance in
the official OCP CI/CD overview, Builds using Shipwright, and Builds using
BuildConfig documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the OpenShift build
surface. It does not replace future OpenShift Pipelines, OpenShift GitOps, or
Jenkins skills.

## Demo Build Posture

For this AWS-hosted RHOAI demo:

- Prefer GitOps-managed build definitions and explicit image provenance when
  active demo build workflows are introduced.
- Use Shipwright-based Builds for modern Kubernetes-native build workflows only
  after the separate Builds for Red Hat OpenShift documentation, installed
  Operator, and active CRDs are verified.
- Use `BuildConfig` only when a demo capability specifically needs classic
  OpenShift build behavior such as ImageStream triggers, S2I examples, or
  existing OpenShift build APIs.
- Do not treat build pipelines as deployment automation. Deployment remains
  ArgoCD/GitOps-managed unless the project explicitly changes that model.
- Do not put secrets, registry credentials, subscription entitlement material,
  or generated build output in Git.

## Build Model

Use the official docs to frame:

- **CI/CD overview**: OpenShift provides multiple CI/CD solutions: OpenShift
  Builds, OpenShift Pipelines, OpenShift GitOps, and Jenkins.
- **Builds using Shipwright**: an extensible Shipwright-based framework for
  building container images on-cluster from source code and Dockerfiles, with
  S2I and Buildah strategies and a Kubernetes-native API.
- **BuildConfig**: the classic OpenShift declarative build process based on
  `build.openshift.io/v1` objects.
- **Build**: an instance created from a `BuildConfig`, with status, logs,
  inputs, outputs, resource limits, and completion behavior.
- **Build inputs**: inline Dockerfile, image source, Git, binary input, input
  secrets, config maps, and external artifacts.
- **Build strategies**: Docker, Source-to-Image, custom, and pipeline build
  strategies as documented by the BuildConfig guide.
- **Build controls**: triggers, hooks, resources, maximum duration, node
  assignment, chained builds, pruning, run policy, and strategy RBAC.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - CI/CD overview and solution routing
   - Shipwright-based Builds
   - `BuildConfig`, `Build`, `BuildRequest`, or `BuildLog`
   - Docker, S2I, custom, or pipeline build strategy
   - source inputs, secrets, config maps, registry credentials, or outputs
   - build triggers, hooks, resources, duration, node placement, or pruning
   - build strategy authorization or cluster build-controller configuration
4. For GitOps manifests, verify all API versions, fields, image references,
   strategy permissions, and secret references before committing.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use future `ocp-pipelines` for OpenShift Pipelines and Tekton behavior.
- Use future `ocp-gitops-operator` for OpenShift GitOps Operator and Argo CD.
- Use future `ocp-jenkins` only if the demo intentionally uses Jenkins.
- Use `ocp-image-registry-and-mirroring` after it exists for image registry,
  ImageStream, mirroring, and trusted registry depth beyond build references.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/build-review-patterns.md`
