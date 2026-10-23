# Model qualification project (`050-model-qualification`)

This Application creates the **Evaluated Models** project (`evaluated-models`): the single EvalHub tenant, its access
and Kueue queues, three S3 connections and project storage, a pipeline server, the **Agentic coding model qualification**
pipeline, the MaaS key that evaluations use, and a candidate model (`qwen3-8-27b-int4`) served next to production.
Platform administrators use it to qualify a model before it is promoted to Models-as-a-Service; developers have no
access. The Application reports **Suspended** by design while the candidate model is stopped.

| | |
|---|---|
| Argo CD Application | `050-model-qualification` ([manifest](../../../applications/050-model-qualification.yaml)) |
| Deployed by | [`stages/050-model-evaluation/deploy.sh`](../../../../stages/050-model-evaluation/deploy.sh) (deploy-order 2, all Stage 050 components at one commit SHA) |
| Validated by | [`validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (Synced, and Healthy or Suspended only by a stopped InferenceService) and [`stages/050-model-evaluation/validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (tenant label, tenant discovery, job ServiceAccount, admin access, developer denial) |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff by annotation; `RespectIgnoreDifferences=true`, `SkipDryRunOnMissingResource=true`. Annotation `demo.rhoai.io/accepted-health: Suspended`. |
| Depends on | `050-mlflow` (AI Pipelines and TrustyAI components enabled by its hook; MLflow for run tracking); `050-evalhub` (EvalHub instance that reconciles the tenant); Stage 040 (MaaS Gateway `maas-default-gateway`, subscription `model-qualification`); Stage 020 (ClusterQueues `cq-cpu-default`, `cq-gpu-reserved-demo`, `cq-gpu-rtxpro6000`; hardware profile `gpu-reserved-demo`); ODF (buckets, Route `s3`). |
| Used by | `050-evalhub` (Role `evalhub-evaluator` bound to its MCP and automation principals), `050-evaluation-content` and `050-oci-export` (objects in `evaluated-models`); evaluation jobs submitted from the dashboard or the EvalHub REST API. |

## Why

EvalHub runs evaluations in tenant namespaces labelled `evalhub.trustyai.opendatahub.io/tenant` and authorizes users and
ServiceAccounts with a Role on its virtual resources in that namespace [1]. Putting every evaluation in one admin-only
tenant keeps model onboarding a platform decision, and gives the qualification pipeline, the helpers, the CLI and the
dashboard one MaaS key, one queue and one set of MLflow experiments.

The qualification flow is an AI pipeline, so it runs on the project's pipeline server and is stored as Kubernetes
`Pipeline` and `PipelineVersion` resources, which the 3.5 guide supports for GitOps workflows [2]. The candidate model is a
project `InferenceService` because the dashboard's **Start evaluation run** form lists InferenceServices of the selected
project. Model evaluation jobs reach production models through MaaS with an API key referenced by
`model.auth.secret_ref` [1].

### Why the Application is Suspended

The candidate InferenceService carries `serving.kserve.io/stop: "true"` in Git, so KServe stops it and sets its `Stopped`
condition. Argo CD's built-in InferenceService health check maps `Stopped=True` to `Suspended` [8], and the Application
aggregates that to `Suspended`. Stopping frees the GPU between qualification runs. The candidate is in the last sync wave
(40) so that no other wave waits on it [7]. `demo.rhoai.io/accepted-health: Suspended` lets `stage-apps.sh status` accept
the state, and `validate.sh` accepts it only when every non-Healthy resource is an InferenceService whose stop annotation is
`true`. Set the annotation to `"false"` in Git to start the candidate; the Application then reports Healthy once it is
ready.

## What

### Project, access and queues (component root)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `evaluated-models` | cluster | Wave 5. Dashboard project, EvalHub tenant label, `kueue.openshift.io/managed: "true"`, Pod Security `baseline` audit/warn. |
| RoleBinding | `rhods-admins-admin` | `evaluated-models` | Wave 6. `admin` ClusterRole for `rhods-admins`. |
| Role | `evalhub-evaluator` | `evaluated-models` | Wave 12. The documented EvalHub tenant rules: `evaluations`, `collections`, `providers` (get, list, create, update, delete) and MLflow `experiments` (create, get) [1]. |
| RoleBinding | `qualification-evalhub-access` | `evaluated-models` | Wave 12. `evalhub-evaluator` for `rhods-admins`. |
| LocalQueue | `lq-cpu-default`, `lq-gpu-reserved-demo`, `lq-gpu-rtxpro6000` | `evaluated-models` | Wave 6. Point to the Stage 020 ClusterQueues; evaluation jobs use the CPU queue, model servers a GPU queue [3]. |

### MaaS key for evaluations (`maas-key-provisioner.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `evalhub-maas-key-provisioner` | `evaluated-models` | Wave 12. Owner of the MaaS key for subscription `model-qualification`. |
| Role / RoleBinding | `evalhub-model-auth-provisioner` | `evaluated-models` | Wave 12. create/get/patch/update Secrets and ConfigMaps in the project. |
| Role / RoleBinding | `qualification-model-auth-gateway-reader` | `openshift-ingress` | Wave 12. `get` on Gateway `maas-default-gateway` and Route `data-science-gateway` only, to read the MaaS API and dashboard hostnames. |
| Job | `provision-evalhub-model-auth` | `evaluated-models` | `Sync` hook, wave 13, `BeforeHookCreation,HookSucceeded`. Keeps the stored key while the MaaS API reports it active, otherwise revokes it and mints a new one; writes Secret `evalhub-model-auth-maas` (`api-key`, `key_id`, `expires_at`, `subscription`) and ConfigMap `qualification-endpoints` (`dashboard_url`, for the links the pipeline records). |

### Candidate model (`candidate-qwen3-8-27b-int4.yaml`, `candidate-model-auth.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServingRuntime | `vllm-cuda-runtime` | `evaluated-models` | Wave 20. Instance of the platform template `vllm-cuda-runtime-template`: the 3.5.2 vLLM image, the same digest as the platform's 3.5.2 LLMInferenceService templates that production MaaS uses (updated 2026-10-23 from the 3.5.1 image). |
| InferenceService | `qwen3-8-27b-int4` | `evaluated-models` | Wave 40. `RedHatAI/Qwen3.8-27B-INT4` pinned to a Hugging Face commit, RawDeployment, token authentication on, hardware profile `gpu-reserved-demo`, queue `lq-gpu-reserved-demo`, one L40S-class GPU, `serving.kserve.io/stop: "true"`. |
| InferenceService | `qwen3-8-27b-nvfp4` | `evaluated-models` | Wave 40. `RedHatAI/Qwen3.8-27B-NVFP4` at the production revision (registry Qwen3.8-27B-NVFP4 version 6) with production's serving arguments, hardware profile `gpu-rtxpro6000`, queue `lq-gpu-rtxpro6000`, one RTX PRO 6000: the candidate configuration that matches production MaaS, added after INT4 on L40S missed the first-token gate. |
| Role / RoleBinding | `qwen3-8-27b-nvfp4-view-role` / `evalhub-job-model-access-nvfp4` | `evaluated-models` | Wave 21. `get` on this InferenceService for `evalhub-evalhub-job`. |
| Role / RoleBinding | `qwen3-8-27b-int4-view-role` / `evalhub-job-model-access` | `evaluated-models` | Wave 21. `get` on this InferenceService for the tenant job ServiceAccount `evalhub-evalhub-job` (implicit authentication). |
| ServiceAccount, Secret (`kubernetes.io/service-account-token`), Role, RoleBinding | `candidate-model-client`, `candidate-model-client-token` | `evaluated-models` | Wave 12. A token that may only `get` InferenceServices in this project, used as the candidate API key. |
| ConfigMap | `candidate-model-service-ca` | `evaluated-models` | Wave 12. Injected service CA. |
| ServiceAccount, Role, RoleBinding | `candidate-model-auth-provisioner` | `evaluated-models` | Wave 12. create/get/patch Secrets. |
| Job | `provision-candidate-model-auth` | `evaluated-models` | `Sync` hook, wave 13, `BeforeHookCreation,HookSucceeded`. Writes Secret `garak-kfp-model-auth`, the one model auth Secret for every candidate evaluation: `api-key` (the `candidate-model-client` token); `ca_cert` with the service CA and the cluster CA; `judge_url`/`judge_api-key` and `sdg_url`/`sdg_api-key` (the abliterated risk assessment model and the same token, EvalHub's multi-model convention that the in-pod `garak` `intents` scan reads; TAP's attacker and evaluator inherit the judge); `JUDGE_API_KEY` and `SDG_API_KEY` (the same token under the names `garak-kfp` reads, guide 7.7.4); `kfp_url`, `kfp_sa_token`, `k8s_url`, `k8s_sa_token` for `garak-kfp`. Other adapters ignore the extra keys. Until 2026-10-23 a second Secret `qualification-model-auth` held only `api-key` and `ca_cert`. |

### Garak in pipeline mode (`garak-kfp-access.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `evalhub-job-dspa-api` | `evaluated-models` | Wave 12. Pipeline-server Role `ds-pipeline-user-access-dspa` (the DSPA API) for the job ServiceAccount `evalhub-evalhub-job`. |
| RoleBinding | `evalhub-job-pipeline-management` | `evaluated-models` | Wave 12. Pipeline-server Role `ds-pipeline-dspa` (runs, workflows, and `get` on Secrets for the S3 connection) for the same ServiceAccount. |

### Pipeline server (`pipeline-server.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding | `pipeline-server-configurator` | `evaluated-models` | Wave 12. Reads the Pipelines connection, creates `dashboard-dspa-secret`, creates/patches the DSPA and its server ConfigMaps. |
| Job | `configure-pipeline-server` | `evaluated-models` | `Sync` hook, wave 14, `BeforeHookCreation,HookSucceeded`, 900 s deadline. Creates DSPA `dspa` the way the dashboard's **Configure pipeline server** does, then points it at a copied server config with the MLflow plugin's `insecureSkipVerify: true`. |
| ConfigMap | `pipeline-tasks-service-ca` | `evaluated-models` | Wave 12. Injected service CA for pipeline task containers that call EvalHub. |
| RoleBinding | `pipeline-runner-evalhub-access` | `evaluated-models` | Wave 15. `evalhub-evaluator` for `pipeline-runner-dspa`. |
| RoleBinding | `pipeline-runner-demo-registry` | `rhoai-model-registries` | Wave 15. The operator-created `registry-user-demo-registry` Role (the one the dashboard's registry permissions bind) for `pipeline-runner-dspa`: the record step writes the verdict on the candidate's model version. |
| NetworkPolicy | `demo-registry-qualification-pipeline` | `rhoai-model-registries` | Wave 15. Admits the qualification pipeline's step pods (`pipelines.kubeflow.org/v2_component: "true"` in `evaluated-models`) to the registry API on 8443. The operator's own `demo-registry-https-route` admits only the router and RHOAI-generated namespaces, so an in-cluster call from this project timed out. |

### `pipeline/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Pipeline | `agentic-coding-model-qualification` | `evaluated-models` | Wave 16 (kustomize patch), `SkipDryRunOnMissingResource`. |
| PipelineVersion | `agentic-coding-model-qualification-v16` | `evaluated-models` | Wave 17. Compiled by `stages/050-model-evaluation/qualification/compile.py` from `pipeline.py`; do not edit by hand. One straight chain: `validate`, `latency`, `throughput`, `livecodebench`, `python-tasks`, `risk-assessment` (built-in `garak` `intents`, the Context-aware vulnerability scan, as a single task in the job pod), `verdict` (judges the run and records the verdict and evidence on the registry version), `report` (HTML report and summary metrics, the last step like garak's `write-kfp-outputs`). |

### `storage/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ObjectBucketClaim | `evaluation-models-models`, `-workbench`, `-pipelines` | `evaluated-models` | Wave 12, `Prune=false,Delete=false`. Fixed bucket names. |
| Secret | `evaluation-models-{models,workbench,pipelines}-connection` | `evaluated-models` | Wave 12, `Prune=false,Delete=false,ServerSideApply=true`. Dashboard S3 connection skeletons (`connection-type-ref: s3`); the hook fills the data. |
| ServiceAccount, Role, RoleBinding | `evaluated-models-s3-connections` | `evaluated-models` | Wave 12. Read the claims' Secrets/ConfigMaps, patch the three connections, create the project PVC. |
| Role / RoleBinding | `evaluated-models-s3-route-reader` | `openshift-storage` | Wave 12. `get` on Route `s3` only. |
| Job | `evaluated-models-s3-connections` | `evaluated-models` | `Sync` hook, wave 13, `BeforeHookCreation` (the completed Job is kept). Copies each claim's keys, bucket and endpoint into its connection after ownership checks; the Pipelines connection uses the external ODF Route so signed artifact links open in a browser; creates PVC `evaluated-models-storage`. |

### Objects not in Git

| Object | Created by |
|---|---|
| Secrets `evalhub-model-auth-maas`, `garak-kfp-model-auth`, `dashboard-dspa-secret`; ConfigMaps `qualification-endpoints`, `ds-pipeline-server-config-custom` | Hook Jobs above |
| DataSciencePipelinesApplication `dspa` | `configure-pipeline-server` hook (not tracked by Argo CD) |
| PVC `evaluated-models-storage` (20 Gi `gp3-csi`) | `evaluated-models-s3-connections` hook, so a `WaitForFirstConsumer` PVC does not hold the sync |
| Pipeline server Deployments, MariaDB, `pipeline-runner-dspa` ServiceAccount, `ds-pipeline-server-config-dspa` | Data Science Pipelines operator from `dspa` |
| ServiceAccount `evalhub-evalhub-job`, ConfigMaps `evalhub-discovery`, `evalhub-service-ca` | TrustyAI operator, for the tenant |
| Secrets and ConfigMaps named after each ObjectBucketClaim | ODF [5] |
| Predictor Deployment and Service of the candidate (when started) | KServe |

## How

**Ordering.** Namespace (5), admin access and queues (6), RBAC, connections and buckets (12), credential hooks (13),
pipeline server hook (14), runner binding (15), Pipeline (16), PipelineVersion (17; its webhook needs the Pipeline),
ServingRuntime (20), candidate access (21), candidate (40) [7].

**Pipeline server.** The hook mirrors the dashboard (odh-dashboard v3.5.0 `configurePipelinesServer`): DSPA `dspVersion:
v2`, object storage from the Pipelines connection, the default on-cluster database, `pipelineStore: kubernetes`, caching on,
no sample pipeline. The 3.5 guide states the default database is for development and testing only [2]. Because a pipeline
server's connection cannot be changed in place, the hook only creates it and fails if an existing `dspa` points elsewhere.
The DSPA is created by the Job rather than declared in Git, and is therefore not pruned or self-healed.

**MLflow TLS for pipeline steps.** Each step's driver and launcher call the in-cluster MLflow service, whose certificate
the service CA signs, and 3.5.1 passes them no CA bundle for that call. By operator decision (2026-10-12) the hook copies
the generated server config, sets the MLflow plugin's `insecureSkipVerify` to `true`, and sets
`apiServer.customServerConfigMap`. Delete the copy and the DSPA field to return to the default. The same copy sets the plugin's default experiment to
`models-onboarding`, so runs started without one (garak-kfp submits through the KFP SDK) and runs started from the form
land beside the onboarding evaluations; the hook restarts the API server when it changes the copy.

**Pipeline tasks.** Each task uses the pinned `odh-pipeline-runtime-minimal-cpu-py312-rhel9` image and installs
`eval-hub-sdk[cli]==1.0.5` and `kfp==2.16.1` from `pypi.org` at run time, so tasks need egress to PyPI.

**Candidate serving arguments.** The candidate shares the Stage 040 serving arguments but not its format or hardware:
it is INT4 on an L40S, while production is NVFP4 on an RTX PRO 6000. A passing result therefore qualifies this candidate
configuration only; a different quantization, runtime or GPU must be evaluated again before promotion. Shared arguments:
262,144-token context, FP8 KV cache, 16 sequences, 16,384 batched tokens, async scheduling, MTP
speculative decoding with three draft tokens, the model card's non-thinking sampling, Qwen3 reasoning and XML tool-call
parsers. The runtime comes from the platform vLLM NVIDIA GPU template and token authentication is on [4].

**Candidate authentication.** Jobs reach the candidate in two ways: the job ServiceAccount's own token with `get` on the
InferenceService, and, for adapters that send their own `Authorization` header, Secret `garak-kfp-model-auth` with the
token of `candidate-model-client` as `api-key` plus the service and cluster CAs as `ca_cert`. These are the article's patterns 1 (implicit ServiceAccount token with the InferenceService view Role) and 3
(`api-key` plus `ca_cert`, mounted for the adapter at `/var/run/secrets/model/`) [Connect EvalHub to protected production
model servers](https://developers.redhat.com/articles/2026/06/23/connect-evalhub-protected-production-model-servers); pattern 3
is needed because LightEval and Inspect send their own `Authorization` header and the garak-kfp pipeline pods have no
sidecar.

**Garak in pipeline mode (`garak-kfp`).** The provider submits the scan as a run on this project's pipeline server and
polls it. Its adapter pod has no ServiceAccount token, so a job names `garak-kfp-model-auth` as `model.auth.secret_ref`
and leaves `kfp_config.endpoint` unset: the adapter then sends its pipeline and Kubernetes API calls to the job sidecar
with the ref tokens `kfp_sa_token:ref` and `k8s_sa_token:ref`, and the sidecar injects the job ServiceAccount token
(the keys are empty) and routes each call to `kfp_url` or `k8s_url`. The garak pipeline pods have no sidecar: they mount
the same Secret at `/mnt/model-auth`, take the candidate's `api-key` from it and call the candidate at the job's
`kfp_config.model_url` (EvalHub rewrites every `*_url` key of the adapter's copy of the Secret to the sidecar address, so
the model address cannot come from the Secret). Cancelling the EvalHub job does not stop the pipeline run; terminate it
under **Pipelines → Runs**. This is the
upstream EvalHub sidecar convention, also used by the upstream `garak-kfp` tests; the RoleBindings above give the job
ServiceAccount the pipeline access those tests grant. A job carries the Secret and the benchmark parameters
`kfp_config.namespace`, `s3_secret_name` and `model_url`; the parameters, the submit command and the dashboard steps are
in [`stages/050-model-evaluation/evaluation/`](../../../../stages/050-model-evaluation/evaluation/README.md#garak-in-pipeline-mode-garak-kfp).
In the dashboard the model is entered under **Other (External endpoint)**: a model picked from the project's list is
submitted without an authentication Secret, a dashboard limitation fixed in 3.6 (BACKLOG). A job that sets
`kfp_config.endpoint` to the pipeline server, as the 3.5 guide's example in 7.3 does, calls it without a token and fails
with HTTP 401 ([troubleshooting](../../../../docs/TROUBLESHOOTING.md#garak-kfp-evaluation-fails-with-401-unauthorized)).

**MaaS key.** Production and judge models are reached through MaaS. The provisioner discovers the Gateway hostname, calls
the MaaS API as its own ServiceAccount, and stores the key under the documented `api-key` key [1]. Keys use the server's
maximum lifetime and are re-minted on the next sync once expired or revoked. The calls use `curl -k`.

**Secrets.** No credential is in Git. Keys and tokens are created in the cluster by hooks, ODF and Kubernetes; hooks pass
values through private temporary files or stdin and never print them.

**Cluster-specific values.** The MaaS hostname and the ODF S3 Route host are read at sync time; nothing is patched into
Git.

## Validation

`validate.sh` requires `050-model-qualification` Synced at the stage revision and, if Suspended, that only stopped
InferenceServices cause it. `stages/050-model-evaluation/validate.sh` checks that `evaluated-models` is the only EvalHub tenant, that
tenant discovery (`evalhub-discovery`) and the service CA were reconciled, that `evalhub-evalhub-job` exists and may write
MLflow experiments, that `rhods-admins` may create and read evaluations, providers, collections and experiments, and that
`rhoai-developers` may not create evaluations.

By hand:

```bash
oc get application 050-model-qualification -n openshift-gitops -o jsonpath='{.status.health.status}{"\n"}'
oc get isvc,dspa,pipelineversion -n evaluated-models
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Tenant namespace | Label `evalhub.trustyai.opendatahub.io/tenant` [1] | Set on `evaluated-models` | Aligned |
| Tenant access | Role on `evaluations`, `collections`, `providers`, MLflow `experiments`, bound to users, groups or ServiceAccounts [1] | `evalhub-evaluator` with exactly those rules | Aligned |
| Model credentials | Secret with `api-key`, referenced by `model.auth.secret_ref` [1] | `evalhub-model-auth-maas`, minted by a hook | Aligned |
| Garak pipeline mode | 3.5 guide 7.3/7.7.4: `model.auth.secret_ref`, `kfp_config.endpoint`, `namespace`, `s3_secret_name` [1]; upstream: Secret keys `kfp_url` and empty `kfp_sa_token`, the sidecar injects the job ServiceAccount token [10], [11] | `garak-kfp-model-auth` from the candidate hook; job ServiceAccount bound to the pipeline-server Roles; jobs set `namespace`, `s3_secret_name` and `model_url`, no `endpoint` | Deviation (justified: the guide's `endpoint` example fails with 401 on 3.5.2; Red Hat support confirmed, BACKLOG) |
| Kueue | Namespace label `kueue.openshift.io/managed=true` and workloads carrying `kueue.x-k8s.io/queue-name` [3]; EvalHub Kueue routing [1] | Label, three LocalQueues, queue label on the InferenceService | Aligned |
| Pipeline server | Configure from an S3 connection; default database for development and testing only [2] | Same values as the dashboard; default MariaDB | Deviation (justified: demo; not a production database) |
| Pipeline server as code | Pipeline definitions stored as Kubernetes resources [2] | Pipeline and PipelineVersion in Git; DSPA created by a hook Job | Gap (DSPA not declared in Git; see findings) |
| MLflow for pipeline runs | MLflow integration per DSPA (`spec.mlflow`) [2] | Default detection plus plugin `insecureSkipVerify: true` | Deviation (justified: 3.5.1 passes no CA to step MLflow calls; operator decision 2026-10-12) |
| Model runtime | vLLM NVIDIA GPU ServingRuntime for KServe; token authentication option [4] | Template instance, auth on | Aligned |
| Model provenance | Use validated models where possible | `RedHatAI/Qwen3.8-27B-INT4` from Hugging Face, not in the validated-model list (OPERATIONS) | Deviation (justified: candidate under qualification) |
| Stop a model | Stopped InferenceService reports `Suspended` in Argo CD [8] | Accepted health `Suspended`, validated | Aligned |
| Bucket provisioning | OBC on `openshift-storage.noobaa.io` [5] | Fixed `bucketName` | Deviation (justified: connection skeletons reference known names) |
| Argo CD | Server-Side Diff by annotation [9]; `Prune=false,Delete=false` for data [6] | Both; connection Secrets also `ServerSideApply=true` | Deviation (repository rule forbids `ServerSideApply=true`; see findings) |

## References

1. Evaluating AI systems (2.8 Route evaluation jobs through Kueue, 2.15 Configure API key authentication for model endpoints, 2.28 Set up a tenant namespace, 2.29 Grant access to EvalHub, 2.30 EvalHub roles), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index
2. Working with AI pipelines (1.1 Configure a pipeline server, 1.2.4 Define a pipeline by using the Kubernetes API, 4 Track pipeline experiments with MLflow), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_ai_pipelines/index
3. Manage workloads with Kueue, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue
4. Deploying models (2.9 Deploy models on the model serving platform), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/deploying_models/index
5. Object Bucket Claim, Red Hat OpenShift Data Foundation 4.22. https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.22/html/managing_hybrid_and_multicloud_resources/object-bucket-claim
6. Sync options, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
7. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
8. InferenceService health check (`Stopped` maps to `Suspended`), Argo CD resource customizations (upstream). https://raw.githubusercontent.com/argoproj/argo-cd/master/resource_customizations/serving.kserve.io/InferenceService/health.lua
9. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
10. EvalHub runtime sidecar, model proxy ref tokens (`*_sa_token`, `*_url`), upstream. https://github.com/eval-hub/eval-hub/blob/main/internal/eval_runtime_sidecar/proxy/model_proxy.go
11. EvalHub *Model Authentication*, scenario 3 "In-cluster SA-token-authenticated services (KFP and others)", upstream. https://github.com/eval-hub/eval-hub.github.io/blob/main/src/content/docs/guides/model-authentication.mdx
