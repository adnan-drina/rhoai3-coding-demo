# Validation Checklist

Use this checklist before accepting OpenShift AI project, workbench,
connection, storage, permission, or project-scoped resource documentation and
GitOps-adjacent examples.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The Working on projects guide is recorded when project workflows are
  introduced.
- Global user and administrator access is delegated to
  `rhoai-users-groups-access` and `rhoai-access-group-selection`.
- Connection type template administration is delegated to
  `rhoai-connection-types`.
- S3-compatible object operations are delegated to
  `rhoai-s3-object-storage-data`.
- Storage class administration and cluster default PVC size are delegated to
  `rhoai-storage-classes` and `rhoai-cluster-pvc-size`.
- Project-scoped resource schema and GitOps review is delegated to
  `rhoai-project-scoped-resources`.

## Project Review

- Project resource names follow the documented lowercase, hyphen, length,
  start-character, and end-character rules.
- Resource names are treated as immutable after creation.
- Display name and description changes are documented separately from resource
  name changes.
- Project deletion warnings identify workbenches, AI pipelines, cluster
  storage, and connections as associated resources that are deleted.
- README claims do not imply project creation deploys resources that are not
  implemented.

## Workbench Review

- A project exists before workbench creation.
- Workbench resource names follow the same naming constraints as projects.
- The selected IDE and image are available for the active OpenShift AI
  baseline.
- RStudio and hardware profile usage is labeled Technology Preview where used.
- code-server examples do not claim Elyra-based pipeline support.
- Extra package installation is either explicitly temporary or moved into a
  custom image workflow.
- Workbench environment variables do not include committed secret values.

## Connection Review

- Connections are project-scoped and consumed from the same namespace as the
  workload.
- Secrets are not committed to Git, notebooks, READMEs, or scripts.
- Credential examples use placeholders or generated secret references only.
- S3 credential variable names are verified against the selected connection
  type before use.
- Connection API annotations are copied from the official docs or verified
  schema; they are not guessed.
- Dependent workbenches, model-serving resources, and pipelines are reviewed
  before deleting a connection.

## Storage Review

- The storage class exists and supports the intended access mode before
  documenting or selecting it.
- `ReadWriteOnce` is used by default for individual workbench storage.
- `ReadWriteMany` is used only with explicit collaboration rationale, backup
  expectations, and write-conflict controls.
- Storage class immutability is documented when cluster storage is attached to
  a workbench.
- Size increases note the possible workbench restart and downtime impact.
- Storage-class migration copies data into new storage, detaches old storage,
  attaches new storage, and verifies the new storage class and mount path.
- Cluster storage deletion includes permanent-data-loss warning and
  post-delete verification.

## Project Access Review

- Permission changes happen at the project Permissions tab or through an
  officially documented equivalent.
- Access level claims match the documented Admin and Contributor behavior.
- Group entry behavior accounts for the cluster-admin versus non-cluster-admin
  dashboard experience.
- Removed users or groups are verified to no longer have the previous project
  actions.

## Project-Scoped Resource Review

- `disableProjectScoped: false` is required before dashboard use of
  project-scoped resources is claimed.
- YAML comes from trusted official docs, existing verified resources, reviewed
  Git, or a cluster administrator.
- `metadata.namespace` is set to the target project.
- `metadata.name` is unique within the target project.
- Only documented display-name fields are changed without component-specific
  review.
- Detailed schema review is handed to `rhoai-project-scoped-resources` and the
  component owner skill.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get project <project-name>
oc get notebooks.kubeflow.org -n <project-name>
oc get secrets -n <project-name>
oc get pvc -n <project-name>
oc get rolebindings -n <project-name>
oc get hardwareprofiles.infrastructure.opendatahub.io -n <project-name>
oc get imagestreams.image.openshift.io -n <project-name>
oc get templates.template.openshift.io -n <project-name>
```

## Fail Conditions

Stop and correct the work if any of these are true:

- Project, workbench, connection, storage, or access behavior is undocumented
  and no verification command is provided.
- Secret values appear in committed content.
- Project or cluster-storage deletion is presented as reversible.
- RWX shared storage is used without a clear collaboration need and risk note.
- Technology Preview features are presented as production-supported.
- Connection API fields or annotations are guessed.
