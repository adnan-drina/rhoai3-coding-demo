# Official Doc Extraction

Use this extraction to keep OCP CI/CD build content grounded in official Red
Hat sources. When implementation needs exact CR fields, verify the active
cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## CI/CD Solution Routing

The OCP CI/CD overview identifies these platform options:

- OpenShift Builds
- OpenShift Pipelines
- OpenShift GitOps
- Jenkins

Use this skill for OpenShift Builds only. Use future dedicated skills for
Pipelines, GitOps, and Jenkins behavior.

## Shipwright-Based Builds

The OCP Builds using Shipwright guide describes Builds as an extensible
framework based on the Shipwright project for building container images on an
OpenShift cluster.

Official behavior to preserve:

- Builds can build container images from source code and Dockerfiles.
- The documented build tools include Source-to-Image (S2I) and Buildah.
- Builds provides a Kubernetes-native API for building container images.
- Builds supports custom build strategies.
- Builds can run from source code in a local directory.
- The Shipwright CLI can create builds, view build-run logs, and manage builds
  on the cluster.
- The OpenShift web console Developer perspective provides an integrated user
  experience.
- The OCP page states that Builds documentation is maintained separately because
  Builds releases on a different cadence from OCP.

Do not invent Shipwright API versions, `Build`, `BuildRun`, `BuildStrategy`,
`ClusterBuildStrategy`, or parameter fields from the OCP page alone. Verify the
separate Builds for Red Hat OpenShift documentation and the active CRDs first.

## BuildConfig-Based Builds

The BuildConfig guide describes a build as a process that transforms input
parameters or source code into an output object, most often a runnable image.
A `BuildConfig` defines the complete build process.

Official behavior to preserve:

- `BuildConfig` resources use `apiVersion: build.openshift.io/v1`.
- A `BuildConfig` is characterized by a build strategy and one or more sources.
- Build strategies documented by the guide include Docker, Source-to-Image
  (S2I), custom, and pipeline.
- Docker builds use Buildah to build a container image from a Dockerfile.
- S2I builds produce ready-to-run images by injecting source into a builder
  image and assembling a new image.
- Custom builds produce whatever output the custom builder image author
  specifies.
- Build objects publish logs, output resources, and final status, and can use
  CPU, memory, and execution-time limits.

## BuildConfig Shape

The official `BuildConfig` example includes these areas:

- `metadata.name`
- `spec.runPolicy`
- `spec.triggers`
- `spec.source`
- `spec.strategy`
- `spec.output`
- `spec.postCommit`

The documented default run policy is `Serial`, meaning newly created builds run
sequentially rather than simultaneously. Verify exact allowed values before
changing run policy.

## Build Inputs And Outputs

The official guide lists build inputs in precedence order:

- inline Dockerfile definitions
- content extracted from existing images
- Git repositories
- binary or local inputs
- input secrets
- external artifacts

The guide also covers input secrets, config maps, registry credentials, service
serving certificate secrets, build environments, output image environment
variables, output image labels, and output image destinations.

Do not commit registry credentials, entitlement material, or generated build
artifacts. Reference secrets by name and document how they are created through
the active environment process.

## Build Operations

The BuildConfig guide covers:

- starting builds
- canceling builds
- editing and deleting `BuildConfig` resources
- preserving or deleting builds when deleting a `BuildConfig`
- viewing build details with `oc describe build`
- streaming logs from a `BuildConfig` with `oc logs -f bc/<name>`
- using `oc logs --version=<number> bc/<name>` for a specific build version
- setting `BUILD_LOGLEVEL` for source or Docker strategies

Deleting a `BuildConfig` normally deletes instantiated builds. The guide
documents `--cascade=false` when deleting a `BuildConfig` while keeping the
builds.

## Triggers, Hooks, Resources, And Scheduling

The guide covers build triggers, build hooks, resource settings, maximum build
duration, node assignment, chained builds, pruning, and build run policy.

Treat node assignment as a scheduling decision. Use `ocp-nodes` to validate
node selectors, labels, taints, tolerations, and placement implications before
committing build placement rules.

## Build Strategy Authorization

The guide documents strategy subresources and default roles:

- Docker: `builds/docker`, `system:build-strategy-docker`
- Source-to-Image: `builds/source`, `system:build-strategy-source`
- Custom: `builds/custom`, `system:build-strategy-custom`
- JenkinsPipeline: `builds/jenkinspipeline`,
  `system:build-strategy-jenkinspipeline`

By default, users who can create builds are granted permission to use Docker
and S2I build strategies. Custom strategy access requires cluster-admin
involvement. Treat strategy RBAC changes as cluster-wide security-sensitive
operations.

## Build Controller And Troubleshooting

The guide covers build controller configuration parameters, build settings,
denied resource access, service certificate generation failures, and adding
certificate authorities to the cluster.

Treat build-controller configuration and cluster CA changes as live platform
operations that require explicit approval and official-doc verification.
