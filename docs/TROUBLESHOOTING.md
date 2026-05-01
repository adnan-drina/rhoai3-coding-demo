# Troubleshooting Guide

This guide collects operational failure modes for the workshop. Keep the README files educational; put recovery procedures here.

Use this format for new entries:

````markdown
## Symptom

**Affected stage:** Stage NNN

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

Start with the failing stage's validation script:

```bash
./stages/NNN-*/validate.sh
```

Then inspect Argo CD:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

For a specific app:

```bash
APP=040-governed-models-as-a-service
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced" or .health.status != "Healthy") | [.kind,.namespace,.name,.status,.health.status,.message] | @tsv'
```

Check pods:

```bash
oc get pods -A | egrep 'CrashLoopBackOff|ImagePullBackOff|Error|Pending'
```

## Argo CD App Is OutOfSync

**Affected stage:** Any

**Likely cause:** Operator-managed fields, PostSync patch jobs, dynamic route values, or manual changes.

**Diagnose:**

```bash
APP=090-developer-portal-self-service
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'
```

**Recover:**

- If drift is expected and cluster-specific, add a narrow `ignoreDifferences` entry to the Argo CD Application.
- If drift is not expected, fix the Git manifest or re-sync the app.
- Avoid broad ignores such as a whole CR `spec` unless the operator truly owns that full field.

## Operator CSV Not Succeeded

**Affected stage:** Any operator install stage

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
- Re-run the stage validation after the CSV reaches `Succeeded`.

## GPU Nodes Do Not Appear

**Affected stage:** Stage 020

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
- Re-run `./stages/020-gpu-infrastructure-private-ai/validate.sh`.

## MaaS Tab Shows No Models

**Affected stage:** Stage 040

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
./stages/040-governed-models-as-a-service/validate.sh
```

## MaaS Gateway Is Not Reachable

**Affected stage:** Stage 040

**Likely cause:** Gateway hostname or HTTPS listener not patched, route not admitted, or gateway policy not ready.

**Diagnose:**

```bash
oc get gateway maas-default-gateway -n openshift-ingress -o yaml
oc get httproute -A | grep -i maas
oc get authpolicy,tokenratelimitpolicy -n maas
```

**Recover:**

- Confirm the Stage 040 PostSync jobs completed.
- Confirm the Gateway has an HTTPS listener with the expected cluster domain.
- Re-sync Stage 040 if the patch job did not run.

## Red Hat Developer Lightspeed for MTA Cannot Call MaaS

**Affected stage:** Stage 080

**Likely cause:** `kai-api-keys` contains placeholder values, the MaaS API key is invalid, or `llm-proxy` did not restart after secret patching.

**Diagnose:**

```bash
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d
oc get deployment llm-proxy -n openshift-mta -o yaml
oc logs deployment/llm-proxy -n openshift-mta --tail=100
```

**Recover:**

- Re-run or re-sync Stage 080 so the PostSync job provisions the MaaS key and restarts `llm-proxy`.
- Confirm `./stages/080-ai-assisted-application-modernization/validate.sh` reports the MaaS credential checks as passing.

## MTA OpenShift Login Does Not Appear

**Affected stage:** Stage 080

**Likely cause:** OAuthClient redirect URI not patched, Keycloak identity provider not configured, or MTA route not available when the PostSync job ran.

**Diagnose:**

```bash
oc get oauthclient mta-keycloak -o yaml
oc get route mta -n openshift-mta
oc logs job/job-patch-mta-maas-url -n openshift-mta --tail=200
```

**Recover:**

- Re-sync Stage 080.
- Confirm the MTA route exists before the auth configuration job runs.
- Re-run Stage 080 validation.

## Red Hat Developer Hub Catalog Does Not Load Coolstore

**Affected stage:** Stage 090

**Likely cause:** RHDH backend is not allowed to read the raw GitHub catalog URL, the catalog location is not reachable, or `RHDH_CATALOG_URL` does not match the GitOps revision deployed by Argo CD.

**Diagnose:**

```bash
oc logs deployment/backstage-developer-hub -n rhdh --tail=200 | grep -i catalog
oc get configmap app-config-rhdh -n rhdh -o yaml
oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_CATALOG_URL}' | base64 -d; echo
oc get application 090-developer-portal-self-service -n openshift-gitops \
  -o jsonpath='{.spec.source.repoURL}{" "}{.spec.source.targetRevision}{"\n"}'
```

Look for errors like:

```text
is not allowed. You may need to configure an integration for the target host, or add it to backend.reading.allow
```

**Recover:**

- Add a narrow `backend.reading.allow` entry or configure the GitHub integration.
- Re-sync Stage 090 so the configure hook derives `RHDH_CATALOG_URL` from the live Argo CD Application source.
- Confirm the Stage 090 hook ServiceAccount can `get` `applications.argoproj.io` in `openshift-gitops`.
- Restart the RHDH deployment.
- Re-run Stage 090 validation after adding catalog checks.

## Red Hat Developer Hub Is Healthy But Stage 090 Is OutOfSync

**Affected stage:** Stage 090

**Likely cause:** Operator-defaulted fields differ from Git, or PostSync jobs patched dynamic fields.

**Diagnose:**

```bash
oc get application 090-developer-portal-self-service -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'

oc get backstage developer-hub -n rhdh -o yaml
```

**Recover:**

- Make Git match stable operator defaults where possible.
- Add narrow `ignoreDifferences` only for dynamic cluster-specific values.
- Avoid ignoring the full Backstage spec.

## Red Hat OpenShift Dev Spaces Workspace Does Not Start

**Affected stage:** Stage 070

**Likely cause:** DevWorkspace operator issue, image pull problem, insufficient workspace resources, or postStart command failure.

**Diagnose:**

```bash
oc get devworkspace -A
oc get pods -n wksp-ai-developer
oc describe devworkspace exercises -n wksp-ai-developer
oc logs -n wksp-ai-developer <workspace-pod> -c tooling-container --tail=100
```

**Recover:**

- Restart the workspace from the Red Hat OpenShift Dev Spaces dashboard.
- Confirm resource requests/limits are sufficient.
- Re-run Stage 070 validation.

## References

- [OpenShift troubleshooting documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/support/troubleshooting)
- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Migration Toolkit for Applications documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1)
