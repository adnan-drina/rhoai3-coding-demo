# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub conceptual content grounded in
official Red Hat sources. When implementation needs exact CR fields or
configuration, verify against the active cluster and official configuration
guides before authoring GitOps manifests.

## Product Overview

Red Hat Developer Hub (RHDH) is a fully supported, enterprise-grade productized
version of upstream Backstage 1.49.4. It is an internal developer portal (IDP)
that centralizes access to source code repositories, CI/CD pipelines, APIs,
documentation, and runtime environments.

RHDH is designed for cloud-native environments including Red Hat OpenShift
Container Platform, supported Kubernetes platforms, and hybrid infrastructure.
It helps developer teams onboard quickly, create environments, and integrate
with existing systems.

## Internal Developer Platforms

IDPs address the challenges of modern software delivery by enabling
self-service, enforcing standards, and improving the developer experience.

### Value for Organizations

- **Scalability**: consistent developer onboarding across growing teams.
- **Security**: RBAC and enterprise system integration.
- **Operational efficiency**: centralized workflows, reduced manual handoffs.

### Value for Platform Engineers

- Curated, reusable templates aligned with organizational policies.
- Central configuration defined as code.
- Governance embedded in developer workflows via automation and templates.

### Value for Developers

- Faster onboarding via learning paths, templates, and software catalog.
- Reduced cognitive load: tools, docs, and environments in one place.
- Self-service workflows for applications and environments.
- Preconfigured templates enforcing secure, compliant workflows.
- Cross-team visibility through shared service catalogs.

## Key Features

| Feature | Description |
|---------|-------------|
| Centralized dashboard | Single interface for dev tools, CI/CD, APIs, monitoring, docs |
| Learning paths | Structured tutorials and onboarding steps |
| Plugins and integrations | Verified dynamic plugins; Tekton, GitOps, Nexus, JFrog, OCP integrations |
| RBAC | Role-based access control with enterprise security permissions |
| Software catalog | Central inventory for services, APIs, libraries with ownership and health |
| Software templates | Preconfigured templates for CI/CD, runtime, and security |
| TechDocs | Markdown-based documentation alongside code with search |
| Scalability | Horizontal scaling with stateless backend design |

## System Architecture

RHDH uses a three-layer client-server architecture.

### Frontend (Client)

Browser-based single-page application (SPA). Communicates with the backend
exclusively using REST API calls. Used to browse the Software Catalog, interact
with plugins, and connect to external integrations.

### Backend (Service Layer)

Provides REST API endpoints for the frontend. Manages the Software Catalog and
handles authentication. Stateless design allows horizontal scaling by running
multiple instances behind a load balancer.

All persistent state is externalized to PostgreSQL:
- Catalog entities
- Task history
- Session data (database-backed session store)

### External Data Dependencies

**PostgreSQL (required):**
- Stores indexed catalog entities, profiles, authentication data, backend state.
- For production: configure with high availability (primary-replica replication).
- If using catalog providers exclusively, the database acts as an indexed cache
  and can be repopulated from external sources (Git, CI/CD).

**Redis Cache (optional):**
- Shared logical cache across backend instances.
- Improves performance for rendered TechDocs and catalog entities.
- Default in-memory cache is suitable only for single-instance deployments.
- Redis required for production multi-instance deployments.

If Redis fails: slower response times, increased DB load, but no impact on
authentication or core functionality.

## Deployment Method Comparison

### Helm Chart

- Deploys across multiple Kubernetes platforms (EKS, GKE, AKS).
- Maximum portability.
- Simplest initial setup; fewer deployment steps.
- Full control over update timing; manual testing in stages.
- Direct access to Kubernetes resources.
- Full visibility into generated manifests.

### Operator

- Primarily for OpenShift with OLM.
- Automated update availability through subscription channels.
- Continuous reconciliation of desired state.
- Declarative configuration through custom resources.
- Validation and reconciliation by the Operator.
- Standardized deployment patterns.

Both installation methods are fully supported by Red Hat.

