# Step 01: Trusted OpenShift AI Platform Foundation

## Why This Matters

Enterprise AI adoption fails when every team builds its own isolated stack. Developers, data scientists, and platform teams need a shared foundation for identity, model lifecycle, observability, and operational consistency.

This step establishes Red Hat OpenShift AI as that foundation. Before the workshop can show private models, MaaS, AI coding assistants, modernization, or a developer portal, it needs a trusted AI control plane running on OpenShift.

## What This Step Adds

Step 01 installs and configures the AI platform layer:

```text
OpenShift AI platform foundation
+-- Red Hat OpenShift AI Operator
+-- DataScienceCluster and DSCInitialization
+-- Dashboard and GenAI Studio configuration
+-- Llama Stack and KServe platform components
+-- Model Registry with PostgreSQL metadata storage
+-- Demo users and RHOAI groups
+-- Hardware profiles for CPU and NVIDIA L4 GPU workloads
+-- User workload monitoring and CA trust configuration
+-- Supporting platform dependencies
```

The important design choice is scope. The platform is configured for the capabilities this workshop needs: GenAI Studio, model serving, model registry, dashboard access, identity, monitoring, and hardware profiles. It is not trying to enable every possible AI feature at once.

## What To Notice In The Demo

When presenting this step, focus on the platform outcome rather than the installation mechanics.

Show that OpenShift AI is present as the AI control plane. Show the demo users and groups. Show GenAI Studio and the model registry foundation. Show hardware profiles that make accelerator choices visible before any model is deployed.

The key takeaway is that enterprise AI starts with shared platform services, not with a model endpoint.

## How Red Hat And Open Source Make It Work

OpenShift provides identity, RBAC, namespaces, scheduling, networking, monitoring, and GitOps integration. OpenShift AI adds AI-specific platform capabilities such as the dashboard, model serving integration, model registry, and GenAI Studio.

This combination matters because AI platforms need both AI-specific features and ordinary enterprise platform controls. The value is in the integration: AI workloads run on the same trusted Kubernetes foundation as other enterprise applications.

## Red Hat Products Used

- **Red Hat OpenShift AI** is the main product demonstrated in this step. It provides the AI dashboard, DataScienceCluster, model serving integration, GenAI Studio, and model registry experience.
- **Red Hat OpenShift** provides the underlying platform services: authentication, namespaces, routes, RBAC, scheduling, monitoring, and storage integration.
- **OpenShift Serverless** and **Service Mesh** provide platform services used by OpenShift AI serving components.

## Open Source Projects To Know

- [Open Data Hub](https://opendatahub.io/) is the upstream community foundation for many OpenShift AI capabilities.
- [KServe](https://kserve.github.io/website/) provides Kubernetes-native model serving concepts used by OpenShift AI.
- [Model Registry](https://github.com/opendatahub-io/model-registry) provides model metadata and lifecycle foundations.
- Kubernetes and OpenShift provide the identity, scheduling, networking, and operational substrate that make the AI layer enterprise-ready.

## Why This Is Worth Knowing

This step teaches the first architectural principle of the workshop: AI should be delivered as a platform capability. Once identity, observability, dashboard access, model metadata, and hardware profiles are in place, the rest of the workshop can build on a consistent foundation.

For regulated organizations, that consistency matters. A platform gives teams a place to define controls and operating practices before developers start sending prompts to models.

## Where This Fits In The Full Platform

| Later step | What it gets from Step 01 |
|------------|---------------------------|
| Step 02 | Hardware profile context and platform readiness |
| Step 03 | GenAI Studio, Playground, model registry, and dashboard integration |
| Step 04 | Shared OpenShift identity for developer workspaces |
| Step 05 | Demo users and groups used by MaaS and MTA workflows |
| Step 06 | Platform identity and catalog context for Developer Hub |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-01-rhoai-platform/deploy.sh
./steps/step-01-rhoai-platform/validate.sh
```

Manifests: [`gitops/step-01-rhoai-platform/base/`](../../gitops/step-01-rhoai-platform/base/)

## References

- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI 3.3 installation guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html-single/installing_and_uninstalling_openshift_ai_self-managed/index)
- [Red Hat OpenShift AI 3.3 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

## Next Step

[Step 02: GPU Infrastructure](../step-02-gpu-infra/README.md) adds the accelerator layer required for private model inference.
