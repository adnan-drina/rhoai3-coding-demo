# Fresh deployment operator lifecycle

This source policy applies to future deployments. The existing cluster applications remain pinned to their already deployed immutable revisions; this change does not approve an existing InstallPlan or upgrade an operator.

All 22 tracked platform Subscriptions use native Automatic approval. Deployment preflight checks the selected package, catalog source, channel and compatible offered release. Deployment waits for the installed/current CSV to converge and reach Succeeded. Historical `startingCSV` selections are removed from the Automatic subscriptions: OLM selects the channel head after compatible-version preflight. A startingCSV would only select an initial bundle, not lock the version. Automatic OLM follows future channel updates, including dependency resolution, so exact immutable versions cannot be guaranteed by this policy. Our deployment-time compatibility check does not constrain future OLM automatic updates. Rolling channels can move outside the tested family after deployment; validation fails clearly rather than claiming that newer product is qualified.

| Component | Qualified installed baseline | Source channel | Approval | Channel boundary |
| --- | --- | --- | --- | --- |
| RHOAI | 3.5.1 | stable-3.5 | Automatic | 3.5 |
| GitOps | 1.21.5 | gitops-1.21 | Automatic | 1.21 |
| ODF | 4.22.5-rhodf | stable-4.22 | Automatic | OCP 4.22 |
| Cluster Observability | 1.5.3 | stable | Automatic | Rolling; preflight 1.5 |
| OpenTelemetry | 0.158.0-2 | stable | Automatic | Rolling; preflight 0.158 |
| Tempo | 0.22.0-2 | stable | Automatic | Rolling; preflight 0.22 |
| NFD | 4.22.0-202609212027 | stable | Automatic | Rolling; preflight OCP 4.22; newer build offered |
| NVIDIA GPU | 26.7.1 | v26.7 | Automatic | 26.7 |
| Kueue | 1.4.2 | stable-v1.4 | Automatic | 1.4; 1.4.3 offered, not live-qualified |
| LeaderWorkerSet | 1.0.1 | stable-v1.0 | Automatic | 1.0 |
| Connectivity Link | 1.4.3 | stable | Automatic | Rolling; preflight 1.4 |
| Authorino | 1.4.3 | stable | Automatic | Rolling; preflight 1.4 |
| DNS | 1.4.2 | stable | Automatic | Rolling; preflight 1.4; Red Hat catalog |
| Limitador | 1.4.2 | stable | Automatic | Rolling; preflight 1.4 |
| Service Mesh | 3.4.3 | stable-3.4 | Automatic | 3.4 |
| Agent Sandbox | 0.9.0 | preview-0.9 | Automatic | 0.9 DP; runtime functional gates remain separate |

Later Stage070 already uses Automatic. Its source channels are Dev Spaces `stable`, RHBK `stable-v26`, MTA `stable-v8.2`, Pipelines `pipelines-1.22`, RHTAS `stable-v1.4`, and RHDH `fast-1.9`. They are deferred/unqualified rather than added to this fresh platform acceptance. The catalog currently offers Dev Spaces 3.30.2 rather than historical 3.28, RHBK 26.6.7, MTA 8.2.2, Pipelines 1.22.6, RHTAS 1.4.3, and RHDH 1.9.9 rather than historical documentation 1.10. This task does not change those product selections. Provisioner-owned cert-manager/Keycloak/Lightspeed and disconnected Lightspeed drafts are not silently adopted or published.

## Credential-mode applicability

The normal fresh demo provisioning contract is standard cluster credentials, persisted as non-secret `RHOAI_OPERATOR_CREDENTIAL_MODE=standard` in the environment template. This is not a per-run approval. Missing or other values fail preflight; advertised CloudCredential Manual mode or an explicit service-account issuer also fail before writing operator intent. An empty credentialsMode or missing Secret does not prove effective Mint mode: the current effective mode is unknown, and the standard input is a provisioner declaration, not discovered proof. AWS STS, Azure Workload Identity and GCP Workload Identity clusters must use the cloud-specific documented Manual lifecycle; this automatic demo path does not bypass that requirement. User OpenShift OIDC and temporary workstation cloud credentials are separate concerns.

## Shared namespaces and dependencies

The unused MCP Gateway prerequisite is retired from future installation; its former shared OperatorGroup remains untouched. OLM InstallPlans are atomic and can include other Subscriptions in the same namespace. A foreign Manual Subscription can hold Automatic subscriptions; preflight refuses that case rather than approving an unrelated plan or changing its policy. All repository-owned selections in a normal fresh namespace use Automatic. Previously reviewed combined upgrades are historical live actions, not required manual steps in the future path.

No deployment helper in the normal 010/020/040/060 flow patches InstallPlan approval. The historical `approve-controller.py` remains an explicit manual audit/recovery utility and is not invoked by normal deployment. `approve-operators.sh` is a backward-compatible name for a read-only Automatic readiness wait.

## Evidence and limits

Read-only live inventory established package/catalog/channel closure and installed baselines. All current repository Applications use immutable source SHAs; none follows the development branch. Eight native renders and shell/Python/embedded syntax checks passed. Actual checker entrypoint fixtures cover compatible newer versions, pending upgrades, unsupported families/preview suffixes and legitimate numeric rebuild/ODF suffixes. The guarded read-only Stage010 catalog preflight passed against the current cluster, using the explicit standard provisioning contract; this is offered-version evidence, not a fresh install. No live policy was applied, no InstallPlan approved, and no fresh end-to-end installation was performed. Native CSV/operator readiness is separate from model, runtime, gateway and user-interface functional acceptance.

Official sources: [OCP 4.22 operator installation and approval](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/operators/administrator-tasks), [starting versions](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/operators/user-tasks), [dependency resolution](https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/operators/understanding-operators), and [RHOAI 3.5 update channels](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/understanding-update-channels_install).
