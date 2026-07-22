# Trusted Enterprise AI Development Platform

Every enterprise adopting AI-assisted development must answer three foundational questions — and each one maps to a platform capability that Red Hat delivers.

## Where Do We Run It?

**Red Hat Hybrid Cloud Platform.** Before AI models can serve developers, they need infrastructure that runs consistently everywhere: on-premises, at the edge, across multiple clouds. Red Hat OpenShift is an open, unified platform designed to build, manage, and scale applications — containers, virtual machines, and AI models — from a single control plane. It provides the enterprise Kubernetes foundation: identity, RBAC, networking, routing, scheduling, storage integration, monitoring, and GitOps patterns that make platform state reproducible and auditable.

The hybrid cloud platform is the first answer because it removes the location constraint. Organizations choose where workloads run based on data sovereignty, latency, cost, and regulation — not based on infrastructure limitations.

## How Do We Serve And Govern AI?

**Red Hat Private AI Platform.** Running AI models is not enough. Enterprises need to retain data sovereignty, control costs, enforce access policy, and operate at scale — without scattering credentials and endpoints across teams. Red Hat OpenShift AI is an enterprise-grade MLOps and GenAIOps platform that builds, tunes, and deploys AI models securely on-premises or across a hybrid cloud. It offers flexibility and consistency to build, deploy, and manage AI at scale across any hardware, addressing data constraints, privacy, security, and cost control.

Centered around open-source LLMs and AI agents, it lets companies serve private models inside the platform boundary while governing approved external models through a centralized Models-as-a-Service layer — one access point where platform teams control identity, API keys, subscriptions, rate limits, token limits, quotas, telemetry, and model lifecycle.

## How Do Developers Consume It?

**Red Hat Enterprise Application Platform.** An application platform is an integrated set of tools and services for developing, testing, deploying, and managing software through its entire lifecycle — not just one phase. It comprises everything developers need to build and run both applications and AI: infrastructure management for scalability, CI/CD pipelines with quality gates, monitoring, service mesh, APIs, GitOps, runtimes, security tooling, and developer portals that provide self-service access to all of it.

Red Hat delivers this through the Advanced Developer Suite: Developer Hub for golden-path templates and software catalog, OpenShift Dev Spaces for managed cloud workspaces, OpenShift Pipelines for trusted delivery with provenance, and Migration Toolkit for Applications for modernization workflows. Every developer tool in this demo — from IDE assistants to autonomous migration agents — enters through the portal and exits through the pipeline. *Self-service in, trusted delivery out.*

## The Demo: An AI Development Maturity Ladder

With the three platform pillars in place, this workshop demonstrates a progressive developer journey. Developers do not arrive at autonomous AI workflows in one step — and tooling that skips the journey gets rejected or misused. The demo structures the developer experience as an **AI development maturity ladder**, with familiar tools at each rung, every one consuming models through the same governed platform:

| Rung | Developer experience | Tooling |
|------|----------------------|---------|
| **Assisted** (060) | First one-shot prompts in the IDE — and their limits | Dev Spaces + Kilo Code via MaaS |
| **Agentic** (070) | Enterprise standards as reusable skills and specs that agents follow and improve | OpenCode + AGENTS.md + skills |
| **Autonomous** (080) | Multi-agent legacy migration with human review gates | MigIQ (MTA + Developer Lightspeed) |

Each rung deliberately exposes its own limits to motivate the next: one-shot prompting fails on project standards, which motivates skills and specs; skill-guided agents motivate autonomous multi-agent workflows — and every step lands on the same platform rails.

