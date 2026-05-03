# Stage 030: Private Model Serving

## Why This Matters

The workshop story now has a platform foundation and a governed GPU service. Stage 030 turns that foundation into something developers and platform services can actually use: private AI inference running on Red Hat OpenShift AI.

Inference is the operational phase of AI. A trained model receives a prompt or input, applies what it learned during training, and returns a prediction, completion, classification, recommendation, or other answer. For this demo, inference means local large language models responding to coding and modernization requests through OpenAI-compatible APIs. That is the point where AI moves from "we have a model" to "we have a service that can power developer workflows."

This stage matters because enterprise AI coding assistance needs a credible private path before developers use it with sensitive source code. Later stages will add MaaS governance, developer workspaces, modernization tools, MCP context, and portal self-service. Those experiences depend on this stage proving that private model inference can be deployed, scheduled, secured, registered, and validated as platform infrastructure.

The important idea is not only that a model responds. It is that regulated enterprise environments need a repeatable inference layer with clear runtime choices, observable behavior, accelerator governance, API compatibility, and a path to scale when demand grows. Stage 030 introduces that layer with vLLM and llm-d in their proper roles: vLLM serves the model efficiently, and llm-d provides the Kubernetes-native architecture for distributed inference patterns around that serving engine.

## Architecture

![Stage 030 layered capability map](../../docs/assets/architecture/stage-030-capability-map.svg)

## What This Stage Adds

This stage adds the private inference layer for the trusted AI development platform.

- Local `LLMInferenceService` resources for `gpt-oss-20b` and `nemotron-3-nano-30b-a3b`.
- Red Hat AI Inference Server / vLLM serving with an OpenAI-compatible API surface.
- Kueue-backed GPU placement and single-GPU demo sizing for each private model replica.
- Platform authentication, RBAC, and gateway posture so private model endpoints are not unmanaged routes.
- llm-d, LeaderWorkerSet, readiness, and metric foundations for scale-aware inference operations.
- Model registry seed data so private models are discoverable as named, versioned platform assets.

The stage intentionally demonstrates a controlled private-serving baseline rather than a full multi-node or disaggregated inference benchmark.

## What To Notice And Why It Matters

Stage 030 turns the GPUaaS foundation into private AI inference on Red Hat OpenShift AI. The local models are declared as GitOps-managed `LLMInferenceService` resources, served by the Red Hat AI Inference Server vLLM runtime, connected to Kueue-managed GPU capacity, registered for discovery, and exposed through platform-controlled service endpoints.

The essential proof point is private inference operated as enterprise platform infrastructure:

- Models are reconciled and validated as OpenShift AI resources, not manually launched from notebooks or exposed as unmanaged endpoints.
- vLLM provides efficient OpenAI-compatible serving, which keeps application integration familiar while preserving platform ownership.
- llm-d scheduler enablement, LeaderWorkerSet prerequisites, queue labels, readiness probes, and vLLM metrics create a controlled path toward distributed inference patterns.
- Model registry seed data makes private models discoverable as named, versioned assets.

This matters because data privacy and sovereignty claims require an operating model, not just a model choice. Keeping prompts, source code, and enterprise context inside the OpenShift platform boundary depends on controlling the inference runtime, GPU scheduling, endpoints, authentication posture, metadata, metrics, and validation path.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift provides the application platform underneath private inference: namespaces, RBAC, scheduling, storage attachment, routes, service networking, monitoring, and operator lifecycle. Red Hat OpenShift GitOps keeps the private model-serving desired state reproducible.

Red Hat OpenShift AI provides the model-serving control plane, data science project integration, dashboard experience, model registry integration, and `LLMInferenceService` API used by this stage. The model-serving platform makes trained models available as services that applications can query through API requests. In this demo, those requests are later routed through MaaS rather than handed directly to each developer tool.

vLLM is the serving engine in this stage. Its job is to run the model efficiently: manage GPU memory, serve LLM requests with high throughput, expose OpenAI-compatible APIs, and provide runtime metrics that operators can use to understand request pressure, latency, tokens, and cache behavior. That matters because enterprise developer tools should not need a custom integration for every private model. They can talk to a familiar API while the platform team retains control over where the model runs and how it is operated.

llm-d is the distributed inference architecture around the serving engine. Its job is to make LLM serving more Kubernetes-native as deployments grow: scheduler-aware routing, distributed serving patterns, LeaderWorkerSet integration, and future paths such as disaggregated prefill/decode and workload-aware autoscaling. In this demo, llm-d is used in a deliberately modest form through `LLMInferenceService` and explicit scheduler enablement. That is enough to show how private inference can be built on the same open cloud-native foundation that enterprises already use for regulated applications.

Stage 020 contributes the GPUaaS foundation. Stage 030 consumes it by labeling the local model resources with `kueue.x-k8s.io/queue-name=private-model-serving`, requesting GPU capacity, and letting the platform manage admission and scheduling rather than hard-coding private model serving as a special case.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides model serving, `LLMInferenceService`, model registry integration, and the data science project experience.
- **Red Hat AI Inference Server** provides the vLLM-based runtime image used by the private LLM serving containers.
- **Red Hat OpenShift** provides the runtime platform, RBAC, routes, service networking, storage, scheduling, and namespace isolation.
- **Red Hat build of Kueue** provides the queue and admission context inherited from Stage 020.
- **OpenShift monitoring** provides the PrometheusRule API used for vLLM metric aliases that support future autoscaling analysis.
- **Red Hat OpenShift GitOps** reconciles the model-serving desired state through Argo CD.

