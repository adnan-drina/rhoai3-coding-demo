# Official Doc Extraction

Use this extraction to keep Migration Toolkit for Applications installation
procedures grounded in the official Red Hat MTA 8.1 installation guide. All CR
fields, namespaces, roles, prerequisites, and procedures are taken directly from
the official documentation.

## Introduction

The Migration Toolkit for Applications (MTA) is a set of tools to accelerate
large-scale application modernization efforts across hybrid cloud environments
on Red Hat OpenShift. MTA provides inventory, assessment, analysis, and
management capabilities for faster migration to OpenShift at both portfolio and
application levels.

## MTA Tools

| Tool | Purpose |
|------|---------|
| User interface (UI) | Assess containerization risks, analyze code changes |
| Command-line interface (CLI) | Assess and analyze with customization and automation integration |
| MTA Operator | Install UI on OpenShift Container Platform |
| VS Code add-on | Analyze, mark issues, provide fix guidance, auto-replace |
| IntelliJ IDEA add-on | Analyze, mark issues, provide fix guidance |

## Supported Migration Paths

### Java

Sources: Oracle WebLogic, IBM WebSphere, JBoss EAP 4–7, Thorntail, Oracle JDK,
Camel 2, Spring Boot, any Java/Java EE application.

Targets: JBoss EAP 7 & 8, OpenShift (cloud readiness), OpenJDK 11/17/21,
Jakarta EE 9, Camel 3 & 4, Spring Boot in Red Hat Runtimes, Quarkus, Open
Liberty.

### .NET (Developer Preview)

Source: .NET Framework 4.5+ (Windows only).
Targets: OpenShift (cloud readiness), .NET 8.0.

## Installing the MTA User Interface

### Persistent Volume Requirements

MTA Operator requires two RWO PVs minimum. With `rwx_supported: true`, two
additional RWX PVs are required.

| Name | Size | Access | Description |
|------|------|--------|-------------|
| hub database | 10 Gi | RWO | Hub database |
| hub bucket | 100 Gi | RWX | Hub file storage (when `rwx_supported: true`) |
| keycloak postgresql | 1 Gi | RWO | Keycloak backend database |
| cache | 100 Gi | RWX | Maven m2 cache (when `rwx_supported: true`) |
| kai-db | 5 Gi | RWO | Developer Lightspeed database |

### Red Hat Build of Keycloak (RHBK)

MTA uses a managed RHBK instance for user authentication and authorization. The
MTA Operator manages the instance and configures a dedicated realm.

Access the RHBK Admin Console:

```bash
oc get secret mta-keycloak-rhbk -n openshift-mta -o json | \
  jq -r '.data.password | @base64d'
```

Console URL: `https://<web_console_address>/auth/admin`

### Roles, Personas, and Permissions

| Role | Persona | Access |
|------|---------|--------|
| `tackle-admin` | Administrator | All permissions, credential management, Administration view |
| `tackle-architect` | Architect | Run assessments, create/modify apps, consume credentials |
| `tackle-migrator` | Migrator | Analyze applications only |

A user can have multiple roles. Only Administrators can access the
Administration view.

### Installing the MTA Operator

#### Prerequisites

- 4 vCPUs, 8 GB RAM, 40 GB persistent storage
- Red Hat OpenShift 4.13–4.15 (cloud service or self-hosted)
- Two RWO persistent volumes
- Logged in as `cluster-admin`

#### Procedure

1. Install MTA Operator from OperatorHub in `openshift-mta` namespace.
2. Review the Tackle CR settings (default settings acceptable).
3. Verify MTA pods are running: Administration > Workloads > Pods.
4. Verify Operator shows `Succeeded` status in Operators > Installed Operators.

### Creating an MTA Instance

#### Prerequisites

- MTA Operator installed
- 4 vCPUs, 8 GB RAM, 40 GB persistent storage
- OpenShift 4.13–4.15
- `cluster-admin` permissions

#### Procedure

1. Create a Tackle CR (defaults acceptable).
2. Log in with default credentials: `admin` / `Passw0rd!`.
3. Change default password immediately.

### Tackle Custom Resource

