# Trusted Enterprise AI Development Platform on Red Hat OpenShift AI

## Why This Workshop Exists

AI-assisted development is now a normal expectation for software teams. But enterprises adopting it face two problems at once, and solving only one of them fails:

**The control problem.** The question is not whether AI can help with code, tests, documentation, or modernization — it is how to offer that help without losing control of source code, credentials, model access, cost, telemetry, and operational risk. This workshop answers with a governed platform pattern:

- private models run on Red Hat OpenShift for sensitive workloads;
- approved external models are exposed only through a governed access layer;
- platform teams control identity, API keys, subscriptions, rate limits, token limits, quotas, telemetry, and lifecycle;
- GitOps keeps platform state reproducible.

**The maturity problem.** Developers do not arrive at autonomous AI workflows in one step — and tooling that skips the journey gets rejected or misused. This workshop structures the developer experience as an **AI development maturity ladder**, with familiar tools at each rung, every one consuming models through the same governed platform:

| Rung | Developer experience | Tooling |
|------|----------------------|---------|
| **Assisted** (050) | First one-shot prompts in the IDE — and their limits | Dev Spaces + Continue via MaaS |
| **Agentic** (060) | Enterprise standards as reusable skills that agents follow and improve | OpenCode + AGENT.md + skills |
| **Autonomous** (070) | Multi-agent legacy migration with human review gates | MTA + Developer Lightspeed |
| **Trusted delivery** (080) | Provenance, signing, and SBOMs for AI-generated changes | OpenShift Pipelines + Trusted Artifact Signer |
| **Self-service** (090) | The whole journey as one discoverable portal | Developer Hub + Lightspeed for RHDH |

Each rung deliberately exposes its own limits to motivate the next: one-shot prompting fails on project standards, which motivates skills; skill-guided agents motivate autonomous workflows; autonomy demands supply-chain trust; and everything lands in the portal as the end-user experience.

The workshop does not claim regulatory compliance. It shows controls and boundaries that help architects design AI-enabled development platforms for privacy-sensitive, sovereignty-sensitive, and regulated environments.

## Architecture

![RHOAI coding demo layered capability map](docs/assets/architecture/rhoai-capability-map.svg)

## What We Are Building

Underneath the ladder sits the governed platform foundation that every rung consumes. The demo builds it on Red Hat OpenShift:

- a Red Hat OpenShift AI foundation with dashboard access, GenAI Studio, model registry, model serving, MaaS, shared identity, and monitoring;
- GPU infrastructure for private AI with NVIDIA GPU enablement, Red Hat build of Kueue, OpenShift Custom Metrics Autoscaler readiness, and observability;
- private model serving with Red Hat AI Inference Server, vLLM, llm-d, and OpenAI-compatible APIs;
- governed Models-as-a-Service access for private and approved external models;
- developer workflows through Red Hat OpenShift Dev Spaces, Continue, OpenCode, Migration Toolkit for Applications, Developer Lightspeed, and Red Hat Developer Hub.

The central design choice is simple: consumers do not connect directly to scattered model endpoints. They connect through MaaS, where platform teams publish approved model choices and enforce access policy.

## What The Demo Shows

The executable platform path is the nine-stage flow in [`flows/default.yaml`](flows/default.yaml): stages 010-040 build the governed platform foundation, and stages 050-090 climb the maturity ladder introduced above.

Each developer-arc stage README (050-090) carries a **Demo Script** section in Know/Show form — the business beat to say, the exact clicks to show, and the deliberately scripted fail-forward moments — so the demo can be delivered by someone who did not build it.

