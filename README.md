# Trusted Enterprise AI Development Platform on Red Hat OpenShift AI

## Why This Workshop Exists

AI-assisted software development is becoming a normal expectation for engineering teams. The hard part for large enterprises is not whether AI can help write, explain, test, or modernize code. The hard part is how to make those capabilities available without losing control of source code, regulated data, model access, cost, and operational risk.

That question matters most in organizations with strict privacy, sovereignty, and governance requirements. Many teams, especially in regulated European industries, cannot simply paste enterprise code into uncontrolled public AI services. At the same time, they still want access to modern AI capabilities and, in some cases, approved frontier models for tasks where policy allows external processing.

This workshop shows a platform pattern for that tension:

- Private models run on OpenShift for sensitive workloads.
- Approved external models are exposed only through a governed access layer.
- Developers use familiar tools instead of learning model infrastructure.
- Platform teams control identity, access, rate limits, telemetry, and lifecycle.
- The same model access pattern powers coding assistance, modernization, and portal-driven self-service.

The goal is not to claim that every AI use case automatically satisfies a regulation. The goal is to show how Red Hat OpenShift AI, open source model infrastructure, and Models-as-a-Service can give enterprise architects the controls and choices needed to design trustworthy AI-enabled development platforms.

## What We Are Building

The workshop builds a complete AI-enabled development platform on Red Hat OpenShift:

```text
Developer experience
  Red Hat Developer Hub
  OpenShift Dev Spaces
  Continue and OpenCode
  MTA Developer Lightspeed
  RHOAI GenAI Studio and Playground

Governed model access
  Models-as-a-Service gateway
  Access policies and subscriptions
  API keys, quotas, rate limits, telemetry

Model choices
  Private local models on OpenShift
    - nemotron-3-nano-30b-a3b
    - gpt-oss-20b
  Governed external models
    - gpt-4o
    - gpt-4o-mini

Platform foundation
  Red Hat OpenShift AI
  OpenShift GitOps
  OpenShift OAuth and RBAC
  NVIDIA GPU Operator and NFD
  OpenShift Serverless, Service Mesh, monitoring
```

The central design choice is that model consumers do not connect directly to scattered model endpoints. They connect through MaaS. MaaS becomes the enterprise control point where platform teams publish model choices and enforce access.

## What The Demo Proves

The demo progresses through six platform capabilities.

| Step | What we show | What to understand |
|------|--------------|--------------------|
| [01 - OpenShift AI platform](steps/step-01-rhoai-platform/README.md) | The AI control plane, dashboard, users, model registry, and platform services | Trusted AI starts with a managed platform, not a collection of scripts |
| [02 - GPU infrastructure](steps/step-02-gpu-infra/README.md) | NVIDIA GPU enablement and worker capacity | Private AI needs centrally managed accelerator infrastructure |
| [03 - MaaS](steps/step-03-llm-serving-maas/README.md) | Local and external models behind one governed API | Model choice can coexist with policy, quotas, and observability |
| [04 - Dev Spaces](steps/step-04-devspaces/README.md) | AI assistants in controlled workspaces | Developers get familiar AI tools without bypassing platform governance |
| [05 - MTA](steps/step-05-mta/README.md) | AI-assisted Java modernization with MTA and Developer Lightspeed | AI becomes more valuable when grounded in analysis and workflow context |
| [06 - Developer Hub](steps/step-06-developer-hub/README.md) | Portal-based discovery of applications and platform capabilities | A developer portal turns AI platform services into self-service paths |

If someone only reads the workshop, they should still learn the architecture: private model serving, governed external model access, platform identity, developer tooling, modernization workflows, and portal-driven consumption.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the trusted platform foundation for managing predictive and generative AI workloads across hybrid cloud environments. OpenShift provides the enterprise substrate: identity, RBAC, networking, monitoring, GitOps, scheduling, and operational consistency.

