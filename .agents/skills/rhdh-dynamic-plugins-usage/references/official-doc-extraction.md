# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Using dynamic plugins
Captured: 2026-07-06

---

## 1. Ansible Plugins (Technology Preview)

Ansible plug-ins deliver an Ansible-specific portal experience:
- Curated learning paths
- Push-button content creation
- Integrated development tools
- Opinionated resources

**Status:** Technology Preview — not supported with Red Hat production SLAs.

Additional resources:
- Using Ansible plug-ins for Red Hat Developer Hub (separate Ansible guide)

## 2. Argo CD Plugin

Visualizes Continuous Delivery (CD) workflows in OpenShift GitOps.

**Prerequisites:** Argo CD plugin must be enabled in RHDH.

**Procedure:**
1. Open RHDH and select a component from the Catalog page
2. Select the **CD tab** to view deployments managed by Argo CD
3. Select a card to view deployment details:
   - Commit message
   - Author name
   - Container image promoted to environment
   - Deployment history
4. Click the link icon to open deployment details directly in Argo CD
5. In the **Overview tab**, navigate to the **Deployment summary** section to
   review deployment across namespaces
6. Select an Argo CD app to open details in Argo CD, or select a commit ID
   from the Revision column to review changes in GitLab or GitHub

## 3. JFrog Artifactory Plugin

Displays container image information from JFrog Artifactory registry.

**Prerequisites:**
- Developer Hub application is installed and running
- JFrog Artifactory plugin is enabled

**Procedure:**
1. Open Developer Hub and select a component from the Catalog page
2. Go to the **Image Registry** tab
3. View container images with: Version, Repositories, Manifest, Modified, Size

## 4. Keycloak Plugin

Backend plugin integrating Keycloak user and group synchronization.

**Capabilities:**
- Synchronization of Keycloak users in a realm
- Synchronization of Keycloak groups and their users in a realm
- Imports users and groups at startup
- Optional scheduled periodic imports

**Procedure:**
1. In RHDH, go to the **Catalog** page
2. Select **User** from the entity type filter to see imported users
3. Browse the list and select a user for detailed Keycloak information
4. Select **Group** from the entity type filter to see imported groups
5. Select a group to view imported group information from Keycloak

## 5. Nexus Repository Manager Plugin

Displays build artifacts from Nexus Repository Manager.

**Prerequisites:**
- Developer Hub application is installed and running
- Nexus Repository Manager plugin is installed

**Procedure:**
1. Open Developer Hub and select a component from the Catalog page
2. Go to the **BUILD ARTIFACTS** tab
3. View artifacts with: VERSION, REPOSITORY, REPOSITORY TYPE, MANIFEST,
   MODIFIED, SIZE

## 6. Tekton Plugin

Visualizes CI/CD pipeline run results from Kubernetes/OpenShift clusters.
Uses the Tekton front-end plugin to view `PipelineRun` resources.

**Prerequisites:**
- RHDH is installed
- Tekton plugin is installed

**Procedure:**
1. Open RHDH and select a component from the Catalog page
2. Go to the **CI tab**
3. View PipelineRun list with: NAME, VULNERABILITIES, STATUS, TASK STATUS,
   STARTED, DURATION
4. Click the expand row button beside a PipelineRun name to view the pipeline
   visualization
5. Hover on a task card to view the steps for that task

## 7. Topology Plugin

Front-end plugin that displays workloads as nodes on a Kubernetes cluster.

### 7.1 RBAC Permissions

When RHDH authorization is enabled, grant the following permissions:

| Permission | Access | Purpose |
|-----------|--------|---------|
| `kubernetes.clusters.read` | `read` | View Topology panel |
| `kubernetes.resources.read` | `read` | View Topology panel |
| `kubernetes.proxy` | `use` | View pod logs |
| `catalog-entity` | `read` | View catalog items |

**Prerequisite:** Managing authorization using external files.

Example `rbac-policy.csv`:

```csv
g, user:default/<YOUR_USERNAME>, role:default/topology-viewer
p, role:default/topology-viewer, kubernetes.clusters.read, read, allow
p, role:default/topology-viewer, kubernetes.resources.read, read, allow
p, role:default/topology-viewer, kubernetes.proxy, use, allow
p, role:default/topology-viewer, catalog-entity, read, allow
```

### 7.2 Using Topology

**Prerequisites:**
- RHDH is installed and running
- Topology plugin is installed
- Users are enabled for the Topology plugin (RBAC granted)

**Procedure:**
1. Open RHDH and select a component from the Catalog page
2. Go to the **TOPOLOGY** tab to view workloads as nodes
3. Select a node — a popup shows **Details** and **Resources** tabs
4. Click **Open URL** on top of a node to access associated Ingresses and
   run the application in a new tab