| Stage | Capability | Why it matters |
|-------|------------|----------------|
| [010 - OpenShift AI Platform Foundation](stages/010-openshift-ai-platform-foundation/README.md) | OpenShift AI control plane, identity, dashboard, model registry, and platform services | Trusted AI starts with a managed platform foundation, not isolated notebooks or unmanaged credentials |
| [020 - GPU Infrastructure for Private AI](stages/020-gpu-infrastructure-private-ai/README.md) | NVIDIA GPU enablement, Red Hat build of Kueue, quotas, hardware profiles, and observability | Private AI needs scarce accelerator capacity to be scheduled, shared, and reviewed |
| [030 - Private Model Serving](stages/030-private-model-serving/README.md) | Local LLMs served with OpenAI-compatible APIs | Sensitive source code and modernization context need a private inference path |
| [040 - Governed Models-as-a-Service](stages/040-governed-models-as-a-service/README.md) | MaaS access with subscriptions, API keys, token limits, rate limits, telemetry, approved external models, and platform-managed MCP context | Model serving becomes a platform service when access, external use, and tool context are centralized |
| [050 - AI-Assisted Development](stages/050-ai-assisted-development/README.md) | Dev Spaces workspaces with Continue via MaaS and the one-shot vibe-coding exercise | The most basic form of AI-assisted coding shows both the possibilities and the limits that motivate agentic workflows |
| [060 - Agentic Development](stages/060-ai-agentic-development/README.md) | The agentic workspace: OpenCode with AGENT.md and reusable skills that encode enterprise Quarkus standards | Internal development guidelines become living assets that agents follow and improve |
| [070 - Autonomous Application Migration](stages/070-ai-autonomous-migration/README.md) | MTA and Developer Lightspeed analysis plus a multi-agent Spring Boot to Quarkus migration through MaaS | Legacy backlogs need secure, affordable, reviewable autonomous migration |
| [080 - AI in Trusted Delivery](stages/080-ai-trusted-delivery/README.md) | OpenShift Pipelines and Trusted Artifact Signer base for provenance, signing, and SBOMs of AI-generated changes | Autonomous output needs supply-chain proof, not trust-me claims (base setup; implementation tracked in backlog) |
| [090 - AI Self-Service Portal](stages/090-ai-self-service-portal/README.md) | Developer Hub catalog, TechDocs, identity, and Developer Lightspeed for RHDH | The whole arc becomes one discoverable self-service experience |

Developer workflow use cases start with [Stage 050 - AI-Assisted Development (vibe-coding exercise)](stages/050-ai-assisted-development/README.md). Stages 010-040 are primarily for platform engineers building the trusted AI development platform; stages 050-090 shift to enterprise developers using that platform for governed coding, agentic development, modernization, delivery, and self-service. A recurring demo beat makes the ladder tangible: Stage 060 reruns Stage 050's one-shot coding task with a skills-guided agent so the audience sees the maturity jump directly. Additional developer workflow topics stay in the backlog until each has a concrete scope, artifacts, and validation path. See [Deferred developer workflow topics](BACKLOG.md#deferred-developer-workflow-topics).

## Why This Is Worth Knowing

The reusable pattern is larger than this repository. Enterprises need to answer practical questions before adopting AI development tools:

- Which model paths are approved for each data classification?
- Which users, teams, tools, and applications can access each model?
- Can sensitive source code stay inside the OpenShift platform boundary?
- Can approved external models be offered without distributing provider keys?
- Can usage be measured, limited, traced, and reviewed?
- Can modernization and portal workflows use AI without bypassing platform governance?

This demo treats AI assistance as a platform capability. Red Hat OpenShift AI supplies model serving and MaaS. Red Hat OpenShift supplies the application platform. Red Hat OpenShift Dev Spaces, MTA, Developer Lightspeed, and Developer Hub bring the governed model path into developer workflows.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the enterprise Kubernetes foundation: identity, RBAC, networking, routing, scheduling, storage integration, monitoring, and GitOps patterns. Red Hat OpenShift AI adds the AI control plane for model serving, GenAI Studio, model registry, and MaaS. Red Hat Advanced Developer Suite capabilities bring workspaces, modernization, portal discovery, and AI-assisted developer experiences into the same platform story.

