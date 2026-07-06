# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | CI/CD |
| Source 1 | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/cicd_overview/index |
| Source 2 | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/builds_using_shipwright/index |
| Source 3 | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/builds_using_buildconfig/index |
| Capture date | 2026-06-10 |

## Captured Sections

From CI/CD overview:

- About CI/CD
- OpenShift Builds
- OpenShift Pipelines
- OpenShift GitOps
- Jenkins

From Builds using Shipwright:

- Overview of Builds
- Shipwright-based Builds capabilities
- source code and Dockerfile image builds
- S2I and Buildah build tools
- Shipwright CLI and web console integration
- release-cadence note that points to the separate Builds for Red Hat
  OpenShift documentation set

From Builds using BuildConfig:

- Understanding image builds
- `BuildConfig` object structure
- build inputs, secrets, config maps, and registry credentials
- build output, output image environment variables, and labels
- Docker, Source-to-Image, custom, and pipeline build strategies
- starting, canceling, editing, deleting, viewing, and logging builds
- build triggers, hooks, resources, duration, node assignment, chained builds,
  pruning, and run policy
- Red Hat Universal Base Image and subscription entitlement build patterns
- build strategy authorization
- build controller configuration and troubleshooting

## Source Boundaries

The CI/CD overview identifies OpenShift Pipelines, OpenShift GitOps, and
Jenkins, but this skill does not extract their detailed behavior because the
user-provided detailed sources are build-specific. Create separate
`ocp-pipelines`, `ocp-gitops-operator`, and `ocp-jenkins` skills when official
sources for those areas are provided.

The OCP Builds using Shipwright page states that Builds releases on a different
cadence from OpenShift Container Platform and that detailed Builds
documentation is available as a separate documentation set. Treat Shipwright
API field details as unresolved until that separate official documentation and
the active cluster CRDs are verified.

## Related Official Sources To Add Later

- OpenShift Pipelines documentation
- OpenShift GitOps documentation
- Jenkins images and templates documentation
- Image registry and ImageStream documentation
- Builds for Red Hat OpenShift documentation set