Open source model infrastructure provides the model-serving layer. vLLM and llm-d support efficient inference patterns. Kubernetes operators make GPU enablement and AI platform components repeatable. Open ecosystem tools such as Continue, OpenCode, and Backstage-compatible catalog patterns make the platform useful to developers.

MaaS is the abstraction that ties the platform together. It lets platform teams expose model endpoints as shared services instead of asking every application team to manage inference infrastructure or direct provider credentials.

## Red Hat Products Demonstrated

This is a Red Hat platform demo. The open source projects are important, but the workshop is primarily about how Red Hat products package, integrate, operate, and support those capabilities for enterprise use.

| Red Hat product | Role in the workshop |
|-----------------|----------------------|
| [Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift) | The Kubernetes application platform providing identity, RBAC, networking, scheduling, storage integration, routes, monitoring, and operational consistency |
| [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai) | The AI platform layer for model serving, GenAI Studio, model registry, dashboard experience, and AI workload lifecycle management |
| [Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops) | GitOps delivery and reconciliation of the workshop platform through Argo CD |
| [Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces) | Cloud-native developer workspaces for AI-assisted development and modernization |
| [Migration Toolkit for Applications](https://www.redhat.com/en/technologies/jboss-middleware/migration-toolkit-for-applications) | Application modernization analysis and Developer Lightspeed integration for AI-assisted migration |
| [Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub) | Enterprise developer portal and software catalog for self-service platform consumption |
| [Red Hat Connectivity Link](https://www.redhat.com/en/blog/red-hat-connectivity-link) | API connectivity, gateway, and policy layer used in the MaaS governance path |
| [Red Hat build of Keycloak](https://www.redhat.com/en/technologies/cloud-computing/openshift/keycloak) | Identity brokering for MTA and Developer Hub authentication flows |

The demo is meant to show how these products work together as a platform: OpenShift runs the infrastructure, OpenShift AI manages AI capabilities, MaaS governs model access, Dev Spaces and MTA consume models in developer workflows, and Developer Hub turns the whole platform into a discoverable experience.

## Open Source Projects You Will Meet

Red Hat products in this workshop are built with and around open source communities. Part of the value of the demo is showing how those projects can be assembled into an enterprise platform with supportable lifecycle, identity, governance, and operations.

| Project | Where it appears | What to learn |
|---------|------------------|---------------|
| [Open Data Hub](https://opendatahub.io/) and [models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) | MaaS control plane | Upstream foundation for OpenShift AI and MaaS-style model access |
| [KServe](https://kserve.github.io/website/) | OpenShift AI model serving | Kubernetes-native model serving primitives |
| [vLLM](https://docs.vllm.ai/) | Local LLM inference | High-throughput LLM serving with an OpenAI-compatible API surface |
| [llm-d](https://llm-d.ai/) | Distributed inference architecture | Open source approach for distributed LLM serving on Kubernetes |
| [Gateway API](https://gateway-api.sigs.k8s.io/) | MaaS gateway | Kubernetes-native API routing and traffic management |
| [Kuadrant](https://kuadrant.io/) and [Authorino](https://www.authorino.io/) | MaaS policy enforcement | AuthN/AuthZ and rate-limit policy patterns at the gateway |
| [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace | Dev Spaces | Cloud-native development workspaces on Kubernetes |
| [Continue](https://www.continue.dev/) and [OpenCode](https://opencode.ai/) | AI coding assistants | OpenAI-compatible developer tooling that can consume MaaS endpoints |
| [Konveyor](https://www.konveyor.io/) | MTA modernization | Open source application modernization analysis and workflows |
| [Backstage](https://backstage.io/) | Developer Hub | Software catalog and developer portal patterns |

The workshop is not only a product tour. It is also a map of how open source projects become consumable, governed enterprise capabilities through Red Hat platforms.

## Trust Boundaries

This workshop deliberately demonstrates more than one trust level.

| Path | Boundary | What it teaches |
|------|----------|-----------------|
| Private local models | Prompts and code remain on the OpenShift platform | Sensitive development and modernization can use AI without sending code to an external provider |
| Governed external models | Prompts are proxied to an approved external provider | Frontier models can be made available with centralized access and usage control where policy permits |
| MCP integrations | The base deployment includes a read-only OpenShift MCP server; Slack and BrightData MCP components are optional and require their own credentials | Tool context must be evaluated separately from model access because each integration has its own data boundary |

This distinction is important. A governed external model is not the same as a private model. The value of the platform is that both choices can be offered through one controlled interface with clear policy boundaries.

External OpenAI model definitions are included in GitOps with a placeholder API key. They demonstrate the governed external model path, but the external calls are only usable after an operator replaces `openai-api-key` in the `maas` namespace with an approved provider credential.

## Why This Is Worth Knowing

The reusable pattern is bigger than this specific demo. A regulated enterprise can use the same architecture to answer common AI adoption questions:

- Which models are approved for which types of data?
- Which teams can access which models?
- Can sensitive source code stay inside the platform boundary?
- Can public models be offered without handing developers unmanaged provider keys?
- Can usage be measured and controlled?
- Can AI tools be embedded into real development and modernization workflows?

The workshop shows that Red Hat OpenShift AI can act as the enterprise AI platform, not only as a place to deploy models. It can become the trusted layer where model choice, developer productivity, and governance meet.

## Running The Workshop

The READMEs are designed to teach the architecture. The commands below are for operators running the lab.

```bash
git clone https://github.com/adnan-drina/rhoai3-coding-demo.git
cd rhoai3-coding-demo
cp env.example .env
oc login --token=<token> --server=<api>
./scripts/bootstrap.sh
```

Deploy steps in order:

```bash
./steps/step-01-rhoai-platform/deploy.sh
./steps/step-02-gpu-infra/deploy.sh
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-04-devspaces/deploy.sh
./steps/step-05-mta/deploy.sh
./steps/step-06-developer-hub/deploy.sh
```

For deployment details, validation strategy, and recovery procedures, use:

- [Documentation Index](docs/README.md)
- [Operations Guide](docs/OPERATIONS.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

## Repository Map

```text
rhoai3-coding-demo/
+-- scripts/                         # Bootstrap, shared helpers, validation
+-- gitops/
|   +-- argocd/app-of-apps/          # One Argo CD Application per workshop step
|   +-- step-01-rhoai-platform/      # OpenShift AI platform foundation
|   +-- step-02-gpu-infra/           # GPU infrastructure
|   +-- step-03-llm-serving-maas/    # MaaS, models, gateway, governance
|   +-- step-04-devspaces/           # Dev Spaces and workspaces
|   +-- step-05-mta/                 # MTA and Developer Lightspeed
|   +-- step-06-developer-hub/       # Red Hat Developer Hub
+-- steps/
|   +-- step-01-rhoai-platform/
|   +-- step-02-gpu-infra/
|   +-- step-03-llm-serving-maas/
|   +-- step-04-devspaces/
|   |   +-- coding-exercises/        # Python exercises for AI assistant demos
|   +-- step-05-mta/
|   +-- step-06-developer-hub/
+-- docs/
|   +-- README.md
|   +-- OPERATIONS.md
|   +-- TROUBLESHOOTING.md
+-- env.example
+-- README.md
```

## Demo Personas

| User | Purpose |
|------|---------|
| `ai-admin` | Platform administrator persona for model, MTA, and portal administration |
| `ai-developer` | Developer persona consuming models, workspaces, and modernization workflows |
| `kubeadmin` | Cluster administrator for platform setup and recovery |

## References

- [Red Hat AI](https://www.redhat.com/en/products/ai)
- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)
- [Accelerate enterprise software development with NVIDIA and MaaS](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [Red Hat OpenShift AI 3.3 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [Migration Toolkit for Applications 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [Red Hat Developer Hub 1.9 documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service)
