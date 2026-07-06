# Official Documentation Extraction: Discover OpenShift Dev Spaces 3.28

Source: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/discover_openshift_dev_spaces/index
Captured: 2026-07-06

---

## Chapter 1: What is OpenShift Dev Spaces?

### Product Description

Red Hat OpenShift Dev Spaces is an OpenShift-native platform that provides
cloud development environments (CDEs) to development teams. Instead of
configuring local machines, developers get on-demand workspaces —
container-based environments with all the tools, dependencies, and IDE access
needed to code, build, test, and debug applications.

### Core Goals

1. **Accelerate project and developer onboarding** — zero-install development
   environment accessible through a browser or desktop IDE. Anyone can join a
   team and contribute within minutes rather than hours or days of local setup.

2. **Remove inconsistency between developer environments** — every developer
   works in the same container-based environment defined by a devfile. Code
   behaves identically across all team members' workspaces.

3. **Provide built-in security and enterprise readiness** — source code stays on
   the cluster, supports RBAC through OpenShift, integrates with enterprise
   identity providers through OIDC authentication.

### What OpenShift Dev Spaces Provides

- **Workspaces**: Container-based developer workspaces running as OpenShift Pods
  with all tools and dependencies. Each workspace is isolated, reproducible, and
  defined by a devfile.
- **Browser-based and desktop IDEs**: Microsoft Visual Studio Code - Open Source
  runs in the browser by default. JetBrains IntelliJ IDEA connects through
  JetBrains Gateway for a native desktop experience.
- **Extensible platform**: Customize through devfiles, VS Code extensions from
  Open VSX registries, and AI coding assistants. Platform engineers define
  standardized environments that developers consume.
- **Enterprise integration**: OpenShift-native deployment through an Operator,
  OIDC authentication, OpenShift RBAC for access control, integration with
  Prometheus for monitoring.

### Workspace Model

A workspace is defined as the project source code together with all dependencies
necessary to edit, build, run, and debug it. The IDE and development runtime are
treated as workspace dependencies — embedded and always included.

Workspaces are OpenShift Pods that replicate application runtimes used in
production and provide a development layer on top (intelligent code completion,
debugging, IDE tools). Workspaces are isolated from one another and manage the
lifecycle of their own components.

---

## Chapter 2: What Problems Does OpenShift Dev Spaces Solve?

| Problem | Solution |
|---------|----------|
| Environment inconsistency | Devfiles define exact tools, runtimes, and dependencies. Every developer opening the same repository gets an identical environment. |
| Slow developer onboarding | Developer opens dashboard URL, pastes repository link, gets fully configured workspace in ~3 minutes. |
| Security and credential management | OAuth integration with Git providers, tokens stored as OpenShift Secrets on cluster, not on individual machines. |
| Environment drift over time | Workspace container rebuilt from devfile on each start. `/home/user` persists for personal preferences; base toolchain always consistent. |
| Resource constraints on laptops | Workspaces run on cluster infrastructure with configurable CPU, memory, and storage limits. |
| Compliance in regulated environments | Runs entirely within OpenShift cluster; supports air-gapped environments with no internet access. |

---

## Chapter 3: Who Is OpenShift Dev Spaces For?

### Platform Administrators

Responsibilities:
- Deploy the OpenShift Dev Spaces Operator and configure the `CheCluster` CR
- Set up OAuth for Git providers
- Manage workspace policies (idle timeouts, resource limits, max workspaces per user)
- Monitor platform health through DWO metrics and Grafana dashboards
- Upgrade OpenShift Dev Spaces

Tools: OpenShift web console, `oc`, `dsc` CLI.

### Developers

Experience:
- Open a Git repository URL to launch a workspace with code, tools, dependencies
- Code in browser-based IDE (VS Code - Open Source default) with full terminal
- Push commits, review PRs, collaborate from the browser
- Switch projects by creating multiple workspaces

Requirements: web browser and network access to the dashboard URL. No local
tools, CLI installations, or cluster credentials needed.

### Deployment Models

- **Small teams**: single instance with default settings
- **Growing teams**: resource quotas, Image Puller for faster starts, monitoring
- **Enterprise**: air-gapped installations, advanced authorization, scalability guidance

---

## Chapter 4: When to Use OpenShift Dev Spaces

### Teams That Benefit

- New developers join regularly and need day-one productivity
- Builds fail from machine differences
- Credentials must stay on cluster infrastructure
- Development within controlled network boundary (including air-gapped)
- Complex dependency chains difficult to reproduce locally

### Enterprise Capabilities

- **On-premises control**: source code and credentials within own infrastructure
- **Air-gapped deployment**: mirrored container images and internal extension registries
- **Native OpenShift integration**: RBAC, OAuth, networking, storage directly
- **Open devfile standard**: devfile.io community-maintained format

---

## Chapter 5: How OpenShift Dev Spaces Works

### Architecture Overview

Three groups of components communicating through Dev Workspace custom resources:

1. **OpenShift Dev Spaces server components** — manage user projects and
   workspaces. Main component: user dashboard.
2. **Dev Workspace Operator** — creates and controls OpenShift objects for user
   workspaces (Pods, Services, PersistentVolumes).
3. **User workspaces** — container-based development environments including IDE.

Central OpenShift features:
- **Dev Workspace Custom Resources** — communication channel between all components
- **OpenShift RBAC** — controls access to all resources

### Operator and Lifecycle Management

The OpenShift Dev Spaces Operator manages the full lifecycle of server
components through the `CheCluster` custom resource.