Open source projects provide the building blocks: Open Data Hub and models-as-a-service for the upstream AI platform pattern, KServe and vLLM for inference, llm-d for distributed serving architecture, Gateway API with Kuadrant and Authorino for policy enforcement, Eclipse Che and DevWorkspace for workspaces, Continue and OpenCode for coding assistants, Konveyor and Kai for modernization, and Backstage for the developer portal.

Red Hat's role in this architecture is integration, lifecycle, support posture, and operational consistency across those pieces.

## Trust Boundaries

Private local models keep prompts and code inside the OpenShift platform boundary. Governed external models use centralized MaaS credentials, subscriptions, rate limits, token limits, and telemetry, but prompts are still processed by the external provider. MCP integrations have their own data boundary because tool context can expose cluster state, documents, chat data, web data, or actions against other systems. These boundaries support governance, traceability, documentation, and EU AI Act readiness; they do not replace legal review, data classification, human review, or production security assessment.

## Red Hat Products Demonstrated

| Red Hat product | Role in the workshop |
|-----------------|----------------------|
| [Red Hat Advanced Developer Suite](https://www.redhat.com/en/products/advanced-developer-suite) | Product family for the developer productivity layer represented by Dev Spaces, MTA, Developer Hub, and Developer Lightspeed |
| [Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift) | Kubernetes application platform for identity, RBAC, networking, routing, scheduling, monitoring, and operations |
| [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai) | AI platform for model serving, GenAI Studio, model registry, and MaaS |
| [Red Hat AI Inference Server](https://www.redhat.com/en/products/ai) | vLLM-based runtime used for private LLM serving |
| [Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops) | Argo CD based reconciliation of stage manifests |
| [Red Hat build of Kueue](https://docs.redhat.com/en/documentation/red_hat_build_of_kueue/1.0/html/overview/index) | Queueing, quota, and admission control for AI workloads |
| [Custom Metrics Autoscaler Operator for Red Hat OpenShift](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/nodes/automatically-scaling-pods-with-the-custom-metrics-autoscaler-operator) | Red Hat-supported KEDA integration for metric-driven autoscaling patterns |
| [Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces) | Managed cloud development workspaces |
| [Migration Toolkit for Applications](https://developers.redhat.com/products/mta) | Application inventory, static analysis, migration rules, and modernization workflow |
| [Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index) | AI-assisted modernization suggestions grounded in MTA findings |
| [Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub) | Enterprise developer portal, software catalog, and TechDocs surface |
| [Developer Lightspeed for Red Hat Developer Hub](https://developers.redhat.com/products/rhdh/developer-lightspeed) | AI-assisted portal experience |
| [Red Hat Connectivity Link](https://www.redhat.com/en/technologies/cloud-computing/connectivity-link) | Gateway and policy layer used in the MaaS governance path |
| [Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak) | Identity broker used by MTA and Developer Hub authentication flows |

## Open Source Projects You Will Meet

| Project | Where it appears | What it contributes |
|---------|------------------|---------------------|
| [Open Data Hub](https://opendatahub.io/) and [models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) | OpenShift AI and MaaS | Upstream AI platform and model access patterns |
| [KServe](https://kserve.github.io/website/) | Model serving | Kubernetes-native serving primitives |
| [vLLM](https://docs.vllm.ai/) | Private inference | Efficient LLM serving with OpenAI-compatible APIs |
| [llm-d](https://llm-d.ai/) | Distributed inference | Kubernetes-native distributed LLM serving architecture |
| [Gateway API](https://gateway-api.sigs.k8s.io/) | MaaS routing | Kubernetes-native API routing |
| [Kuadrant](https://kuadrant.io/) and [Authorino](https://www.authorino.io/) | MaaS policy | AuthN/AuthZ, rate limiting, token limiting, and protection patterns |
| [Kueue](https://kueue.sigs.k8s.io/) and [KEDA](https://keda.sh/) | GPUaaS | Queueing, quota, admission, and autoscaling primitives |
| [Eclipse Che](https://www.eclipse.org/che/) and [DevWorkspace](https://github.com/devfile/devworkspace-operator) | Dev Spaces | Cloud workspace orchestration |
| [Continue](https://www.continue.dev/) and [OpenCode](https://opencode.ai/) | Coding assistance | IDE and terminal AI coding workflows that can consume MaaS endpoints |
| [Konveyor](https://www.konveyor.io/) and [Kai](https://github.com/konveyor/kai) | MTA and Developer Lightspeed | Modernization analysis and AI-assisted remediation foundations |
| [Backstage](https://backstage.io/) and [TechDocs](https://backstage.io/docs/features/techdocs/) | Developer Hub | Software catalog and documentation publishing |

## Running The Workshop

The READMEs explain the architecture. Operators should use the commands below only in a prepared OpenShift environment.

```bash
git clone https://github.com/adnan-drina/rhoai3-coding-demo.git
cd rhoai3-coding-demo
cp env.example .env
oc login --token=<token> --server=<api>
./scripts/validate-stage-flow.sh
```

Stage 010 bootstraps OpenShift GitOps itself (declarative overlays in
`gitops/bootstrap/`) before handing the platform to Argo CD.

Deploy the implemented stages in order:

```bash
./stages/010-openshift-ai-platform-foundation/deploy.sh
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/030-private-model-serving/deploy.sh
./stages/040-governed-models-as-a-service/deploy.sh
./stages/050-ai-assisted-development/deploy.sh
./stages/060-ai-agentic-development/deploy.sh
./stages/070-ai-autonomous-migration/deploy.sh
./stages/080-ai-trusted-delivery/deploy.sh
./stages/090-ai-self-service-portal/deploy.sh
```

For deployment detail, validation strategy, and recovery procedures, use:

- [Documentation Index](docs/README.md)
- [Operations Guide](docs/OPERATIONS.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- [Backlog and Workaround Register](BACKLOG.md)

## Repository Map

```text
rhoai3-coding-demo/
|-- README.md
|-- AGENTS.md                        # Entry point for AI coding agents working on this repo
|-- BACKLOG.md                       # Workarounds, limitations, and deferred work
|-- CONTRIBUTING.md
|-- env.example
|-- flows/default.yaml               # Ordered source of truth for the demo flow
|-- scripts/                         # Shared helpers, validation, recovery
|-- .agents/                         # Tool-neutral shared agent guidance: rules, skills, hooks, references
|-- gitops/
|   |-- bootstrap/                   # Declarative OpenShift GitOps bootstrap (stage 010)
|   |-- argocd/app-of-apps/          # Argo CD Applications for stages 010-090
|   `-- stages/                      # GitOps source for stage manifests
|-- stages/                          # Stage READMEs and per-stage deploy/validate scripts
`-- docs/                            # Operations, troubleshooting, TechDocs, and governance docs
```

## This Repository Practices What It Demonstrates

Stage 060 teaches agentic development with `AGENT.md` and reusable skills. This repository is maintained the same way: [`AGENTS.md`](AGENTS.md) is the agent entry point, and [`.agents/`](.agents/README.md) holds tool-neutral rules, doc-grounded skills for every Red Hat product in the demo, and safety hooks (including a cluster guard that blocks mutating `oc`/`kubectl` commands against unintended clusters). Tool-specific directories such as `.cursor/` contain only thin bridge files that point at the shared layer.

## Demo Personas

| User | Purpose |
|------|---------|
| `ai-admin` | Platform administrator persona for OpenShift AI, MTA, portal, and model administration |
| `ai-developer` | Developer persona consuming workspaces, models, and modernization workflows |
| `kubeadmin` | Cluster administrator for platform setup and recovery |

## References

- [Red Hat AI](https://www.redhat.com/en/products/ai)
- [Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)
- [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)
- [Red Hat OpenShift AI 3.4 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/)
- [Red Hat OpenShift AI 3.4 MaaS documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Migration Toolkit for Applications 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [Red Hat Developer Hub 1.9 documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
