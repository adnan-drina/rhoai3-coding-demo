# Stage 040: Governed Models-as-a-Service

## Why This Matters

A model endpoint alone does not provide a shared enterprise service. Models-as-a-Service (MaaS) gives developers governed access to private and approved external models through API keys, subscriptions, quotas and usage telemetry.

## Architecture

Two exclusive L40S GPUs serve the project's Qwen models. Native OpenShift AI controllers connect them to one governed Gateway. Separate HTTPS listeners serve the API, Qwen 3.6 and Qwen 3.8; namespace restrictions keep their routes separate. Native MaaS policies control access across the same Gateway.

## What This Stage Adds

- Qwen 3.6 27B FP8 and Qwen 3.8 27B INT4, each on one full GPU.
- Native MaaS API key storage, subscriptions, authentication and token quotas.
- Approved GPT-6 Luna access through the native OpenAI external-provider integration.
- GenAI Studio enablement for experimenting with available model endpoints.
- A bounded, read-only OpenShift MCP endpoint for later coding workflows.

## What To Notice And Why It Matters

Private model hosts separate routing while MaaS preserves a common governance boundary. The two full GPUs are this project's model-memory choice; the configuration does not enable time slicing or automatic scaling.

GPT-6 Luna uses the OpenAI Chat Completions protocol. Function calls require `reasoning_effort: none`. OpenAI Responses built-in tools are outside this connection's protocol. External requests leave the cluster for the approved provider.

GenAI Studio uses existing model endpoints. A user creates a playground in their project through the dashboard; the native service creates its supporting pgvector storage. Basic playground use does not add another GPU or an object-storage bucket. RAG, AutoRAG and AutoML are outside this stage.

## How Red Hat And Open Source Make It Work

OpenShift AI manages AIGateway, KServe and OGX. Red Hat Connectivity Link supplies native authentication and rate limiting. Service Mesh and Gateway API provide routing. PostgreSQL stores MaaS API-key state. GitOps owns customer configuration while native operators own generated workloads.

## Trust Boundaries

Provider keys and database credentials stay outside Git. Each model request must use its authorized MaaS key. OpenShift MCP exposes only the selected read-only tools and retains Kubernetes RBAC restrictions. Browser checks use your own session.

## Red Hat Products Used

Red Hat OpenShift AI 3.5, OpenShift Container Platform 4.22, Red Hat Connectivity Link 1.4 and OpenShift Service Mesh 3.4. Native external-model integration and GenAI Studio retain their documented product support status; upstream MCP is a separately pinned project component.

## Deploy And Validate

Use the reviewed published branch configured in your private environment:

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh --readiness
./stages/040-governed-models-as-a-service/register-model-cards.sh
```

Readiness checks do not establish inference, streaming or quota behavior. Bounded functional checks and user playground interaction complete acceptance. In the dashboard, create a playground in your project and select an available governed model endpoint. Do not use the playground to create a replacement serving deployment.

## References

- [OpenShift AI 3.5 Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/index)
- [GenAI Playground prerequisites](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/experimenting_with_models_in_the_gen_ai_playground/playground-prerequisites_rhoai-user)
- [Connectivity Link 1.4 installation](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/install_connectivity_link/rhcl-install-on-ocp)
- [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [Kubernetes MCP Server](https://github.com/containers/kubernetes-mcp-server/tree/v0.0.67)

## Next Stage

[Stage 050: Model Evaluation](../050-model-evaluation/README.md)
