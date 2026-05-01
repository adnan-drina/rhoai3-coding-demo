# Troubleshooting Guide

This guide collects operational failure modes for the workshop. Keep the README files educational; put recovery procedures here.

Use this format for new entries:

````markdown
## Symptom

**Affected step:** Step NN

**Likely cause:** ...

**Diagnose:**
```bash
...
```

**Recover:**
```bash
...
```
````

## General Diagnostic Flow

Start with the failing step's validation script:

```bash
./steps/step-XX-*/validate.sh
```

Then inspect Argo CD:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

For a specific app:

```bash
APP=step-03-llm-serving-maas
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced" or .health.status != "Healthy") | [.kind,.namespace,.name,.status,.health.status,.message] | @tsv'
```

Check pods:

```bash
oc get pods -A | egrep 'CrashLoopBackOff|ImagePullBackOff|Error|Pending'
```

## Argo CD App Is OutOfSync

**Affected step:** Any

**Likely cause:** Operator-managed fields, PostSync patch jobs, dynamic route values, or manual changes.

**Diagnose:**

```bash
APP=step-06-developer-hub
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'
```

**Recover:**

- If drift is expected and cluster-specific, add a narrow `ignoreDifferences` entry to the Argo CD Application.
- If drift is not expected, fix the Git manifest or re-sync the app.
- Avoid broad ignores such as a whole CR `spec` unless the operator truly owns that full field.

## Operator CSV Not Succeeded

**Affected step:** Any operator install step

**Likely cause:** InstallPlan pending, catalog issue, insufficient permissions, or dependency operator not ready.

**Diagnose:**

```bash
oc get subscription,csv,installplan -A
oc describe subscription <name> -n <namespace>
oc describe installplan <name> -n <namespace>
```

**Recover:**

- If install approval is manual, approve the InstallPlan.
- If the package or channel is unavailable, confirm the package manifest in `openshift-marketplace`.
- Re-run the step validation after the CSV reaches `Succeeded`.

## GPU Nodes Do Not Appear

**Affected step:** Step 02

**Likely cause:** MachineSet provisioning delay, cloud quota issue, instance type unavailable, or Machine API failure.

**Diagnose:**

```bash
oc get machineset -n openshift-machine-api | grep -i gpu
oc get machine -n openshift-machine-api | grep -i gpu
oc get nodes -l node-role.kubernetes.io/gpu
oc describe machineset <gpu-machineset> -n openshift-machine-api
```

**Recover:**

- Wait if machines are still provisioning.
- Check cloud quota and instance availability.
- Inspect Machine API events.
- Re-run `./steps/step-02-gpu-infra/validate.sh`.

## MaaS Tab Shows No Models

**Affected step:** Step 03

**Likely cause:** `maas-api` is not using the expected upstream-compatible configuration, `MaaSModelRef` resources are not ready, or the tenant reconciler has not recreated resources.

**Diagnose:**

```bash
oc get deployment maas-api -n redhat-ods-applications \
  -o jsonpath='{.metadata.labels.maas\.opendatahub\.io/tenant-name}{"\n"}'

oc get deployment maas-api -n redhat-ods-applications \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="MAAS_SUBSCRIPTION_NAMESPACE")].value}{"\n"}'

oc get maasmodelref -n maas
oc get externalmodel -n maas
```

**Recover:**

If the `maas-api` deployment is stale, delete it and let the tenant reconciler recreate it:

```bash
oc delete deployment maas-api -n redhat-ods-applications
oc annotate tenant default-tenant -n models-as-a-service \
  recovery.rhoai-demo.io/restarted-at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
oc rollout status deployment/maas-api -n redhat-ods-applications
```

Then re-run:

```bash
./steps/step-03-llm-serving-maas/validate.sh
```

## MaaS Gateway Is Not Reachable

**Affected step:** Step 03

**Likely cause:** Gateway hostname or HTTPS listener not patched, route not admitted, or gateway policy not ready.

**Diagnose:**

```bash
oc get gateway maas-default-gateway -n openshift-ingress -o yaml
oc get httproute -A | grep -i maas
oc get authpolicy,tokenratelimitpolicy -n maas
```

**Recover:**

- Confirm the Step 03 PostSync jobs completed.
- Confirm the Gateway has an HTTPS listener with the expected cluster domain.
- Re-sync Step 03 if the patch job did not run.

## MTA Developer Lightspeed Cannot Call MaaS

**Affected step:** Step 05

**Likely cause:** `kai-api-keys` contains placeholder values, the MaaS API key is invalid, or `llm-proxy` did not restart after secret patching.

**Diagnose:**

```bash
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d
oc get deployment llm-proxy -n openshift-mta -o yaml
oc logs deployment/llm-proxy -n openshift-mta --tail=100
```

**Recover:**

- Re-run or re-sync Step 05 so the PostSync job provisions the MaaS key and restarts `llm-proxy`.
- Confirm `./steps/step-05-mta/validate.sh` reports the MaaS credential checks as passing.

## MTA OpenShift Login Does Not Appear

**Affected step:** Step 05

**Likely cause:** OAuthClient redirect URI not patched, Keycloak identity provider not configured, or MTA route not available when the PostSync job ran.

**Diagnose:**

```bash
oc get oauthclient mta-keycloak -o yaml
oc get route mta -n openshift-mta
oc logs job/job-patch-mta-maas-url -n openshift-mta --tail=200
```

**Recover:**

- Re-sync Step 05.
- Confirm the MTA route exists before the auth configuration job runs.
- Re-run Step 05 validation.

## Developer Hub Catalog Does Not Load Coolstore

**Affected step:** Step 06

**Likely cause:** RHDH backend is not allowed to read the raw GitHub catalog URL, or the catalog location is not reachable.

**Diagnose:**

```bash
oc logs deployment/backstage-developer-hub -n rhdh --tail=200 | grep -i catalog
oc get configmap app-config-rhdh -n rhdh -o yaml
```

Look for errors like:

```text
is not allowed. You may need to configure an integration for the target host, or add it to backend.reading.allow
```

**Recover:**

- Add a narrow `backend.reading.allow` entry or configure the GitHub integration.
- Restart the RHDH deployment.
- Re-run Step 06 validation after adding catalog checks.

## Developer Hub Is Healthy But Step 06 Is OutOfSync

**Affected step:** Step 06

**Likely cause:** Operator-defaulted fields differ from Git, or PostSync jobs patched dynamic fields.

**Diagnose:**

```bash
oc get application step-06-developer-hub -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'

oc get backstage developer-hub -n rhdh -o yaml
```

**Recover:**

- Make Git match stable operator defaults where possible.
- Add narrow `ignoreDifferences` only for dynamic cluster-specific values.
- Avoid ignoring the full Backstage spec.

## Dev Spaces Workspace Does Not Start

**Affected step:** Step 04

**Likely cause:** DevWorkspace operator issue, image pull problem, insufficient workspace resources, or postStart command failure.

**Diagnose:**

```bash
oc get devworkspace -A
oc get pods -n wksp-ai-developer
oc describe devworkspace exercises -n wksp-ai-developer
oc logs -n wksp-ai-developer <workspace-pod> -c tooling-container --tail=100
```

**Recover:**

- Restart the workspace from the Dev Spaces dashboard.
- Confirm resource requests/limits are sufficient.
- Re-run Step 04 validation.

## References

- [OpenShift troubleshooting documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/support/troubleshooting)
- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Migration Toolkit for Applications documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1)
