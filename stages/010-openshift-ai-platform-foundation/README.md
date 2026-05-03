# Stage 010: Trusted OpenShift AI Platform Foundation

## Why This Matters

Enterprise AI adoption becomes difficult to govern when every team assembles its own notebooks, model endpoints, credentials, and dashboards. Platform teams need a shared control plane before developers and AI engineers start consuming models from multiple tools and trust boundaries.

This stage establishes that foundation with Red Hat OpenShift AI on OpenShift. It creates the place where model access, model metadata, dashboard access, user identity, monitoring, and accelerator choices can be managed as platform capabilities rather than one-off project setup.

## Architecture

![Stage 010 layered capability map](../../docs/assets/architecture/stage-010-capability-map.svg)

## What This Stage Adds

This stage adds the shared Red Hat OpenShift AI foundation for the workshop.

- An OpenShift AI 3.3 control plane installed through the Red Hat OpenShift AI Operator.
- Core OpenShift AI services for dashboard access, GenAI Studio, model serving, model registry, KServe, Llama Stack, and MaaS-related capabilities.
- A PostgreSQL-backed model registry so model metadata can be managed as a platform asset.
- Demo users, OpenShift groups, and OpenShift OAuth integration for consistent identity across platform surfaces.
- CPU and NVIDIA L4 hardware profiles that make workload sizing and accelerator choices explicit.
- User workload monitoring and CA trust configuration for platform observability and secure internal communication.

The scope is intentional: this stage turns on the services needed for the demo platform without trying to enable every possible OpenShift AI feature.

## What To Notice And Why It Matters

Stage 010 establishes Red Hat OpenShift AI as the shared control plane for enterprise AI on Red Hat OpenShift. The dashboard, GenAI Studio, model registry, demo identities, OpenShift groups, hardware profiles, monitoring, and model-serving prerequisites are in place before any model endpoint is exposed.

The essential proof point is governed platform readiness:

- Platform teams get one OpenShift AI entry point for model discovery, metadata, dashboard access, and workload choices.
- OpenShift OAuth, groups, and RBAC provide the identity foundation that regulated environments need before teams consume AI services.
- Hardware profiles make CPU and NVIDIA L4 accelerator options explicit, so workload placement starts from approved platform choices rather than local assumptions.

This matters because regulated European enterprises need a repeatable AI platform that can run consistently across hybrid cloud environments while preserving control over identity, access, metadata, and infrastructure choices. Starting with the platform foundation makes privacy, sovereignty, and operational governance part of the architecture rather than a retrofit after model adoption begins.

## How Red Hat And Open Source Make It Work

OpenShift provides the operational substrate: identity, RBAC, namespaces, scheduling, networking, routes, storage integration, monitoring, and GitOps reconciliation. OpenShift AI adds the AI platform layer: dashboard access, data science projects, model serving integration, model registry, GenAI Studio, and components that later support MaaS.

The open source foundation comes from Kubernetes, Open Data Hub, KServe, Model Registry, and related serving projects. Red Hat packages and integrates those capabilities through operators and supported platform patterns so AI workloads can use the same identity, access, monitoring, and lifecycle controls as other OpenShift workloads.

## Red Hat Products Used

- **Red Hat OpenShift AI** is the main product demonstrated in this stage. It provides the AI dashboard, DataScienceCluster, model serving integration, GenAI Studio, and model registry experience.
- **Red Hat OpenShift** provides the underlying platform services: authentication, namespaces, routes, RBAC, scheduling, monitoring, and storage integration.
- **OpenShift Serverless** and **Service Mesh** provide platform services used by OpenShift AI serving components.

## Open Source Projects To Know

- [Open Data Hub](https://opendatahub.io/) is the upstream community foundation for many OpenShift AI capabilities.
- [KServe](https://kserve.github.io/website/) provides Kubernetes-native model serving concepts used by OpenShift AI.
- [Model Registry](https://github.com/opendatahub-io/model-registry) provides model metadata and lifecycle foundations.
- Kubernetes and OpenShift provide the identity, scheduling, networking, and operational substrate that make the AI layer enterprise-ready.

## Where This Fits In The Full Platform

| Later stage | What it gets from Stage 010 |
|------------|---------------------------|
| Stage 020 | Platform readiness before accelerator capacity is added |
| Stage 030 | Data science project, model registry, and model serving integration |
| Stage 040 | Demo users, groups, and MaaS-related platform components |
| Stage 070 | Shared OpenShift identity for developer workspaces |
| Stage 090 | Platform identity and catalog context for Developer Hub |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/010-openshift-ai-platform-foundation/deploy.sh
./stages/010-openshift-ai-platform-foundation/validate.sh
```

Manifests: [`gitops/stages/010-openshift-ai-platform-foundation/base/`](../../gitops/stages/010-openshift-ai-platform-foundation/base/)

## References

- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI 3.3 installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [Red Hat OpenShift AI 3.3 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Next Stage

[Stage 020: GPU Infrastructure for Private AI](../020-gpu-infrastructure-private-ai/README.md) adds the accelerator layer required for private model inference.
