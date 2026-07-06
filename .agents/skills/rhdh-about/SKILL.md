---
name: rhdh-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when explaining Red Hat Developer Hub concepts, architecture, software
  catalog, Backstage foundations, developer portal capabilities, sizing
  requirements, deployment method comparison, high availability, integrations,
  or supported platforms from the official RHDH 1.10 about guide. Do NOT use
  for installing (use rhdh-install), configuring (use rhdh-configure),
  extending with plugins or dynamic plugins (use rhdh-plugins), or access
  control and RBAC (use rhdh-rbac).
---

# RHDH About

Use this skill to ground Red Hat Developer Hub conceptual guidance in the
official RHDH 1.10 about guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## What Is Red Hat Developer Hub

Red Hat Developer Hub (RHDH) is an enterprise-grade internal developer portal
(IDP) built on upstream Backstage 1.49.4. It provides a customizable web-based
interface that centralizes access to source code repositories, CI/CD pipelines,
APIs, documentation, and runtime environments.

RHDH is designed for cloud-native environments including Red Hat OpenShift
Container Platform, supported Kubernetes platforms (EKS, GKE, AKS), and hybrid
infrastructure.

## Key Features

- **Software Catalog**: central inventory to search, view, and manage services,
  APIs, and libraries with ownership, metadata, and component health tracking.
- **Software Templates**: preconfigured templates for CI/CD, runtime, and
  security to standardize project setup.
- **TechDocs**: create, store, and view technical documentation alongside code.
- **RBAC**: role-based access control with enterprise security permissions.
- **Learning Paths**: structured tutorials and onboarding steps.
- **Dynamic Plugins**: extend RHDH with verified plugins without downtime.
- **Scalability**: horizontal scaling with stateless backend design.

## Architecture

RHDH uses a three-layer architecture:

- **Frontend**: browser-based SPA communicating with backend via REST API.
- **Backend**: stateless service layer providing REST API endpoints; scales
  horizontally behind a load balancer; externalizes all state to PostgreSQL.
- **Data layer**: PostgreSQL (required) for persistence; Redis (optional) as
  shared logical cache for multi-instance deployments.

## Deployment Methods

Two fully supported installation methods:

- **Helm chart**: maximum portability across Kubernetes platforms; manual
  update control; direct access to Kubernetes resources.
- **Operator**: OpenShift-native with OLM; automated update availability via
  subscription channels; continuous reconciliation; declarative configuration
  through custom resources.

## Sizing Requirements

| Scale | Entities | Concurrent Users | App CPU | App Memory | DB Storage |
|-------|----------|-------------------|---------|------------|------------|
| Small | up to 5K | up to 50 | 2 vCPU | 8 GiB | 50 GiB |
| Mid | 5-20K | 50-150 | 4 vCPU | 16 GiB | 100 GiB |
| Large | 20-50K | 150-400 | 8 vCPU | 32 GiB | 200 GiB |
| Enterprise | 50-150K | 400-800 | 16 vCPU | 64 GiB | 500 GiB |

Base component requirements: application (4 vCPU, 16 GB), database (2 vCPU,
8 GB, 20 GB storage), operator (1 vCPU, 1500 Mi).

## High Availability

- Deploy 2+ backend instances with load balancing.
- Disable session affinity (database-backed sessions).
- Configure PostgreSQL HA (primary-replica replication).
- Optional Redis cache for multi-instance consistency.

## Integrations

- **Red Hat OpenShift Container Platform**: operators, service mesh, serverless,
  GitOps, distributed tracing, pipelines plugins.
- **RHADS - secure supply chain**: code scanning, image building, vulnerability
  detection, TAS, TPA, ACS integration.
- **Backstage ecosystem**: enhanced search, centralized catalog, open-source
  plugins, simplified TechDocs.

## Supported Platforms

See the RHDH Life Cycle page for current platform compatibility. OCP 4.21 and
Kubernetes 1.34 are supported as of RHDH 1.10.

## Support

- Red Hat Knowledgebase for technical articles.
- Support cases via Red Hat Customer Portal (product: Red Hat Developer Hub).
- `must-gather` tool for collecting diagnostic data from RHDH deployments.

## Workflow

1. Read `references/official-doc-extraction.md` for detailed concepts.
2. Identify the relevant concept (architecture, sizing, HA, integrations).
3. Use sizing tables to plan infrastructure.
4. Use deployment method comparison for installation decisions.
5. Validate against `references/source-capture.md` boundaries.

## Related Skills

- `rhdh-release-notes` — RHDH 1.10 new features, fixes, known issues.
- `rhdh-preview-features` — Technology Preview and Developer Preview features.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
