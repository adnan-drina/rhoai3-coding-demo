---
name: rhoai-installation-troubleshooting
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when Stage 010 cannot install or start OpenShift AI: the rhods-operator
  Subscription or CSV in redhat-ods-operator is not Succeeded, the operator
  image cannot be pulled, the operator reports unsupported infrastructure,
  default-dsci or default-dsc never become Ready, the Auth CR blocks a
  reinstall, the dashboard route does not answer after install, or the
  010-rhoai-operator / 010-rhoai-platform Applications are not Synced and
  Healthy. Maps symptoms to the official 3.5 installation troubleshooting
  sections and to this repo's GitOps checks. Do NOT use for day-2 component
  failures (use rhoai-troubleshoot), operator logging or audit review (use
  rhoai-logs-and-audit-records), or decommissioning (use rhoai-uninstallation).
---

# RHOAI Installation Troubleshooting

Thin skill: how an install failure shows up in this repo and where to look,
with the product symptoms and remedies in the linked OpenShift AI 3.5
"Troubleshooting reference: Installation" chapter.

## When to use

- `./stages/010-openshift-ai-platform-foundation/validate.sh` fails on the
  RHOAI CSV, DSCI, DSC, `Auth` or dashboard route checks.
- `deploy.sh` times out waiting for the `rhods-operator` CSV.
- A reinstall after an uninstall does not converge.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Check GitOps first: Application sync and health at the reviewed revision, then the OLM objects, then the operator | `stages/010-openshift-ai-platform-foundation/validate.sh`, `docs/TROUBLESHOOTING.md#general-diagnostic-flow` | [Installation troubleshooting][ts] |
| Catalog, channel and minimum version are checked before deploy (`stable-3.5`, `3.5.1`) | `check_operator_policy` in `scripts/lib.sh`, `stages/010-openshift-ai-platform-foundation/deploy.sh` | [Install the Operator by CLI][op-cli] |
| Operator auto-creation of the DSCI is disabled (`DISABLE_DSC_CONFIG=true`); `default-dsci` comes from `010-rhoai-platform` at wave 2, DSC at 3, `Auth` at 4 | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/subscription.yaml`, `.../rhoai-platform/` | [Install components by CLI][comp-cli] |
| Operator and platform are applied in one batch; order comes from Argo CD retry and `SkipDryRunOnMissingResource`, so early `CRD not found` sync errors are expected and transient | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/README.md` (How: Ordering) | — (repo GitOps rule) |
| The `Auth` CR `auth` is managed in Git, not left over by hand | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/auth.yaml` | [Reinstalling fails][reinstall] |
| Support escalation: collect evidence (Subscription, CSV, InstallPlan, operator logs, DSC/DSCI conditions); remedies that say "contact Red Hat Support" are not replaced by local fixes | — | [Installation troubleshooting][ts] |

## Procedure

After the OpenShift safety guard in `AGENTS.md`:

1. Run `./stages/010-openshift-ai-platform-foundation/validate.sh` and note the
   first failing check.
2. GitOps state:

   ```bash
   oc get applications.argoproj.io -n openshift-gitops 010-rhoai-operator 010-rhoai-platform \
     -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status,REV:.status.sync.revision'
   ```

3. OLM and operator:

   ```bash
   oc get subscription rhods-operator -n redhat-ods-operator -o jsonpath='{.spec.channel} {.status.state} {.status.installedCSV}{"\n"}'
   oc get csv,installplan -n redhat-ods-operator
   oc get events -n redhat-ods-operator --sort-by=.lastTimestamp | tail -20
   oc logs -n redhat-ods-operator -l name=rhods-operator --tail=200
   ```

4. Platform CRs: `oc get dsci default-dsci`, `oc get dsc default-dsc`,
   `oc get auths.services.platform.opendatahub.io auth`; read their
   `status.conditions`.
5. Match the symptom to a row below, then fix in Git and redeploy; record any
   live action and its Git follow-up in `docs/TROUBLESHOOTING.md`.

| Symptom | Repo entry | Official section |
|---|---|---|
| CSV not `Succeeded`, InstallPlan pending | `docs/TROUBLESHOOTING.md#operator-csv-not-succeeded` | — |
| Operator pod cannot pull its image | events in `redhat-ods-operator` | [Operator image cannot be retrieved][pull] |
| Subscription names a CSV that no longer exists | `docs/TROUBLESHOOTING.md#operator-subscription-claims-a-csv-that-no-longer-exists` | — |
| Approving a plan upgrades other operators | `docs/TROUBLESHOOTING.md#installplan-approval-carries-hidden-passenger-csvs` | — |
| Argo CD Synced but objects missing | `docs/TROUBLESHOOTING.md#argo-cd-reports-synced-but-new-manifests-are-missing` | — |
| Operator log says the infrastructure is unsupported | check `rhoai-platform-planning` | [Unsupported infrastructure][infra] |
| DSC/DSCI or Notebooks CR creation fails | `010-rhoai-platform` resources | [OpenShift AI CR fails][cr], [Notebooks CR fails][nb] |
| Dashboard not reachable after install | `validate.sh` route check | [Dashboard not accessible][dash] |
| Reinstall fails on a leftover `Auth` CR | `rhoai-uninstallation` | [Reinstalling fails][reinstall] |

## Pitfalls

- The `Auth` CR holds the dashboard admin and user groups (`auth.yaml`);
  delete it only for the documented reinstall case, after an uninstall.
- Follow a dedicated-admins RBAC, ODH parameter secret or ClusterExtensions
  section only when the exact error it quotes appears; these symptoms have not
  been seen in this repo.
- Do not mutate Argo CD-managed objects to "unstick" an install; self-heal
  reverts them. Fix the manifest or the Application.
- A CSV `Succeeded` does not prove the DSC is Ready; check both.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Troubleshooting reference: Installation][ts] |
| Operator retrieval and infrastructure | [Image cannot be retrieved][pull], [Unsupported infrastructure][infra], [ClusterExtensions redirect][clusterext] |
| CR creation and access | [OpenShift AI CR fails][cr], [Notebooks CR fails][nb], [Dashboard not accessible][dash] |
| Reinstall and add-on paths | [Reinstalling fails][reinstall], [dedicated-admins RBAC][rbac], [ODH parameter secret][secret] |
| Install procedure | [Install the Operator by CLI][op-cli], [Install components by CLI][comp-cli] |

## Related skills

`rhoai-self-managed-installation`, `rhoai-update-channels`,
`rhoai-logs-and-audit-records`, `rhoai-troubleshoot`, `inspect-cluster`,
`rhoai-uninstallation`.

[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#troubleshooting-common-installation-problems_install
[clusterext]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing_certain_operators_redirects_to_clusterextensions_page
[pull]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_redhat_openshift_ai_operator_cannot_be_retrieved_from_the_image_registry
[infra]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#openshift_ai_does_not_install_on_unsupported_infrastructure
[cr]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_creation_of_the_openshift_ai_custom_resource_cr_fails
[nb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_creation_of_the_openshift_ai_notebooks_custom_resource_cr_fails
[dash]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_openshift_ai_dashboard_is_not_accessible
[reinstall]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#reinstalling_openshift_ai_fails_with_an_error
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_dedicated_admins_role_based_access_control_rbac_policy_cannot_be_created
[secret]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#the_odh_parameter_secret_does_not_get_created
[op-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-cli_operator-install
[comp-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-cli_component-install