```yaml
kind: Tackle
apiVersion: tackle.konveyor.io/v1alpha1
metadata:
  name: mta
  namespace: openshift-mta
spec:
  hub_bucket_volume_size: "100Gi"
  maven_data_volume_size: "100Gi"
  rwx_supported: "false"
```

### Common CR Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `cache_data_volume_size` | 100 GB | Cache volume size (ignored when `rwx_supported: false`) |
| `cache_storage_class` | default | Storage class for cache volume |
| `feature_auth_required` | true | Whether Keycloak auth is required; `false` = single admin user |
| `feature_isolate_namespace` | true | Enable namespace isolation via NetworkPolicy |
| `hub_database_volume_size` | 10 GB | Hub database volume size |
| `hub_bucket_volume_size` | 100 GB | Hub bucket volume size |
| `hub_bucket_storage_class` | default | Storage class for bucket volume |
| `keycloak_database_data_volume_size` | 1 GB | Keycloak database volume size |
| `pathfinder_database_data_volume_size` | 1 GB | Pathfinder database volume size |
| `rwx_supported` | true | Whether cluster supports RWX storage |
| `rwo_storage_class` | NA | Storage class for RWO volumes |
| `rhsso_external_access` | false | Create dedicated route for RHSSO |
| `analyzer_container_limits_cpu` | 1 | Max CPUs for analyzer pod |
| `analyzer_container_limits_memory` | 4 GB | Max memory for analyzer pod (increase if OOMKilled) |
| `analyzer_container_requests_cpu` | 1 | Min CPUs for analyzer pod |
| `analyzer_container_requests_memory` | 4 GB | Min memory for analyzer pod |

## Installing the MTA CLI

### Prerequisites (zip install)

- Logged in to `registry.redhat.io` (not needed for containerless mode)
- Java Development Kit (JDK) 17 or later
- `JAVA_HOME` environment variable set
- Maven 3.9.9 or later on `$PATH`

### Available CLI Downloads (8.1.2)

- `mta-8.1.2-cli-linux-amd64.zip`
- `mta-8.1.2-cli-linux-arm64.zip`
- `mta-8.1.2-cli-darwin-amd64.zip`
- `mta-8.1.2-cli-darwin-arm64.zip`
- `mta-8.1.2-cli-windows-amd64.zip`
- `mta-8.1.2-cli-windows-arm64.zip`
- `mta-8.1.2-cli-src.zip`

### Procedure

1. Download OS-specific zip from the MTA download page.
2. Extract the archive.
3. Move `mta-cli` binary to a directory on `$PATH`.

### Disconnected Environment Installation

Applies to container mode only (`--run-local=false`).

1. On connected device: `podman login registry.redhat.io`
2. Run `mta-cli analyze` to pull required provider images
3. Save images: `podman save <image_ID> -o <image_name>.image`
4. Transfer to disconnected device
5. Load images: `podman load --input <image_name>.image`

Required images (container mode):

- `registry.redhat.io/mta/mta-generic-external-provider-rhel9`
- `registry.redhat.io/mta/mta-cli-rhel9`
- `registry.redhat.io/mta/mta-java-external-provider-rhel9`
- `registry.redhat.io/mta/mta-dotnet-external-provider-rhel9`

Note: Analysis output in disconnected mode has fewer incidents because
dependency analysis does not run accurately without Maven access.

### Docker on Windows (Developer Preview)

For .NET Framework 4.5+ to .NET 8.0 migrations:

Prerequisites:

- 64-bit Windows 11 21H2 or later
- Docker Desktop for Windows
- Hyper-V and Containers features enabled

Key configuration:

- Docker must use Windows containers (not Linux containers)
- `CONTAINER_TOOL` = `C:\Windows\system32\docker.exe`
- `DOTNET_PROVIDER_IMG` = `quay.io/konveyor/dotnet-external-provider:v0.5.0`
- `RUNNER_IMG` = `quay.io/konveyor/kantra:v0.5.0`

## Verification Commands

```bash
# Verify MTA Operator installed
oc get csv -n openshift-mta | grep mta

# Verify MTA pods running
oc get pods -n openshift-mta

# Verify Tackle CR
oc get tackle -n openshift-mta

# Verify Keycloak secret exists
oc get secret mta-keycloak-rhbk -n openshift-mta

# Verify CLI installed
mta-cli --version
```
