# Migration Toolkit for Applications (`070-mta`)

This Application installs Migration Toolkit for Applications (MTA) 8.3.2 in `openshift-mta`. It enables Hub authentication through the platform Keycloak realm, the Developer Lightspeed LLM proxy and the native MTA Agents. All model traffic goes through the governed MaaS Gateway with an owner-bound MaaS subscription. Developers use the MTA UI and the editor extensions in Dev Spaces workspaces. Stage 130 (AI-autonomous migration) uses the Hub for analysis. Optional Solution Server stays disabled.

| | |
|---|---|
| Argo CD Application | `070-mta` ([manifest](../../../applications/070-mta.yaml)) |
| Deployed by | `stages/070-advanced-app-platform/deploy.sh` → `stage-apps.sh deploy 070` (deploy-order 6) |
| Validated by | `stages/070-advanced-app-platform/validate.sh`: operator rows plus the steps "MTA 8.3 native Agents", "MTA Developer Lightspeed proxy" and "Optional MTA Solution Server", and its security-boundary checks; `validate.sh --static` (renders, disjoint components, scripts parse; the former offline tests `tests/*.test.py` are in git history at `82092e01`) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`, `ClientSideApplyMigration=false`; compare-option `ServerSideDiff=true`. `ignoreDifferences`: OperatorGroup annotation `olm.providedAPIs` (OLM-owned); Subscription `startingCSV`; ConsoleLink `mta` `href`/`imageURL`; Tackle `mta` `/spec/kai_llm_baseurl`; Gateway `maas-qwen` `/spec/endpoint` |
| Depends on | `070-namespaces` (`openshift-mta`, `openshift-vertical-pod-autoscaler` and the workspace namespaces `wksp-*`); `070-identity` (Secret `openshift-mta/stage070-mta-provisioner`, a platform-realm client with realm/user/client administration); Stage 040 (`maas-default-gateway`, the MaaS API and the CRDs `MaaSSubscription`/`MaaSAuthPolicy`); Stage 040/030 model `qwen3-8-27b` in `internal-models`; Stage 060 (Agent Sandbox controller) |
| Used by | `070-gitlab` (`bootstrap-scm.py` reads the MTA Route for the catalog's `MTA_HUB_URL`); `070-devspaces` workspaces (`mta-hub-config` ConfigMaps); Stage 130 migration workflow |

## Why

MTA analyses applications and suggests migration changes. Version 8.3 adds two AI paths that this platform must route through private, governed models: the Developer Lightspeed proxy (Technology Preview) [3] and native MTA Agents in the Hub (Developer Preview) [2]. The Operator-based install with a `Tackle` resource is the documented method [1]. The Operator then owns the Hub, UI, databases and network policies.

Everything MTA-specific lives in one Application: the Operator, the instance, SSO wiring, the MaaS identity and the controller sizing. These parts change together when MTA is upgraded. The Lightspeed and Gateway settings depend on the instance's schema.

## What

### Operator and instance

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| OperatorGroup | `mta` | `openshift-mta` | Own-namespace target (wave 1) |
| Subscription | `mta-operator` | `openshift-mta` | Channel `stable-v8.3`, `redhat-operators`, `installPlanApproval: Manual`, `startingCSV: mta-operator.v8.3.2` (wave 2) |
| ServiceAccount, Role, RoleBinding | `approve-installplan` | `openshift-mta` | `get`/`list`/`patch` InstallPlans; `get` on Subscription `mta-operator` only (wave 1) |
| Job (Sync hook) | `approve-installplan` | `openshift-mta` | Approves this operator's InstallPlan only if every CSV is on its allowlist (`mta-operator.v8.3.2`), then waits for that CSV (wave 2; `BeforeHookCreation,HookSucceeded`) |
| ConsoleLink | `mta` | (cluster) | Application-menu entry; a placeholder URL in Git, patched by the SSO hook (wave 9) |
| Tackle | `mta` | `openshift-mta` | `feature_auth_required: true`, `idp_primary: true`, `rwx_supported: "false"`, `kai_llm_proxy_enabled: true`, `kai_solution_server_enabled: false`, `kai_llm_provider: openai`, `kai_llm_model: publishers/internal-models/models/qwen3-8-27b`, `kai_database_volume_size: 5Gi`, `agentic_enabled: true`, `agentic_steer_enabled: false` (wave 10) |

The `openshift-mta` and `openshift-vertical-pod-autoscaler` namespaces come from `070-namespaces`.

The Operator creates the Hub, UI, `kai-db`, `llm-proxy` and `agentic-controller` Deployments, the Route `mta`, three `gp3-csi` PVCs and its own NetworkPolicies (`mta-deny-all`, `mta-egress`, `mta-external`, `mta-metrics`, `mta-namespace`). None of these are in Git.

### Governed model access (`jobs/configure-ai.yaml`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `mta-maas-provisioner` | `openshift-mta` | Standing MaaS identity; the owner of the subscription and of the API key (wave 10) |
| Role, RoleBinding | `mta-maas-provisioner` | `openshift-mta` | `get`/`patch`/`update` on Secret `kai-api-keys`; Secret `create`; `get`/`patch` on Tackle `mta` and Gateway `maas-qwen` |
| Role, RoleBinding | `mta-maas-provisioner` | `openshift-ingress` | `get` on Gateway `maas-default-gateway` |
| MaaSSubscription | `mta-migration-ai` | `models-as-a-service` | Owner: the service account; model `qwen3-8-27b`, 5,000,000 tokens per hour, priority 100 |
| MaaSAuthPolicy | `mta-migration-ai` | `models-as-a-service` | Authorizes the same service account for `qwen3-8-27b` |
| Gateway (`konveyor.io/v1alpha1`) | `maas-qwen` | `openshift-mta` | Native-agent LLM gateway: provider `openai`, credential `kai-api-keys`/`OPENAI_API_KEY`, model name as above, `contextWindow: 262144` (the served length), tier `efficient`; the endpoint is a placeholder until the hook writes it |
| Job (Sync hook) | `configure-mta-ai` | `openshift-mta` | Wave 11; see How |

### Platform SSO and workspace configuration

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount, Role, RoleBinding, ClusterRole, ClusterRoleBinding | `job-configure-mta-sso` | `openshift-mta`, (cluster) | Hook RBAC (wave 10): `identityproviders` get/create/patch; Deployments get/list/patch; `get` on the two named Secrets; `patch` on `mta-idp-client-secret`; Secret `create`; Routes get/list; ConsoleLink `mta` get/patch |
| Job (Sync hook) | `job-configure-mta-platform-sso` | `openshift-mta` | Wave 10; see How |
| ConfigMap (generated) | `mta-ai-bootstrap-<hash>` | `openshift-mta` | `configure-ai.py`, `secret_writer.py` |
| ServiceAccount, ClusterRole, ClusterRoleBinding, Role/RoleBinding in `wksp-kubeadmin`, `wksp-ai-admin`, `wksp-ai-developer` | `job-mta-hub-workspace-config` | various | PostSync hook RBAC (wave 25): routes get/list; create, or get/patch/update, of ConfigMap `mta-hub-config` |
| Job (PostSync hook) | `job-mta-hub-workspace-config` | `openshift-mta` | Writes `MTA_HUB_URL` (the external Route URL) to `mta-hub-config` in the three workspace namespaces |

All hooks use `BeforeHookCreation,HookSucceeded`.

### Controller sizing (`controller-sizing/`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| OperatorGroup, Subscription | `openshift-vertical-pod-autoscaler`, `vertical-pod-autoscaler` | `openshift-vertical-pod-autoscaler` | Red Hat VPA Operator, channel `stable`, Automatic, `startingCSV: vertical-pod-autoscaler.v4.22.0-202609291750` (waves 1–2) |
| VerticalPodAutoscalerController | `default` | `openshift-vertical-pod-autoscaler` | Keeps the cluster default `minReplicas: 2` (wave 8) |
| VerticalPodAutoscaler | `mta-agentic-controller` | `openshift-mta` | Targets only `Deployment/agentic-controller`, container `manager`; memory requests and limits, request 256–512Mi; `updateMode: Recreate`, `minReplicas: 1`; other containers `Off` (wave 9) |

## How

- **Installation.** `stable-v8.3` with Manual approval pins the patch level. This component's own `approve-installplan` Sync hook approves the plan only if every CSV in it is on its allowlist (`mta-operator.v8.3.2`), and waits until that CSV is installed. Its Role reaches only `openshift-mta` InstallPlans and the `mta-operator` Subscription. Argo CD ignores `startingCSV` after installation.
- **SSO (`job-configure-mta-platform-sso`).** The hook waits for the Keycloak Route and the MTA Route. It gets a token for the `stage070-mta-provisioner` client in the `platform` realm. It ensures the realm roles `role.admin`, `role.architect`, `role.migrator` and `role.project-manager`, assigns `role.admin` to `ai-admin` and `role.architect` to `ai-developer`, and ensures the confidential client `mta-hub` with redirect `https://<mta-host>/oidc/idp/callback`. It creates the optional client scopes `+role.<name>`, each mapped to its realm role. It writes `mta-idp-client-secret` (key `clientSecret`) and applies the `IdentityProvider` `platform-sso` (primary, with the issuer-templated redirect URI and the `+role.*` scopes) [1]. If anything changed, it restarts the Hub Deployment. Finally it patches the ConsoleLink to the live Route. The client secret is generated in the Job and reused while the Secret exists.
- **MaaS key (`configure-mta-ai`).** The Job runs as `mta-maas-provisioner` and authenticates to the MaaS API with its own service-account token. It reads the single `maas.` listener of `maas-default-gateway`. If `kai-api-keys` holds a key that MaaS reports as `active` for this principal and subscription, it keeps the key. Otherwise it mints a new key for subscription `mta-migration-ai`. A foreign owner or subscription, or an unknown status, stops the Job before it mints or revokes anything. It writes `OPENAI_API_KEY` and `MAAS_KEY_ID` through `secret_writer.py`, which stores no `last-applied-configuration`. Then it patches Tackle `kai_llm_baseurl` to `https://maas.<cluster-domain>/v1` and Gateway `maas-qwen` `endpoint` to the bare origin, because the native Gateway appends `/v1/models` itself. Both fields are in `ignoreDifferences`. Rotation (formerly `rotate-credentials.py`, in git history at `82092e01`) uses a short-lived token for the same service account, so that account must stay.
- **Controller sizing.** MTA 8.3 sets the `agentic-controller` memory to 64Mi request and 128Mi limit, and the operator owns that Deployment. The VPA changes the pod's memory at admission instead of editing the Deployment. The reasoning is in [Operations](../../../../docs/OPERATIONS.md#mta-native-agents-and-controller-memory-sizing).
- **Storage.** `rwx_supported: "false"` keeps all Hub volumes RWO. `deploy.sh` requires `gp3-csi` to be the default StorageClass, because MTA 8.3 has no supported RWO class parameter.

