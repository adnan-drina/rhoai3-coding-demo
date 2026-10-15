---
name: mta-lightspeed
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when changing, reviewing, or debugging Red Hat Developer Lightspeed for
  MTA in this demo: the Tackle LLM proxy flags (kai_llm_proxy_enabled,
  kai_llm_provider, kai_llm_model, kai_llm_baseurl), the kai-api-keys Secret
  minted from the owner-bound MaaS subscription mta-migration-ai, the
  deliberately disabled Solution Server, IDE agent mode against MaaS, and
  emergency proxy shutdown. Do NOT use for native Hub Agents and the
  konveyor.io Gateway (use mta-ui), the MTA install (use mta-install), MaaS
  subscriptions in general (use rhoai-maas-governance), or the VS Code
  extension install (use mta-vscode).
---

# Developer Lightspeed for MTA

Thin skill: repo decisions and pitfalls here, product behavior in the linked
MTA 8.3 sections. Lightspeed proxy and Solution Server are Technology
Preview. Detailed record: `gitops/stages/070-advanced-app-platform/mta/README.md`.

## When to use

- A change touches the AI fields of `mta/mta-instance/tackle.yaml` or
  `mta/jobs/configure-ai.yaml` / `configure-ai.py`.
- The `llm-proxy` cannot reach MaaS, or the MaaS key in `kai-api-keys` is
  rotated or refused.
- Someone proposes re-enabling the Solution Server.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Proxy on: `kai_llm_proxy_enabled: true`, `kai_llm_provider: openai`, `kai_llm_model: publishers/internal-models/models/qwen3-8-27b` (the MaaS canonical id) | `gitops/stages/070-advanced-app-platform/mta/mta-instance/tackle.yaml` | [Enable LLM proxy in Tackle][proxy], [Provider settings][provider] |
| `kai_llm_baseurl` written at runtime to `https://maas.<cluster-domain>/v1`; Argo CD ignores the field | `mta/jobs/configure-ai.py`, Application `ignoreDifferences` | [Enable LLM proxy in Tackle][proxy] |
| Model credential: Secret `kai-api-keys` key `OPENAI_API_KEY` (+ `MAAS_KEY_ID`), minted by `configure-mta-ai` as ServiceAccount `mta-maas-provisioner`; existing active key kept, foreign owner/subscription stops the Job | `mta/jobs/configure-ai.yaml`, `mta/secret_writer.py` | [Configure the model secret key][secret] |
| MaaS access: `MaaSSubscription` + `MaaSAuthPolicy` `mta-migration-ai` for that ServiceAccount, `qwen3-8-27b`, 5,000,000 tokens/h | `mta/jobs/configure-ai.yaml` | see `rhoai-maas-governance` |
| Solution Server disabled (`kai_solution_server_enabled: false`); proxy kept so `kai-db` and its PVC survive | `mta/mta-instance/tackle.yaml` | [About the Solution Server][ss] |
| Private model hosting is the IP-protection posture: all traffic goes to the governed MaaS gateway | Stage 040, `mta/jobs/configure-ai.yaml` | [Self-managed hosting][selfhost], [LLM on OpenShift AI][rhoai] |
| Key rotation keeps the same ServiceAccount (`rotate-credentials.py`) | `stages/070-advanced-app-platform/rotate-credentials.py` | — |

## Procedure

1. Change Tackle AI fields or the provisioning Job in Git only; keep the
   model id equal to the MaaS canonical id
   (`stage070-upgrade.test.py::test_mta_consumers_use_the_governed_model_id`).
2. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh          # "MTA Developer Lightspeed proxy" rows
   ./stages/070-advanced-app-platform/validate.sh --static
   ```

3. Read-only checks (never print the key):

   ```bash
   oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_baseurl}{"\n"}'
   oc get deployment llm-proxy -n openshift-mta
   oc get maassubscription,maasauthpolicy mta-migration-ai -n models-as-a-service
   ```

4. Emergency isolation follows the product procedure ([Disable the proxy (CLI)][shutcli]);
   the GitOps value must be changed too, or self-heal re-enables it.

## Pitfalls

- Lightspeed keeps the `/v1` base; the native Gateway endpoint must be the
  bare origin. Reusing one for the other gives `/v1/v1/models`:
  `docs/TROUBLESHOOTING.md#mta-83-solution-server-crashes-or-its-agentic-controller-oomkills`.
- Proxy cannot call MaaS (placeholder key, invalid key, proxy not restarted):
  `docs/TROUBLESHOOTING.md#red-hat-developer-lightspeed-for-mta-cannot-call-maas`
  (entry still names Stage 130; the Job is now `configure-mta-ai` in `070-mta`).
- The Solution Server image lacks `greenlet` (vendor defect); do not
  re-enable it to reproduce the crash.
- Models may be stopped during platform work: a failed inference is not a
  configuration verdict until models run and the functional checks pass.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Concepts, Solution Server, agent mode | [Overview][overview], [Solution Server][ss], [Agent AI][agent], [Enable agent mode][agentmode] |
| Proxy setup | [Prerequisites][prereq], [Proxy workflow][proxyflow], [Model secret][secret], [Enable proxy][proxy] |
| Models and data protection | [Supported providers][providers], [Code transmission][ip], [Self-managed hosting][selfhost], [LLM on OpenShift AI][rhoai] |
| IDE settings | [IDE settings][ide], [Profile settings][profile] |
| Logs and monitoring | [Logs][logs], [Proxy logs][proxylogs] |
| Emergency shutdown | [Overview][shut], [CLI][shutcli], [Re-enable][reenable] |

## Related skills

`mta-ui`, `mta-vscode`, `mta-install`, `rhoai-maas-governance`.

[overview]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#how-developerlightspeed-works_intro-to-the-developer-lightspeed
[ss]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#solution-server_dl-context
[agent]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#agent-ai_solution-server
[agentmode]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#enabling-agent-mode_agent-ai
[prereq]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#prerequisites_getting-started
[proxyflow]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-proxy-workflow_getting-started
[secret]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#tackle-llm-secret_getting-started
[proxy]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#tackle-enable-llm-proxy_getting-started
[providers]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#supported-large-language-models-and-providers_configuring-llm
[ip]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#ip-protection-risk-disclosure_configuring-llm
[selfhost]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#ip-protection-mitigation_configuring-llm
[rhoai]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-service-openshift-ai_configuring-llm
[provider]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-provider-settings_configuring-llm
[ide]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#configuring-developer-lightspeed-ide-settings_configuring-dev-lightspeed-ide
[profile]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#configuring-developer-lightspeed-profile-settings_configuring-dev-lightspeed-ide
[logs]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#developer-lightspeed-logs_mta-developer-lightspeed
[proxylogs]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-proxy-log-access_assembly-llm-proxy-interaction-monitoring
[shut]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#llm-proxy-shutdown-overview_assembly-emergency-llm-proxy-shutdown
[shutcli]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#disable-llm-proxy-cli_assembly-emergency-llm-proxy-shutdown
[reenable]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index#reenable-llm-proxy_assembly-emergency-llm-proxy-shutdown
