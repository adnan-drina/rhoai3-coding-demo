# Official Doc Extraction

Use this extraction to keep OCP GitOps content grounded in the official OCP
source. When implementation needs exact Operator, Argo CD, Application,
AppProject, RBAC, or configuration fields, verify the separate Red Hat
OpenShift GitOps documentation and active cluster schema before authoring
GitOps manifests.

## OCP-Level Product Definition

The official OCP GitOps page defines Red Hat OpenShift GitOps as an Operator
that uses Argo CD as the declarative GitOps engine.

The page states that OpenShift GitOps enables GitOps workflows across
multicluster OpenShift and Kubernetes infrastructure and lets administrators
consistently configure and deploy Kubernetes-based infrastructure and
applications across clusters and development lifecycles.

## Argo CD Relationship

The official OCP page states that Red Hat OpenShift GitOps is based on the
upstream Argo CD project and provides a similar feature set, with additional:

- automation
- integration into Red Hat OpenShift Container Platform
- Red Hat enterprise support
- quality assurance
- focus on enterprise security

Do not treat upstream Argo CD behavior as Red Hat product behavior until it is
verified against Red Hat OpenShift GitOps documentation and the installed
Operator version.

## Documentation Cadence Boundary

The official OCP page states that Red Hat OpenShift GitOps releases on a
different cadence from OpenShift Container Platform and that Red Hat OpenShift
GitOps documentation is available as a separate documentation set.

Implications for this repo:

- OCP 4.20 is the platform baseline, but it is not enough to infer a specific
  Red Hat OpenShift GitOps minor version.
- Do not hard-code GitOps Operator channel, Argo CD version, Argo CD CR schema,
  or Application fields from OCP 4.20 alone.
- Pin or capture the Red Hat OpenShift GitOps product version before creating
  detailed reusable skills for install, security, RBAC, notifications,
  multi-cluster, progressive delivery, or GitOps CLI workflows.

## Demo-Specific GitOps Constraint Handoff

The following are project constraints from `AGENTS.md` and
`project-gitops-authoring`, not claims extracted from the OCP overview page:

- Argo CD `resourceTrackingMethod` must be `annotation` for this demo.
- Demo Applications should use `project: rhoai-demo` unless the project model
  changes.
- New deploy automation must apply Argo CD Applications first and avoid direct
  `oc apply -k` against Argo CD-managed resources.
- During active refactoring, Applications may temporarily pin to the active
  refactoring branch.

Use `project-gitops-authoring` for these repo-specific implementation rules.

## Verification Before Implementation

Before implementing active GitOps platform resources, verify:

- installed OpenShift GitOps Operator subscription and CSV
- available Argo CD and Argo Rollouts API resources
- existing Argo CD namespace and instance
- Application and AppProject CRDs
- Operator-managed ConfigMaps and Secrets
- RBAC, service accounts, cluster roles, and cluster role bindings
- Argo CD resource tracking configuration

Discovery commands belong in `references/validation-checklist.md`; do not run
them unless the OpenShift safety guard confirms the target cluster.
