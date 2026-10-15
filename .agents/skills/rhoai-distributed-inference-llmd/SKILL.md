---
name: rhoai-distributed-inference-llmd
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing, changing, or debugging the private model qwen3-8-27b
  served as an LLMInferenceService (llm-d) in internal-models: its vLLM args
  list, endpoint-picker scheduler config, gateway refs to maas-default-gateway
  listeners qwen3-8 and api, the enable-auth annotation, delegated replicas,
  the qwen38-fp8 component, and the LLMInferenceServiceConfig topology
  templates in gitops/stages/040-governed-models-as-a-service/040-local-models/.
  Also for deciding whether to adopt llm-d autoscaling, flow control, or
  prefill/decode disaggregation. Do NOT use for KServe InferenceService or
  ServingRuntime work (use rhoai-model-serving-platform or
  rhoai-model-deployment) or MaaS subscriptions and API keys (use
  rhoai-maas-governance).
---

# Distributed Inference with llm-d

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/040-governed-models-as-a-service/040-local-models/README.md`.

## When to use

- A change touches `040-local-models/qwen38-27b-llminferenceservice.yaml`, the
  templates `single-node-topology.yaml` / `single-node-router.yaml`, or
  `components/qwen38-fp8/`.
- The model is not Ready, does not roll out, or shows "Starting" in the console.
- Someone proposes llm-d autoscaling, priority queuing, disaggregation or a
  second replica.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Private model `qwen3-8-27b` is an `LLMInferenceService` (`serving.kserve.io/v1alpha2`) in `internal-models`: `RedHatAI/Qwen3.8-27B-NVFP4` at a pinned Hugging Face revision on one RTX PRO 6000 GPU | `040-local-models/qwen38-27b-llminferenceservice.yaml` | [Deploy with llm-d][deploy] |
| LeaderWorkerSet Operator is installed although the model is single-GPU; the docs need it only for multi-node (more than 8 accelerators) | `gitops/stages/040-governed-models-as-a-service/040-maas-operators/` | [Enable distributed inference][enable] |
| Gateway chosen in YAML: `router.gateway.refs` to `maas-default-gateway` (`openshift-ingress`) listeners `qwen3-8` and `api` | same manifest; `040-gateway-governance/gateway/gateway.yaml` | [Select a Gateway in YAML][gw-yaml], [Gateway on OpenShift][gw-ocp] |
| Authentication on: `security.opendatahub.io/enable-auth: "true"` set explicitly (the default is on); Kuadrant and Authorino TLS live in `040-gateway-governance` | same manifest; `040-gateway-governance/governance/` | [Enable authentication][auth], [Connectivity Link auth][auth-rhcl] |
| Manifest owns `command` and the full `args` list (TLS args repeated; tool-calling flags in `args`, not `VLLM_ADDITIONAL_ARGS`); each non-default arg has a reason in the README | same manifest | [Configure vLLM args][vllm-args], [Configure tool calling][tools] |
| Inline `EndpointPickerConfig`: `queue-scorer` (weight 2) + `max-score-picker`, `failureMode: FailOpen`; prefix and KV scorers dropped for one replica | same manifest | [Inline scheduler config][sched-inline], [Scheduler plugins][sched-plugins] |
| Two dashboard templates in `redhat-ods-applications`: `single-node-exclusive-gpu` (`workload-single-node`) and `single-node-queue-router` (`router`); the Git model does not use them | `040-local-models/single-node-topology.yaml`, `single-node-router.yaml` | [Config labels][topo-labels], [Router configs][router-configs] |
| `/spec/replicas` delegated to operators (parked at 0, resumed by hand); Git says 1 | `ignoreDifferences` in `gitops/applications/040-local-models.yaml` | — (Argo CD behavior) |
| Kueue placement through hardware profile `gpu-rtxpro6000` and queue label `lq-gpu-rtxpro6000` | same manifest; `040-local-models/local-queue.yaml` | see `rhoai-kueue-workload-management` |
| Serving health alerts are a repo `PrometheusRule`, not the product llm-d dashboards | `040-local-models/monitoring/prometheusrule-vllm-serving-health.yaml` | [Monitor llm-d deployments][monitor] |
| Not used: Workload Variant Autoscaler, priority queuing, prefill/decode disaggregation, controlled (canary) deployment, batch inference, WideEP, tracing | — | [WVA][wva], [Priority queuing][flow], [P/D][pd], [Controlled deployment][canary] |

## Procedure

1. Read the component README and the manifest comments before editing an
   argument; measured values come from
   `docs/OPERATIONS.md#model-serving-study-and-default-model-2026-10-13`.
2. Check any new field against the installed schema (`oc explain
   llminferenceservice.spec.<field>`); the docs mix `v1alpha1` and `v1alpha2`
   examples.