## High Availability

### Backend Scalability

- Deploy 2+ backend instances for basic HA.
- Configure a load balancer (OpenShift Routes, K8s Ingress, cloud LB).
- Enable health checks for load balancer probing.
- Disable session affinity (sticky sessions) — database-backed sessions allow
  any instance to serve any request.

### Database HA

PostgreSQL outage renders the deployment non-functional. For production,
configure primary-replica replication. If using catalog providers exclusively,
disaster recovery backups are not required since catalog data can be
repopulated from external sources.

### Cache HA (Optional)

Configure Redis with high availability:
- Redis Sentinel for small deployments.
- Redis Cluster for larger deployments.

## Sizing Requirements

### Component Sizing

| Component | CPU | Memory | Storage | Replicas |
|-----------|-----|--------|---------|----------|
| RHDH application | 4 vCPU | 16 GB | 2 GB | 2+ |
| RHDH database | 2 vCPU | 8 GB | 20 GB | 3+ |
| RHDH Operator | 1 vCPU | 1500 Mi | 50 Mi | 1+ |

### Scale-Based Sizing (External PostgreSQL)

| Scale | Entities | Concurrent Users | vCPU | Memory | Storage | Replicas | DB HA |
|-------|----------|-------------------|------|--------|---------|----------|-------|
| Small | up to 5K | up to 50 | 2 | 8 GiB | 50 GiB | 1 | 1 primary |
| Mid | 5-20K | 50-150 | 4 | 16 GiB | 100 GiB | 2 | 1 primary + 1 standby |
| Large | 20-50K | 150-400 | 8 | 32 GiB | 200 GiB | 2-3 | 1 primary + 1 sync standby |
| Enterprise | 50-150K | 400-800 | 16 | 64 GiB | 500 GiB | 3+ | 1 primary + 1 sync + 1 async |

### PostgreSQL Tuning Parameters

| Scale | Memory | shared_buffers | effective_cache_size |
|-------|--------|----------------|----------------------|
| Small | 8 GiB | 2 GB | 4 GB |
| Mid | 16 GiB | 4 GB | 8 GB |
| Large | 32 GiB | 8 GB | 16 GB |
| Enterprise | 64 GiB | 16 GB | 32 GB |

Set `shared_buffers` to approximately 1/4 of allocated DB memory and
`effective_cache_size` to approximately 1/2 of allocated DB memory.

An external PostgreSQL instance is recommended for production deployments.

## Integrations

### Red Hat OpenShift Container Platform

- Operators for application lifecycle management.
- Access to service mesh, serverless, GitOps, distributed tracing.
- Pipelines and GitOps plugins for cloud-native workflows.

### Red Hat Advanced Developer Suite - Secure Supply Chain (RHADS - ssc)

Manages the outer loop (code scanning, image building, vulnerability
detection, deployment). Includes:
- Red Hat Trusted Artifact Signer (TAS) for code integrity.
- Red Hat Trusted Profile Analyzer (TPA) for automated SBOMs.
- Red Hat Advanced Cluster Security (ACS) for vulnerability scanning.

### Extending Backstage with RHDH

- Enhanced search aggregating data from CI/CD, cloud providers, source control.
- Centralized software catalog for applications, APIs, and resources.
- Automation through open-source plugins.
- Simplified TechDocs with Markdown and GitHub integration.

## Supported Platforms

See the Red Hat Developer Hub Life Cycle page for current platform
compatibility. As of RHDH 1.10:
- OpenShift Container Platform 4.21 and Kubernetes 1.34 are supported.

## Support Resources

- Red Hat Knowledgebase for technical support articles.
- Create support cases via Red Hat Customer Portal (product: Red Hat Developer
  Hub, select appropriate version).
- RHDH `must-gather` tool collects diagnostic data: platform information,
  deployment configs, application logs, routes/ingress, namespace state.
- Available on OCP 4.18+ via `oc adm must-gather` and on Kubernetes platforms
  (AKS, EKS, GKE) via Helm chart deployment.