The workshop does not claim regulatory compliance. It shows controls and boundaries that help architects design AI-enabled development platforms for privacy-sensitive, sovereignty-sensitive, and regulated environments.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ENTERPRISE APPLICATION PLATFORM                                            │
│                                                                             │
│  Developer Hub · Dev Spaces · CI/CD Pipelines · Migration Toolkit           │
│  Golden-path templates · Quality gates · Software catalog · TechDocs        │
├─────────────────────────────────────────────────────────────────────────────┤
│  PRIVATE AI PLATFORM                                                        │
│                                                                             │
│  OpenShift AI · Model Serving (vLLM) · Model Registry · GenAI Studio        │
│  Models-as-a-Service · GPU Scheduling (Kueue) · Model Observability         │
│  AI Gateway · Usage Metrics · Token limits · API keys · Telemetry           │
├─────────────────────────────────────────────────────────────────────────────┤
│  HYBRID CLOUD PLATFORM                                                      │
│                                                                             │
│  Red Hat OpenShift · Kubernetes · Identity & RBAC · Networking & Routing    │
│  Storage (ODF) · Monitoring · GitOps (Argo CD) · GPU Infrastructure         │
│  Scheduling · Certificate Management · Node Management                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

The three layers work together as a single governed stack. Developers interact with the top layer — portals, workspaces, and AI coding assistants. Their prompts and code flow through the middle layer where models are served, access is governed, and usage is metered. Everything runs on the bottom layer where infrastructure, identity, networking, and state are managed consistently across hybrid cloud environments.

The central design choice: developers and their tools never connect directly to scattered model endpoints. They connect through Models-as-a-Service, where platform teams publish approved model choices and enforce access policy — one governed gateway for every AI consumer.

## What The Demo Shows

The demo follows an eight-stage flow organized in two parts.

**Part 1: Building the platform (GitOps-driven)**

Stages 010–050 construct the three platform layers declaratively — every resource reconciled from Git by Argo CD.

| Stage | Intent |
|-------|--------|
| [010 - OpenShift AI Platform Foundation](stages/010-openshift-ai-platform-foundation/README.md) | Establish the AI control plane: operator, dashboard, model registry, identity, and observability |
| [020 - GPU Infrastructure for Private AI](stages/020-gpu-infrastructure-private-ai/README.md) | Provision GPU workers and quota-controlled scheduling for model workloads |
| [030 - Private Model Serving](stages/030-private-model-serving/README.md) | Serve private LLMs with vLLM inside the platform boundary |
| [040 - Governed Models-as-a-Service](stages/040-governed-models-as-a-service/README.md) | Expose private and external models through a governed MaaS gateway with API keys, rate limits, and telemetry |
| [050 - Advanced Application Platform](stages/050-advanced-app-platform/README.md) | Add the developer-facing layer: Developer Hub, Dev Spaces, Pipelines, quality gates, and provenance |

**Part 2: Climbing the AI development maturity ladder (use-case-driven)**

Stages 060–080 are developer workflow exercises that consume the platform built above. Each enters through the developer portal, uses governed models from MaaS, and exits through the CI pipeline.

| Stage | Intent |
|-------|--------|
| [060 - AI-Assisted Development](stages/060-ai-assisted-development/README.md) | One-shot AI coding in the IDE — and its limits without project standards |
| [070 - AI-Agentic Development](stages/070-ai-agentic-development/README.md) | Spec-driven development where agent-executable standards guide every change |
| [080 - AI-Autonomous Migration](stages/080-ai-autonomous-migration/README.md) | Multi-agent legacy migration with human review gates |

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the enterprise Kubernetes foundation: identity, RBAC, networking, routing, scheduling, storage integration, monitoring, and GitOps patterns. Red Hat OpenShift AI adds the AI control plane for model serving, GenAI Studio, model registry, and MaaS. Red Hat Advanced Developer Suite capabilities bring workspaces, modernization, portal discovery, and AI-assisted developer experiences into the same platform story.