3. Deploy: `./stages/040-governed-models-as-a-service/deploy.sh`. Validate:
   `./stages/040-governed-models-as-a-service/validate.sh --readiness`
   (spec equals Git, owned workloads, route listeners, `MaaSModelRef`), then
   `--functional` for inference through MaaS.
4. Inspect, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get llminferenceservice qwen3-8-27b -n internal-models \
     -o jsonpath='{.spec.replicas}{" "}{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get pods,httproute,inferencepool -n internal-models
   ```

5. Switch to FP8: add `components: [components/qwen38-fp8]` to
   `040-local-models/kustomization.yaml`, publish, redeploy, then run
   `stages/040-governed-models-as-a-service/register-model-cards.sh`.

## Pitfalls

- 3.5 changed the default scheduler profile to four scorers; services with a
  custom config keep theirs on upgrade ([3.5 scheduler upgrade][sched-upgrade]).
  The inline config here gets no new defaults; revisit it before adding a replica.
- A custom `args` list overrides the platform default list (stated for
  access-log filtering in [Endpoint log filtering][log-filter]). Upgrade-time
  default arguments are not picked up, and dropping the TLS args breaks the
  HTTPS probes.
- Single-replica rollouts with `maxSurge` deadlock on a full GPU queue:
  `docs/TROUBLESHOOTING.md#qwen-serving-change-never-finishes-rolling-out`.
- Console shows "Starting" with a Ready pod: Gateway preconditions, not the
  model (`docs/TROUBLESHOOTING.md#model-shows-starting-in-the-rhoai-console-but-its-pod-is-ready`).
- FP8 on RTX PRO 6000 needs `VLLM_USE_DEEP_GEMM=0`
  (`docs/TROUBLESHOOTING.md#qwen-38-fp8-crashes-at-startup-on-rtx-pro-6000-unknown-recipe`).
- The topology selector and Gateway discovery are Technology Preview; WideEP is
  Developer Preview ([Topology patterns][topo-patterns], [Gateway discovery][gw-disc]).
- The checkpoint is not a Red Hat validated model; a successful load is
  compatibility only (`BACKLOG.md`).

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Deploy and enable | [Deploy with llm-d][deploy], [Enable distributed inference][enable] |
| Topology selector (TP) | [Topology patterns][topo-patterns], [Config labels][topo-labels], [Router configs][router-configs] |
| Gateway | [Gateway discovery][gw-disc], [Select a Gateway in YAML][gw-yaml], [Gateway on OpenShift][gw-ocp] |
| Authentication | [Connectivity Link auth][auth-rhcl], [Enable authentication][auth] |
| vLLM and tool calling | [Configure vLLM args][vllm-args], [Configure tool calling][tools] |
| Request routing | [Inline config][sched-inline], [Plugins][sched-plugins], [3.5 upgrade][sched-upgrade] |
| Not used | [Priority queuing][flow], [WVA][wva], [P/D disaggregation][pd], [Controlled deployment][canary] |
| Operations | [Monitor llm-d][monitor], [Troubleshooting][ts] |

## Related skills

`rhoai-model-serving-platform`, `rhoai-model-deployment`,
`rhoai-maas-governance`, `rhoai-kueue-workload-management`,
`rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators`, `rhcl-configure`,
`ocp-ingress-gateway-routes`, `resume-gpu-demo`.

[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#deploying-models-using-distributed-inference_distributed-inference
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#enabling-distributed-inference_distributed-inference
[topo-patterns]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#llm-deployment-topology-patterns_topology-selector
[topo-labels]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#llmd-configuration-labels-and-topology-mapping_topology-selector
[router-configs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#router-configs-and-supported-topologies_topology-selector
[gw-disc]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#gateway-discovery-for-llmd-overview_gateway-discovery
[gw-yaml]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#select-gateway-yaml_gateway-discovery
[gw-ocp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configuring-gateway-for-llmd-on-openshift_gateway-discovery
[auth-rhcl]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configuring-authentication-for-llmd_distributed-inference
[auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#enabling-authentication-and-authorization-for-llm-inference-service_distributed-inference
[canary]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#controlled-deployment_distributed-inference
[vllm-args]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configuring-vllm-args-llm-d_distributed-inference
[log-filter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configure-vllm-endpoint-log-filtering_distributed-inference
[tools]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configuring-tool-calling-for-llmd_distributed-inference
[sched-inline]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#configuring-scheduler-inline_configuring-llm-scheduler
[sched-plugins]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#scheduler-plugins_configuring-llm-scheduler
[sched-upgrade]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#upgrading-epp-scheduler-configuration-rhoai-3-5_configuring-llm-scheduler
[flow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#managing-mixed-workloads-with-priority-queuing
[wva]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#autoscaling-llmd-model-deployments
[pd]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#llmd-configuring-pd-disaggregation_distributed-inference
[monitor]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#monitoring-llmd-deployments
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploy_models_using_distributed_inference_with_llm-d/index#troubleshooting-llm-d-deployment-issues_distributed-inference