Symptoms and recovery: [Lightspeed cannot call MaaS](../../../../docs/TROUBLESHOOTING.md#red-hat-developer-lightspeed-for-mta-cannot-call-maas), [MTA login does not appear](../../../../docs/TROUBLESHOOTING.md#mta-openshift-login-does-not-appear), [Solution Server or controller OOM](../../../../docs/TROUBLESHOOTING.md#mta-83-solution-server-crashes-or-its-agentic-controller-oomkills).

## Validation

`validate.sh` (live, no inference):

- Operator: "mta-operator installed revision" (`mta-operator.v8.3.2`) and "mta-operator.v8.3.2 succeeded".
- Native Agents: "MTA Hub authentication retained", "MTA platform IdP retained", "MTA native agentic component enabled", "MTA native Gateway credential binding", "MTA Gateway uses MaaS canonical model ID", "MTA credential provisioned", "MTA native agentic controller ready", "MTA memory sizing targets only its controller", "MTA memory recommendation is available".
- Lightspeed: "MTA AI proxy enabled", "MTA proxy uses MaaS canonical model ID", "MTA LLM proxy ready without inference", "MTA MaaS origin is unambiguous", "MTA native Gateway uses MaaS origin", "MTA Lightspeed uses versioned MaaS API base".
- Solution Server: "MTA Solution Server explicitly deferred" and "Deferred Solution Server is not crash-looping" (no `kai-api` Deployment).
- `stages/070-advanced-app-platform/validate.sh`: `no_credential_annotation:openshift-mta/kai-api-keys`, `no_retained_secret_annotation:openshift-mta`, `no_master_secret:openshift-mta/job-configure-mta-sso`, and the `stage070-mta-provisioner` client checks (it can read `mta-hub` and cannot administer the `sso` or `master` realms).

`validate.sh --static` checks renders, disjoint components and script syntax; the former offline tests (`product-schemas.test.py`, `stage070-upgrade.test.py`) are in git history at `82092e01`.

By hand (read-only):

```bash
oc get subscription,csv,tackle,identityprovider,gateways.konveyor.io -n openshift-mta
oc get deployment,vpa -n openshift-mta
```

## Alignment with official guidance

| Topic | Official guidance | This repository | Status |
|---|---|---|---|
| Install method and platform | MTA Operator and a `Tackle` instance; OpenShift 4.21–4.22 [1] | Operator Subscription plus `Tackle mta` on OpenShift 4.22 | Aligned |
| Version selection | The install guide gives no channel or approval guidance [1] | `stable-v8.3`, Manual, allow-listed 8.3.2 | Deviation (justified: reviewed patch-level pin) |
| Persistent volumes | Hub database 10Gi RWO; bucket and cache RWX only with `rwx_supported`; `kai-db` 5Gi RWO [1] | `rwx_supported: "false"`; `gp3-csi` RWO volumes (Hub bucket 100Gi RWO observed) | Aligned |
| Authentication | `feature_auth_required` default true; `idp_primary` makes MTA redirect to the IdP (chapter 11) [1] | Both true | Aligned |
| External IdP | Client Secret with key `clientSecret`; `IdentityProvider` CR with `issuer`, `clientId`, `clientSecret`, `redirectURI` containing `/oidc/idp/callback`, `primary`, `scopes`; restart the Hub (9.1–9.2); `${issuer.*}` templates (chapter 12) [1] | All fields as documented; Secret `mta-idp-client-secret`; Hub restarted on change | Aligned |
| Roles | `admin`, `architect`, `migrator`, `project-manager`, delivered as `+role.<name>` client scopes in the token scope [1] | `role.<name>` realm roles mapped to `+role.<name>` optional client scopes | Aligned with the documented scope mechanism; realm role names are a project choice |
| Lightspeed proxy | Technology Preview; Secret `kai-api-keys` with `OPENAI_API_KEY` and `OPENAI_API_BASE`, or `kai_llm_baseurl` in the Tackle CR; `kai_llm_proxy_enabled`, `kai_llm_provider`, `kai_llm_model` (2.4–2.5) [3] | `kai_llm_baseurl` set to the MaaS `/v1` base; key from MaaS | Aligned |
| Solution Server | Optional, Technology Preview (1.3) [3] | Disabled; database kept | Deviation (justified: vendor dependency defect, see [stage README](../../../../stages/070-advanced-app-platform/README.md)) |
| Native Agents | Developer Preview; needs the Agent Sandbox Operator, SCM push access, `agentic_enabled`; `konveyor.io/v1alpha1` Gateway with `provider`, `endpoint` (base URL), `credentialRef`, `model` (chapter 14) [2] | As documented. The Secret is `kai-api-keys`/`OPENAI_API_KEY`, not the example `openai-credentials`/`api-key` | Aligned (`credentialRef.key` is a documented field); Developer Preview stays unqualified with models stopped |
| Controller memory | VPA modes include `Recreate`; `Auto` is deprecated (2.5) [4] | `Recreate`, memory only, one container | Aligned. The per-policy `minReplicas` override is checked against the 4.22 CRD schema in tests; Red Hat doc text for it was not verified |
| MaaS subscription | `MaaSSubscription` (owner, `modelRefs`, `tokenRateLimits`) and `MaaSAuthPolicy` (`subjects`, `modelRefs`) are both required; keys are subscription-bound [5] | Both declared for one service account; key bound to `mta-migration-ai` | Aligned (documented examples use groups; this uses a single service-account user) |

## References

1. Installing the Migration Toolkit for Applications, chapters 3, 8, 9, 11 and 12, MTA 8.3. https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/installing_the_migration_toolkit_for_applications/index
2. Configuring and managing the MTA user interface, chapter 14 "MTA agents", MTA 8.3. https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index
3. Configuring and using Red Hat Developer Lightspeed for MTA, 1.1.2, 1.3, 2.4, 2.5, MTA 8.3. https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index
4. Working with pods, 2.5 "Automatically adjust pod resource levels with the vertical pod autoscaler", OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/nodes/working-with-pods
5. Govern LLM access with Models-as-a-Service, 1.1, 1.11, 1.13, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
6. Repository: [Stage 070 README](../../../../stages/070-advanced-app-platform/README.md), [Operations: Stage 070 MTA](../../../../docs/OPERATIONS.md#stage-070--mta-mta-component), [Operations: native Agents and controller sizing](../../../../docs/OPERATIONS.md#mta-native-agents-and-controller-memory-sizing).
