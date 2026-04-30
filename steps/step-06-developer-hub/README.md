# Step 06: Red Hat Developer Hub — Self-Service Developer Portal
**"From platform components to a self-service developer portal."** — Developer Hub ties together the RHOAI platform, MaaS models, Dev Spaces, and MTA modernization into a single catalog-driven portal.

## Overview

After Steps 01-05, the platform has RHOAI, MaaS models, Dev Spaces, MTA, and AI-assisted modernization. Step 06 adds **Red Hat Developer Hub 1.9** as the internal developer portal that ties the whole workflow together: one place where developers discover applications, models, tools, and modernization workflows.

### What Gets Deployed

```text
Developer Hub (RHDH 1.9)
├── RHDH Operator                     → rhdh-operator namespace
├── Backstage CR                      → rhdh namespace
│   ├── app-config-rhdh ConfigMap     → portal title, auth, catalog config
│   ├── dynamic-plugins-rhdh ConfigMap → Phase 1: defaults only
│   └── rhdh-secrets Secret           → session key, OIDC credentials, URLs
├── ConsoleLink                       → OpenShift launcher menu entry
├── Software Catalog                  → coolstore Component, demo Users/Group
└── PostSync Job                      → RHBK OIDC client, secret patching, restart
```

Manifests: [`gitops/step-06-developer-hub/base/`](../../gitops/step-06-developer-hub/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-06-developer-hub/deploy.sh
./steps/step-06-developer-hub/validate.sh
```

</details>

## Authentication

RHDH authenticates via OIDC against the **MTA Keycloak (RHBK)** realm, which brokers identity from OpenShift OAuth. This gives a consistent identity chain:

```text
Developer Hub → MTA Keycloak (RHBK) → OpenShift OAuth → HTPasswd
```

Users see **"Sign in using OIDC"** on the RHDH login page. After clicking, they authenticate with their OpenShift credentials (same `ai-admin` / `ai-developer` / `<demo-password>` used across MTA and Dev Spaces).

| User | Catalog Role | Portal Access |
|------|-------------|--------------|
| `ai-admin` | ai-modernization-team member | Full catalog visibility |
| `ai-developer` | ai-modernization-team member | Full catalog visibility |

## Software Catalog

The catalog contains:

| Entity | Kind | Description |
|--------|------|-------------|
| `coolstore` | Component | Legacy Java EE CoolStore monolith (lifecycle: modernizing) |
| `ai-admin` | User | Platform administrator |
| `ai-developer` | User | Application developer |
| `ai-modernization-team` | Group | Team owning the modernization workflow |

The coolstore component includes links to:
- GitHub repository (source code)
- Quarkus migration reference branch

## The Demo

### Act 1: Portal Entry

1. Open Developer Hub from the OpenShift launcher menu (or `oc get route -n rhdh`)
2. Click **Sign in using OIDC**
3. Authenticate with OpenShift credentials (`ai-admin` / `<demo-password>`)

### Act 2: Catalog Discovery

1. Search for `coolstore` in the catalog
2. Show the component page: ownership, lifecycle (`modernizing`), tags
3. Click through to the GitHub repository link
4. Explain: "This is where developers discover what applications exist, who owns them, and where to find the tools to work on them."

### Act 3: Modernization Handoff

From the coolstore catalog page:
1. Open **Dev Spaces** to work on the code (Step 04 workspace has coolstore pre-cloned)
2. Open **MTA UI** to run migration analysis (Step 05)
3. The same MaaS model (Nemotron) powers both the coding assistant and MTA's AI fixes

### Act 4: Platform Story

Explain the unified identity and platform story:
- One OpenShift login for everything: RHDH, MTA, Dev Spaces, RHOAI
- The software catalog is the starting point for all developer workflows
- Platform teams control model access (MaaS), migration targets (MTA), and workspace templates (Dev Spaces) — developers consume them through the portal

## Phase 2 Enhancements

- **Software Template**: "Modernize Java EE App with MTA" golden path
- **TechDocs**: Coolstore modernization runbook
- **ArgoCD Plugin**: Show GitOps app status for Steps 01-06
- **OpenShift Plugin**: Show Kubernetes resources for catalog components
- **AI Model Catalog Entities**: Nemotron/GPT-4o as Resource/API kinds
- **OpenShift AI Connector**: Import AI model assets from RHOAI (Developer Preview)

## References

- [Red Hat Developer Hub 1.9 Documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Installing RHDH on OpenShift](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_red_hat_developer_hub_on_openshift_container_platform/index)
- [Configuring RHDH](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/configuring_red_hat_developer_hub/index)
- [RHDH Authentication](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html-single/authentication_in_red_hat_developer_hub/authentication_in_red_hat_developer_hub)
- [RHDH Dynamic Plugins](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9/html/installing_and_viewing_plugins_in_red_hat_developer_hub/index)
