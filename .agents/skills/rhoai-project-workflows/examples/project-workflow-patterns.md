# Project Workflow Patterns

These examples are review patterns. Verify the active baseline, dashboard
state, and schema before turning them into GitOps artifacts or runbooks.

## Project Boundary Pattern

Use a project to separate a demo capability, team, or regulated audience
persona.

Review points:

- Resource name is stable, lowercase, and no longer than 30 characters.
- Display name can be audience-facing and can change later.
- README explains the Why and What; operational commands belong in
  `docs/OPERATIONS.md`.
- The project README does not claim workbenches, pipelines, storage, or models
  until those resources are implemented.

## Workbench Pattern

```text
Project: <project-name>
Workbench display name: <audience-facing-name>
Workbench resource name: <stable-resource-name>
IDE: JupyterLab | code-server | RStudio (Technology Preview)
Image: <supported-image-and-version>
Storage: <RWO cluster storage by default>
Connections: <project-scoped connections only>
```

Review points:

- Use the most recently added supported image only when latest packages are
  intentional.
- Label RStudio workbench images as Technology Preview.
- Do not use code-server examples for Elyra-based pipelines.
- Keep additional package installation either temporary or move it to a custom
  image skill workflow.

## Connection Pattern

```text
Connection scope: same project as the consuming workload
Connection type: <S3-compatible | URI | OCI | custom>
Consumers: <workbench | InferenceService | LLMInferenceService | pipeline>
Secrets: Kubernetes Secret or dashboard-managed secret reference
```

Review points:

- Do not commit secret values.
- Verify the connection type and environment variable names before notebook
  code consumes them.
- For `InferenceService` and `LLMInferenceService`, copy annotations and
  fields only from official docs or schema checks.
- Before deleting a connection, list consuming workbenches, serving resources,
  and pipelines.

## Cluster Storage Pattern

```text
Storage purpose: <individual workbench data | shared project data>
Access mode: ReadWriteOnce by default
Storage class: <verified-class>
Mount path: /opt/app-root/src/<mount-folder>
Size: <GiB-or-MiB>
```

Review points:

- Use `ReadWriteMany` only for explicit shared-data collaboration.
- Document backup and write-conflict expectations for RWX.
- Treat storage class as immutable after attachment.
- Increasing size can restart the attached workbench.

## Storage Class Migration Pattern

Use this pattern when a project storage instance needs a different storage
class.

```text
1. Stop the affected workbench.
2. Add new cluster storage with the desired storage class.
3. Start the workbench with old and new storage attached.
4. Copy data from old storage to new storage.
5. Stop the workbench again.
6. Remove old storage from the workbench.
7. Attach new storage at the expected mount path.
8. Restart the workbench and verify files, storage class, and mount path.
```

Review points:

- The official guide uses `rsync` for the copy step.
- Exclude the target mount folder when copying from `/opt/app-root/src`.
- Keep the old storage until post-copy verification passes.

## Project Access Pattern

```text
Principal: <user-or-group>
Project role: Admin | Contributor
Reason: <demo role or team responsibility>
Review owner: <OpenShift AI admin or project owner>
```

Review points:

- Admin can edit project details and manage access.
- Contributor can view and edit project components.
- Project access is separate from global OpenShift AI user/admin access.
- Removed access must be verified from the affected user's perspective where
  practical.

## Project-Scoped Resource Handoff Pattern

```text
Resource type: Workbench image | HardwareProfile | KServe serving runtime template
Trusted source: <official docs | verified resource | reviewed Git | cluster admin>
Target namespace: <project-name>
Unique name: <project-local-resource-name>
Display-name field: <documented field only>
```

Review points:

- Confirm `disableProjectScoped: false` before claiming dashboard visibility.
- Use `rhoai-project-scoped-resources` for manifest review.
- Use the component skill for schema details.
