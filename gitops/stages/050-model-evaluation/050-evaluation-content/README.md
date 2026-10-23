# Evaluation content (`050-evaluation-content`)

This Application holds the evaluation definitions EvalHub serves: four versioned `agentic-coding-*` collections (the
evaluation-driven development criteria for coding models), one bounded custom provider (`inspect-coding`), and the
staged SWE-bench provider with the RBAC, agent configuration and S3 test-data Secret its runs
need. The qualification pipeline (`050-model-qualification`) and jobs submitted from the dashboard or the EvalHub REST
API consume it through `050-evalhub`. Criteria change more often than the service, so they are a separate Application.

| | |
|---|---|
| Argo CD Application | `050-evaluation-content` ([manifest](../../../applications/050-evaluation-content.yaml)) |
| Deployed by | [`stages/050-model-evaluation/deploy.sh`](../../../../stages/050-model-evaluation/deploy.sh) (deploy-order 4, all Stage 050 components at one commit SHA) |
| Validated by | [`validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (Synced and Healthy at the stage revision); EvalHub start-up validates the ids (see How). No content-specific check. |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff by annotation; `RespectIgnoreDifferences=true`, `SkipDryRunOnMissingResource=true`. |
| Depends on | `050-evalhub` (lists every id in its CR); `050-model-qualification` (namespace `evaluated-models`, OBC `evaluation-models-workbench`, tenant job ServiceAccount); ODF Route `s3`; Stage 040 MaaS (models under test). |
| Used by | `050-evalhub`; the qualification pipeline steps 1 to 4 (`latency-v1`, `throughput-v2`, `livecodebench-v3`, `python-tasks-v1`; its risk assessment step is a built-in `garak` `intents` job, not a collection); jobs submitted from **Develop & train → Evaluations** or the EvalHub REST API, or `stages/050-model-evaluation/evaluation/submit.sh` (the former SWE-bench driver `swebench-run.sh` is in git history at `82092e01`). |

## Why

EvalHub supports adding system-owned providers and collections as ConfigMaps labelled with
`trustyai.opendatahub.io/evalhub-{provider,collection}-type: system` and `-name: <id>`; the TrustyAI operator discovers them
by label and mounts them once the id is listed in the `EvalHub` CR [1]. Collections carry pass criteria and weights per
benchmark, so a collection is a versioned qualification gate [1]. Changing a gate means adding a new `-vN` collection,
which keeps older results comparable.

The custom provider reuses the built-in Inspect adapter image with different limits: a 512-token cap, eight connections
and three retries so samples stay inside the evaluation sidecar's 30-second model request limit. The risk
assessment uses the built-in `garak` provider's `intents` benchmark as a single job, not a collection; the
`garak-coding` provider and the `security-*-v2` collections were retired on 2026-10-23.

SWE-bench is not a 3.5.1 built-in provider. It is staged from the community `eval-hub-contrib` adapter. Patch generation
works; grading inside EvalHub does not run on 3.5.1 because the adapter needs Kubernetes API credentials and EvalHub runs
adapters without a mounted token (Stage 050 README and TROUBLESHOOTING).

## What

### `edd/` (collections and bounded providers)

All objects are ConfigMaps in `redhat-ods-applications`, wave 10.

| Name | Id | Benchmarks (provider) | Used by |
|---|---|---|---|
| `evalhub-collection-agentic-coding-latency-v1` | `agentic-coding-latency-v1` | interactive TTFT, 8,000/256 tokens, one session (`guidellm`) | pipeline step 1 |
| `evalhub-collection-agentic-coding-throughput-v2` | `agentic-coding-throughput-v2` | same, fixed 64 requests (`guidellm`) | pipeline step 2 |
| `evalhub-collection-agentic-coding-livecodebench-v3` | `agentic-coding-livecodebench-v3` | LiveCodeBench v6 (`lighteval`), gate 0.20 (v2 had 0.25) | pipeline step 3 |
| `evalhub-collection-agentic-coding-python-tasks-v1` | `agentic-coding-python-tasks-v1` | MBPP, HumanEval (`inspect-coding`) | pipeline step 4; CI template `stages/050-model-evaluation/evaluation/agentic-coding-python-tasks.ci.yaml` |
| `evalhub-provider-inspect-coding` | provider `inspect-coding` | `inspect/humaneval`, `inspect/mbpp`; image `quay.io/evalhub/community-inspect` pinned by digest, `INSPECT_EVAL_MAX_TOKENS=512`, `MAX_CONNECTIONS=8`, `MAX_RETRIES=3` | python-tasks-v1 |

### `swebench/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `evalhub-provider-swebench` | `redhat-ods-applications` | Wave 10. Provider `swebench` (Verified, Lite, Full); image `quay.io/evalhub/community-swebench` v0.6.0 pinned by digest. |
| Role / RoleBinding | `swebench-eval` | `evaluated-models` | Wave 12. create/get/list/delete Jobs and read pods and logs, for `evalhub-evalhub-job` (one grading Job per instance). |
| ServiceAccount | `swebench-agent` | `evaluated-models` | Wave 12. Identity of the patch-generation Jobs. |
| ClusterRoleBinding | `swebench-eval-anyuid-evaluated-models` | cluster | Wave 12. `system:openshift:scc:anyuid` for `evalhub-evalhub-job` and `swebench-agent` only (operator approval 2026-10-09). |
| ServiceAccount, Role, RoleBinding | `evalhub-s3-test-data-provisioner` | `evaluated-models` | Wave 12. Read the workbench OBC Secret and ConfigMap; create/patch Secrets. |
| Role / RoleBinding | `evalhub-s3-test-data-provisioner-route-reader` | `openshift-storage` | Wave 12. `get` on Route `s3` only. |
| Job | `provision-evalhub-s3-test-data` | `evaluated-models` | `Sync` hook, wave 13, `BeforeHookCreation,HookSucceeded`. Composes Secret `evalhub-s3-test-data` from the workbench bucket, pointing at the external ODF Route. |
| ConfigMap | `swebench-agent` | `evaluated-models` | Generated by `configMapGenerator` (no hash suffix) from `mini-swe-agent-swebench.yaml` (mini-swe-agent 2.4.6 configuration, MIT) and `run-instance.sh`, mounted by the patch-generation Jobs. |

### Objects not in Git

| Object | Created by |
|---|---|
| Secret `evaluated-models/evalhub-s3-test-data` | `provision-evalhub-s3-test-data` hook |
| Patch-generation Jobs, grading Jobs, predictions in the workbench bucket | The SWE-bench adapter at run time (formerly driven by `swebench-run.sh`, in git history at `82092e01`) |
| Built-in provider ConfigMaps | TrustyAI operator |

## How

**Ordering.** ConfigMaps at wave 10, SWE-bench RBAC at 12, the S3 hook at 13 [4]. The `EvalHub` CR in `050-evalhub`
references these ids; if this Application has not synced yet, the new EvalHub pod fails start-up validation while the old
pod keeps serving.

**Id rules.** Collection and provider ids are 36 characters or fewer: EvalHub 1.0 validates them at start-up and one invalid
id keeps the new pod from starting (`edd/kustomization.yaml`).

**Sizing choices (from the collection comments).** LiveCodeBench uses `num_examples: 100`, a code-only system prompt and
`max_new_tokens: 512` so a 16-sample request finishes inside the sidecar's 30-second limit; Inspect benchmarks are bounded
by `max_samples` because the shipped adapter ignores `num_examples`; LiveCodeBench runs alone in its own collection because
16 samples use all 16 sequence slots of the served model.

**SWE-bench agent.** `run-instance.sh` runs inside each SWE-bench instance image. At run time it downloads the `uv`
release archive (version 0.12.21, checked against its published SHA-256), installs `mini-swe-agent` at the version the Job passes, loads the dataset split from Hugging
Face and uploads predictions to the tenant bucket. Instance images come from Docker Hub.

**S3 test data.** EvalHub's init container verifies TLS against system roots only, so the Secret uses the publicly
trusted ODF Route instead of the in-cluster service [1].

**anyuid.** The SWE-bench images keep their repository under root-owned paths and the adapter's grading init container
runs as UID 0, so both ServiceAccounts get the `anyuid` SCC, which allows any UID and GID [3]. The binding is limited to
those two ServiceAccounts in the admin-only tenant.

**Secrets.** None in Git. `evalhub-s3-test-data` is composed in the cluster from the ODF-generated bucket Secret.

## Validation

`validate.sh` requires the Application Synced and Healthy at the stage revision. There is no check that each collection
loads; a failed load shows as an EvalHub pod that does not become ready, which `stages/050-model-evaluation/validate.sh` catches through
the EvalHub Deployment check.

By hand:

```bash
oc get configmap -n redhat-ods-applications -l trustyai.opendatahub.io/evalhub-collection-type=system
oc get configmap -n redhat-ods-applications -l trustyai.opendatahub.io/evalhub-provider-type=system
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Custom providers | ConfigMap with type/name labels, discovered by the operator, id in `spec.providers` [1] | Three providers, ids listed in `050-evalhub` | Aligned |
| Custom collections | ConfigMap with type/name labels, id in `spec.collections`; pass criteria and weights [1] | Nine collections | Aligned |
| ConfigMap namespace | Guide says "Operator namespace" in the introduction and "EvalHub custom resource namespace" in the procedure [1] | Operator namespace `redhat-ods-applications`, where the built-in provider ConfigMaps live | Aligned (doc is inconsistent; behaviour verified on the cluster) |
| Image provenance | Red Hat registry images or a documented exception | `inspect-coding` and `swebench` use `quay.io/evalhub` community images pinned by digest | Deviation (justified: the operator's own built-in `inspect` provider uses `quay.io/evalhub/community-inspect:v0.5.0`; SWE-bench has no built-in) |
| S3 test data | Documented credential Secret for custom S3 data [1] | Composed by a hook | Aligned |
| SCC | Grant SCCs to specific ServiceAccounts; `anyuid` allows any UID/GID [3] | Two ServiceAccounts | Deviation (justified: SWE-bench images require root; operator approval) |
| Kueue for evaluation jobs | Route evaluation jobs through Kueue [1][2] | Tenant uses `lq-cpu-default` (in `050-model-qualification`) | Aligned |
| Reproducible inputs | Pinned versions | Adapter images and the `uv` archive (version and SHA-256) pinned; the dataset split is fetched by name at run time | Partial (dataset revision not pinned) |
| Argo CD | Server-Side Diff by annotation [5] | Annotation present | Aligned |

## References

1. Evaluating AI systems (2.8 Route evaluation jobs through Kueue, 2.17 Use custom data from S3 for EvalHub evaluations, 2.22 Add a custom provider by using a ConfigMap, 2.23 Add a collection by using a ConfigMap), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index
2. Manage workloads with Kueue, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue
3. Managing security context constraints (default security context constraints), OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/managing-pod-security-policies
4. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
5. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