Creating a `CheCluster` CR triggers deployment of:
- Dev Workspace Operator
- Gateway
- Dashboard
- Server
- Plug-in registry

Key objects:
- `CheCluster` CRD — defines the `CheCluster` OpenShift object
- OpenShift Dev Spaces controller — creates pods, services, persistent volumes
- `CheCluster` CR — triggers full lifecycle management of all server components

### Dev Workspace Operator (DWO)

DWO extends OpenShift to manage workspace pods, services, and persistent volumes
by reconciling Dev Workspace custom resources.

Every workspace has an underlying Dev Workspace CR containing:
- Devfile details
- Editor definition
- Configuration attributes (from CheCluster CR settings)

When a workspace starts, DWO reads the Dev Workspace CR and creates:
- Deployments
- Secrets
- ConfigMaps
- Routes

#### Custom Resource Definitions

| CRD | Purpose |
|-----|---------|
| `DevWorkspace` | Workspace definition (devfile + editor + attributes) |
| `DevWorkspaceTemplate` | Reusable `spec.template` content (e.g., editor definitions) |
| `DevWorkspaceOperatorConfig` (DWOC) | DWO configuration (global and non-global) |
| `DevWorkspaceRouting` | Workspace endpoint definitions |

#### DevWorkspaceOperatorConfig (DWOC)

Two types:
- **Global**: named `devworkspace-operator-config`, located in DWO installation
  namespace. Not created by default. Applies to DWO and all Dev Workspaces.
- **Non-global**: any other DWOC. Only applies to Dev Workspaces that reference
  it. Takes precedence over global config for matching fields.

OpenShift Dev Spaces creates a non-global DWOC named `devworkspace-config` in
the Dev Spaces namespace. Workspaces reference it via the
`controller.devfile.io/devworkspace-config` attribute.

#### DWO Operands

- `devworkspace-controller-manager` — reconciles custom resources
- `devworkspace-webhook-server` — webhook validation

```bash
$ oc get pods -l 'app.kubernetes.io/part-of=devworkspace-operator' \
    -o custom-columns=NAME:.metadata.name -n openshift-operators
```

### DevWorkspaceRouting Example

```yaml
apiVersion: controller.devfile.io/v1alpha1
kind: DevWorkspaceRouting
metadata:
  annotations:
    controller.devfile.io/devworkspace-started: 'false'
  name: routing-workspaceb14aa33254674065
  labels:
    controller.devfile.io/devworkspace_id: workspaceb14aa33254674065
spec:
  devworkspaceId: workspaceb14aa33254674065
  endpoints:
    universal-developer-image:
      - attributes:
          cookiesAuthEnabled: true
          discoverable: false
          type: main
          urlRewriteSupported: true
        exposure: public
        name: che-code
        protocol: https
        secure: true
        targetPort: 3100
  podSelector:
    controller.devfile.io/devworkspace_id: workspaceb14aa33254674065
  routingClass: che
status:
  exposedEndpoints:
    ...
```

### Configuring DWO Controller Manager

Configure via the Dev Workspace Operator Subscription:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: devworkspace-operator
  namespace: openshift-operators
spec:
  config:
    affinity:
      nodeAffinity: ...
      podAffinity: ...
    resources:
      limits:
        memory: ...
        cpu: ...
      requests:
        memory: ...
        cpu: ...
```

### Configuring DWO Webhook Server

Configure via global DWOC:

```yaml
apiVersion: controller.devfile.io/v1alpha1
kind: DevWorkspaceOperatorConfig
metadata:
  name: devworkspace-operator-config
  namespace: <DWO install namespace>
config:
  webhooks:
    nodeSelector: <map[string]string>
    replicas: <int>
    tolerations: <[]corev1.Toleration>
```

### Gateway and Request Routing

The `che-gateway` Deployment (managed by the Operator) has three roles:
- **Routing requests** — uses Traefik
- **Authenticating users** — uses OAuth2 Proxy (OIDC)
- **Applying RBAC** — uses kube-rbac-proxy

Controls access to: dashboard, server, plug-in registry, user workspaces.

### Dashboard and Workspace Management

The user dashboard is the landing page. Workspace startup sequence:

1. Sends repository URL to server, receives devfile
2. Reads the devfile describing the workspace
3. Collects additional metadata from the plug-in registry
4. Converts information into a Dev Workspace CR
5. Creates the Dev Workspace CR in the user project via OpenShift API
6. Watches Dev Workspace CR status
7. Redirects user to the running workspace IDE

### Server and Namespace Provisioning

Java web service (HTTP REST API) with functions:
- Creating user namespaces
- Provisioning user namespaces with secrets and config maps
- Integrating with Git service providers (devfile fetching, authentication)

Needs access to: Git service providers, OpenShift API.

### Plug-in Registry

Provides available editors and editor extensions, each described by a Devfile v2.
The dashboard reads this registry when assembling the Dev Workspace CR.

### User Workspace Contents

A workspace is one OpenShift Deployment containing:
- Workspace containers and enabled plugins
- ConfigMaps
- Services
- Endpoints
- Ingresses or Routes
- Secrets
- Persistent Volumes (PV)

Services provided in the browser:
- Editor
- Language auto-completion
- Language server
- Debugging tools
- Plug-ins
- Application runtimes

Source code persists in an OpenShift Persistent Volume (PV). Microservices have
read/write access to this shared directory.

Use the **devfile v2** format to specify tools and runtime applications.