Open-source models and AI-assisted tooling make the developer experience possible. Models such as Nemotron, Qwen, and MiniMax run locally on the platform through vLLM, keeping prompts and code inside the trust boundary. [Kilo Code](https://kilocode.ai/) is an open-source AI coding assistant that runs inside the IDE, providing one-shot prompt-and-edit workflows — the starting point of the maturity ladder. [OpenCode](https://opencode.ai/) is a terminal-based AI coding agent that goes further: it reads `AGENTS.md` (a project-level file that organizes reusable skills) to apply enterprise conventions on every change without longer prompts. [Spec-kit](https://github.com/adnan-drina/spec-kit) completes the agentic workflow — a lightweight spec-driven development tool that turns natural-language requirement briefs into structured specifications the agent implements against, closing the loop between what the team wants and what the agent builds. All three tools consume models exclusively through the governed MaaS gateway, so platform teams retain full visibility and control regardless of which tool or model a developer chooses.

Red Hat's role in this architecture is integration, lifecycle, support posture, and operational consistency — turning open-source building blocks into a governed enterprise platform.

## Running The Workshop

The READMEs explain the architecture. Use the commands below only in a prepared OpenShift environment.

**Environment sizing (required).** The full stack (RHOAI + ODF + GPU + MaaS + model serving) puts heavy, sustained load on the control plane. Provision `m6a.4xlarge`-class nodes (16 vCPU / 64 GiB) for the control plane *and* the CPU workers. The `m6a.xlarge` (4 vCPU / 16 GiB) control plane is **not** sufficient: kube-apiserver exhausts the node's CPU/memory and masters fail one after another. GPU nodes are sized by accelerator (e.g. `g6e.2xlarge`) and are exempt. Every stage's `deploy.sh` runs `scripts/require-node-sizing.sh` first and refuses to start on undersized nodes.

```bash
git clone https://github.com/adnan-drina/rhoai3-coding-demo.git
cd rhoai3-coding-demo
```

**Environment configuration (required).** Before deploying any stage, copy the environment template and fill in the values for your target cluster. The `.env` file drives Git source references for Argo CD, cluster safety guards, demo persona credentials, external model API keys, and Stage 050 delivery-chain integrations (GitHub App, PAT, Quay robot account). Deploy scripts source this file automatically — deployment will fail or produce incomplete results without it.

```bash
cp env.example .env
# Edit .env — fill in RHOAI_EXPECTED_API_SERVER, credentials, and API keys
oc login --token=<token> --server=<api>
./scripts/validate-stage-flow.sh
```

**Deploy the platform stages in order.** Stage 010 bootstraps OpenShift GitOps itself (declarative overlays in `gitops/bootstrap/`) before handing the platform to Argo CD.

```bash
./stages/010-openshift-ai-platform-foundation/deploy.sh
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/030-private-model-serving/deploy.sh
./stages/040-governed-models-as-a-service/deploy.sh
./stages/050-advanced-app-platform/deploy.sh
```

**Validate the developer workflow stages.** Stages 060–080 are workflow-only: all of their infrastructure (workspaces, pipelines, quality gates, the MigIQ stack) is deployed by Stage 050. Each keeps a read-only `validate.sh` for its demo prerequisites:

```bash
./stages/060-ai-assisted-development/validate.sh
./stages/070-ai-agentic-development/validate.sh
./stages/080-ai-autonomous-migration/validate.sh
```

For deployment detail, validation strategy, and recovery procedures, see:

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

Stage 070 teaches agentic development with `AGENTS.md` and reusable skills. This repository is maintained the same way: [`AGENTS.md`](AGENTS.md) is the agent entry point, and [`.agents/`](.agents/README.md) holds tool-neutral rules, doc-grounded skills for every Red Hat product in the demo, and safety hooks (including a cluster guard that blocks mutating `oc`/`kubectl` commands against unintended clusters). Tool-specific directories such as `.cursor/` contain only thin bridge files that point at the shared layer.

## Demo Personas

| User | Purpose |
|------|---------|
| `ai-admin` | Platform administrator persona for OpenShift AI, MTA, portal, and model administration |
| `ai-developer` | Developer persona consuming workspaces, models, and modernization workflows |
| `kubeadmin` | Cluster administrator for platform setup and recovery |

## Red Hat Products Demonstrated

| Red Hat product | Role in the workshop |
|-----------------|----------------------|
| [Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift) | Kubernetes application platform for identity, RBAC, networking, routing, scheduling, monitoring, and operations |
| [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai) | AI platform for model serving, GenAI Studio, model registry, and MaaS |
| [Red Hat Advanced Developer Suite](https://www.redhat.com/en/products/advanced-developer-suite) | Product family for the developer productivity layer represented by Dev Spaces, MTA, Developer Hub, and Developer Lightspeed |

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
