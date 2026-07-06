# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working on projects |
| Guide title | Organize projects, collaborate in workbenches, and deploy models |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_on_projects/index |
| Documentation category | Develop / Working on projects |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Using projects; 1.1 Creating a project; 1.2 Updating a project; 1.3 Deleting a project; 2 Using project workbenches; 2.1 Creating a workbench and selecting an IDE; 2.1.1 About workbench images; 2.1.2 Creating a workbench; 2.2 Starting a workbench; 2.3 Updating a project workbench; 2.4 Deleting a workbench from a project; 3 Using connections; 3.1 Adding a connection to your project; 3.2 Updating a connection; 3.3 Deleting a connection; 3.4 Using the connections API; 4 Configuring cluster storage; 4.1 About persistent storage; 4.2 Adding cluster storage to your project; 4.3 Updating cluster storage; 4.4 Changing the storage class for an existing cluster storage instance; 4.5 Deleting cluster storage from a project; 5 Managing access to projects; 6 Creating project-scoped resources for your project |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Dedicated workbench creation guide and IDE context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-connection-types | Administrator connection type template workflow |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | Storage class administration and OpenShift AI storage class visibility |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-cluster-pvc-size | Cluster default PVC size administration |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-project-scoped-resources_managing-rhoai | Project-scoped resource administrator context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index | KServe serving platform and serving runtime details |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | Workbench data access to S3-compatible object storage |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | Global OpenShift AI user and admin access boundary |
| `.agents/skills/rhoai-connection-types/SKILL.md` | Connection type template administration boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3-compatible object storage data workflow boundary |
| `.agents/skills/rhoai-storage-classes/SKILL.md` | Storage class administration boundary |
| `.agents/skills/rhoai-project-scoped-resources/SKILL.md` | Project-scoped resource schema and GitOps review boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working on projects
  guide above.
- The guide defines user-facing project workflows: project lifecycle,
  workbenches, project connections, cluster storage, permissions, and
  project-scoped resource creation workflow.
- It does not replace global OpenShift AI access administration, connection
  type template administration, storage class administration, custom workbench
  image authoring, complete KServe serving platform configuration, or AI
  Pipelines implementation details.
- Verification: dashboard project state, project resource names, workbench
  state, connection presence and annotations, PVC and storage attachment state,
  project permission entries, and project-scoped resource visibility.

## Unresolved Or Environment-Specific Items

- Active clean-slate project names and persona boundaries.
  Verification: document project ownership and naming in the new GitOps step
  README and `docs/OPERATIONS.md` when implemented.
- Active workbench image choices and custom image needs.
  Verification: inspect dashboard image availability and cross-check support
  status before selecting images in demo content.
- Active storage class and access-mode policy.
  Verification: confirm available OpenShift storage classes and supported
  access modes before documenting cluster storage behavior.
- Active project connection types and environment variable names.
  Verification: inspect selected connection types before authoring notebooks,
  scripts, or model-serving manifests that consume connections.
