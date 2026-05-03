# Stage 030: Private Model Serving

## Why This Matters

The workshop story now has a platform foundation and a governed GPU service. Stage 030 turns that foundation into something developers and platform services can actually use: private AI inference running on Red Hat OpenShift AI.

Inference is the operational phase of AI. A trained model receives a prompt or input, applies what it learned during training, and returns a prediction, completion, classification, recommendation, or other answer. For this demo, inference means local large language models responding to coding and modernization requests through OpenAI-compatible APIs. That is the point where AI moves from "we have a model" to "we have a service that can power developer workflows."

This stage matters because enterprise AI coding assistance needs a credible private path before developers use it with sensitive source code. MaaS governance, developer workspaces, modernization tools, MCP context, and portal self-service all depend on private model inference that can be deployed, scheduled, secured, registered, and validated as platform infrastructure.

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

Red Hat OpenShift provides the platform foundation for private inference: namespaces, RBAC, scheduling, routes, service networking, monitoring, operator lifecycle, and GitOps-managed desired state. Red Hat OpenShift AI adds the model-serving control plane, data science project integration, dashboard experience, model registry integration, and `LLMInferenceService` API used to expose local models as services.

The open source serving layer is vLLM and llm-d. vLLM provides efficient LLM serving, OpenAI-compatible APIs, and runtime metrics. llm-d brings a Kubernetes-native distributed inference pattern around the serving engine. Together with the GPUaaS foundation from Stage 020, this lets private models run inside OpenShift while consumers use a familiar API and platform teams keep scheduling, telemetry, and lifecycle control centralized.

## Trust Boundaries

Private local models keep prompts, source code, inference runtime, service endpoints, and model metadata inside the OpenShift platform boundary. This supports data-sovereignty and confidentiality goals for sensitive engineering work, while model artifact provenance, licensing, access control, telemetry, and human approval remain necessary governance controls for EU AI Act readiness rather than automatic compliance.

## Red Hat Products Used

- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides model serving, `LLMInferenceService`, model registry integration, and the data science project experience.
- **[Red Hat AI Inference Server](https://www.redhat.com/en/products/ai)** provides the vLLM-based runtime image used by the private LLM serving containers.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the runtime platform, RBAC, routes, service networking, storage, scheduling, monitoring, and namespace isolation.
- **[Red Hat build of Kueue](https://docs.redhat.com/en/documentation/red_hat_build_of_kueue/1.0/html/overview/index)** provides queueing and admission control for private model workloads.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** reconciles the model-serving desired state through Argo CD.

## Open Source Projects To Know

- [KServe](https://kserve.github.io/website/) provides Kubernetes-native inference service abstractions.
- [vLLM](https://docs.vllm.ai/) provides high-throughput LLM serving with OpenAI-compatible APIs.
- [llm-d](https://llm-d.ai/) contributes Kubernetes-native distributed inference patterns for large language models.
- [LeaderWorkerSet](https://lws.sigs.k8s.io/) supports coordinated leader-worker deployment patterns used by distributed AI workloads.
- [Open Data Hub](https://opendatahub.io/) is the upstream foundation for many OpenShift AI capabilities.

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