## Open Source Projects To Know

- [KServe](https://kserve.github.io/website/) provides Kubernetes-native inference service abstractions.
- [vLLM](https://docs.vllm.ai/) provides high-throughput LLM serving with OpenAI-compatible APIs. vLLM is a Linux Foundation-hosted open source project under the PyTorch Foundation ecosystem, with broad collaboration across model labs, hardware vendors, and AI infrastructure companies.
- [llm-d](https://llm-d.ai/) contributes Kubernetes-native distributed inference patterns for large language models. llm-d is a CNCF Sandbox project backed by contributors and supporters including Red Hat, Google Cloud, IBM Research, CoreWeave, NVIDIA, AMD, Cisco, Hugging Face, Intel, Lambda, Mistral AI, UC Berkeley, and the University of Chicago.
- [LeaderWorkerSet](https://lws.sigs.k8s.io/) supports coordinated leader-worker deployment patterns used by distributed AI workloads.
- [Open Data Hub](https://opendatahub.io/) is the upstream foundation for many OpenShift AI capabilities.

## Trust Boundaries

Private local models keep prompts and code inside the OpenShift platform boundary. In this stage, the inference runtime, model containers, GPU scheduling, service endpoints, and model metadata are all operated inside the cluster.

That does not mean every later AI path is private. Stage 050 introduces governed external models, where prompts are centrally controlled but still processed by an external provider. Stage 030 establishes the private option that sensitive coding and modernization workflows can use when policy requires local processing.

The model artifacts themselves also remain part of the trust boundary. Operators must verify licensing, provenance, and approved use for the model images they deploy. This repository uses declared model image references for a disposable demo and does not commit provider credentials, kubeconfigs, or private model secrets.

## Where This Fits In The Full Platform

| Earlier capability | How this stage uses it |
|--------------------|------------------------|
| Stage 010 platform foundation | Uses Red Hat OpenShift AI, model registry, RBAC, gateway prerequisites, and GitOps foundations |
| Stage 020 GPU Infrastructure for Private AI | Consumes queue-backed GPU capacity and the `private-model-serving` Kueue local queue |

| Later capability | What this stage provides |
|------------------|--------------------------|
| Stage 040 MaaS | Supplies local models that MaaS can publish, meter, and govern |
| Stage 050 Approved External Model Access | Provides the private baseline that approved external model access must be compared against |
| Stage 060 MCP Context Integrations | Provides the private model path that can receive approved tool context through governed consumers |
| Stage 070 Dev Spaces | Provides private model endpoints for coding assistants |
| Stage 080 MTA | Provides the private model path for modernization assistance |
| Stage 090 Developer Portal | Provides a platform capability that can be documented and discovered as self-service |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/030-private-model-serving/deploy.sh
./stages/030-private-model-serving/validate.sh
```

Manifests: [`gitops/stages/030-private-model-serving/base/`](../../gitops/stages/030-private-model-serving/base/)

## References

- [Red Hat: What is AI inference?](https://www.redhat.com/en/topics/ai/what-is-ai-inference)
- [Red Hat OpenShift AI 3.4: Configuring your model-serving platform](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/configuring_your_model-serving_platform/index)
- [Red Hat OpenShift AI 3.4: Deploying models by using Distributed Inference with llm-d](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/deploy_models_using_distributed_inference_with_llm-d/deploying-models-using-distributed-inference_distributed-inference)
- [Red Hat OpenShift AI 3.4: Managing workloads with Kueue](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-workloads-with-kueue)
- [Red Hat: Red Hat launches the llm-d community](https://www.redhat.com/en/about/press-releases/red-hat-launches-llm-d-community-powering-distributed-gen-ai-inference-scale)
- [Red Hat Developer: llm-d Kubernetes-native distributed inferencing](https://developers.redhat.com/articles/2025/05/20/llm-d-kubernetes-native-distributed-inferencing)
- [Red Hat Developer: Run Model-as-a-Service for multiple LLMs on OpenShift](https://developers.redhat.com/articles/2026/03/24/run-model-service-multiple-llms-openshift)
- [PyTorch: vLLM project](https://pytorch.org/projects/vllm/)
- [CNCF: Welcome llm-d to the CNCF](https://www.cncf.io/blog/2026/03/24/welcome-llm-d-to-the-cncf-evolving-kubernetes-into-sota-ai-infrastructure/)
- [KServe documentation](https://kserve.github.io/website/)
- [vLLM documentation](https://docs.vllm.ai/)
- [llm-d documentation](https://llm-d.ai/)
- [Open Data Hub](https://opendatahub.io/)

## Next Stage

[Stage 040: Governed Models-as-a-Service](../040-governed-models-as-a-service/README.md) adds the MaaS control point, gateway policy, quotas, telemetry, and subscriptions.
