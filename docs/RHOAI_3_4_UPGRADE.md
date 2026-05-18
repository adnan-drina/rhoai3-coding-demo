# Red Hat OpenShift AI 3.4 Upgrade Readiness

This document prepares the demo branch for Red Hat OpenShift AI 3.4 validation.
It is an upgrade-readiness record, not a request to change the live platform.

## Current Branch

- Branch: `codex/rhoai-3-4-demo-upgrade`
- Base branch at creation: `feature/vibe-agentic-workflow-readmes`
- Scope: documentation, validation gates, and upgrade decision cleanup first.
- Live deployment changes: none from this document.

## Source Baseline

Reviewed on 2026-05-18:

- [Red Hat OpenShift AI Self-Managed 3.4 release notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/release_notes/release_notes)
- [Installing and deploying Red Hat OpenShift AI Self-Managed 3.4](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install)
- [Red Hat OpenShift AI Self-Managed life cycle](https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle)
- [Red Hat OpenShift AI supported configurations](https://access.redhat.com/articles/rhoai-supported-configs)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)

Key source findings:

- Red Hat OpenShift AI 3.4 documentation now describes a 3.4 GA release.
- The 3.4 install guide keeps `DataScienceCluster` as the component install and management API.
- The operator follows sequential OLM updates when moving across intermediate versions.
- Models-as-a-Service is a 3.4 capability, but several adjacent demo paths still need support-scope checks before removing demo glue.
- AI Available Assets integration with MaaS is documented as Developer Preview in the 3.4 release notes.

## Current Repo Baseline

The repository is already partially aligned with the target 3.4 platform:

- Stage 010 installs `rhods-operator` from `stable-3.4` with `startingCSV: rhods-operator.3.4.0`.
- Stage 010 uses `DSCInitialization`, `DataScienceCluster`, and the 3.x `Auth` resource.
- Stage 030 uses `LLMInferenceService` and the 3.4 model-serving story.
- Stage 040 assumes operator-owned `maas-api` and `maas-controller`.
- Stage 040 no longer reintroduces the previous upstream `maas-controller` deployment or `maas-api` image override.
- Stage 070 and Stage 100+ consume MaaS through generated OpenAI-compatible endpoint configuration.

The currently connected sandbox, checked on 2026-05-18, reports:

- `Subscription/rhods-operator` channel: `stable-3.4`
- Installed CSV: `rhods-operator.3.4.0`
- `DataScienceCluster/default-dsc`: `Ready`
- `ModelsAsServiceReady`: `True`
- `maas-api` and `maas-controller`: operator-owned `registry.redhat.io/rhoai/*` images

## Upgrade Decisions

- Keep the 3.4 upgrade isolated on this branch until every stage validates.
- Do not merge this branch to `main` while the working demo environment is being used.
- Keep Stage 010 as the owner of the RHOAI operator and `DataScienceCluster`.
- Keep Stage 040 as the owner of demo-facing MaaS policy, subscriptions, observability helpers, and validation.
- Do not re-add upstream MaaS controller deployments or `maas-api` image overrides unless a live schema/product gap is proven again.
- Treat AI Available Assets plus MaaS key generation as a demo validation point with known UI risk until the current empty-key issue is resolved or documented as a browser/UI defect.
- Preserve conservative support language for Developer Preview or Technology Preview features.

## Required Readiness Gates

1. **Static stage validation**

   ```bash
   ./scripts/validate-stage-flow.sh
   bash -n scripts/*.sh
   bash -n stages/*/*.sh
   ```

2. **RHOAI operator and component check**

   ```bash
   oc get subscription rhods-operator -n redhat-ods-operator \
     -o jsonpath='{.spec.channel}{"\n"}{.status.installedCSV}{"\n"}'

   oc get csv -n redhat-ods-operator | grep rhods-operator

   oc get dsc default-dsc \
     -o jsonpath='{.status.phase}{"\n"}{range .status.conditions[*]}{.type}={.status}{"\n"}{end}'
   ```

3. **Operator-owned MaaS check**

   ```bash
   oc get deployment maas-api maas-controller -n redhat-ods-applications \
     -o custom-columns='NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image,READY:.status.readyReplicas'
   ```

   Both images must come from `registry.redhat.io/rhoai/`.

4. **Stage-by-stage live validation**

   ```bash
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   ./stages/020-gpu-infrastructure-private-ai/validate.sh
   ./stages/030-private-model-serving/validate.sh
   GUIDELLM_SKIP_LOAD_TEST=true ./stages/040-governed-models-as-a-service/validate.sh
   ./stages/050-approved-external-model-access/validate.sh
   ./stages/060-mcp-context-integrations/validate.sh
   ./stages/070-controlled-developer-workspaces/validate.sh
   ./stages/080-ai-assisted-application-modernization/validate.sh
   ./stages/090-developer-portal-self-service/validate.sh
   ```

5. **Developer workflow validation**

   - Developer Hub has exactly the intended Stage 100 entry points.
   - Each Developer Hub component opens only its own Dev Spaces workspace.
   - `getting-started-ai-coding` can configure Continue and OpenCode from MaaS.
   - OpenShift MCP works from Continue.
   - MaaS API key generation works through a supported path or has a documented fallback.

## Risks To Track

- **AI Available Assets key dialog:** The Gen AI backend can mint a non-empty `data.key`, but the browser modal has shown an empty field in the live sandbox. Do not route `/gen-ai/api/v1/maas/tokens` directly to the tokens bridge; that bypasses dashboard user-header handling.
- **MaaS token bridge:** Keep the `/maas-api/v1/tokens` compatibility bridge until the product path covers Playground and dashboard token callers without it.
- **External model routing:** Keep provider credential and trust-boundary language explicit. External inference remains governed but not private.
- **GuideLLM path:** Current validation uses the upstream GuideLLM container directly. Treat this as demo tooling unless the Red Hat Evaluation Stack path is adopted.
- **Community Grafana:** The current MaaS dashboard is a disposable demo add-on. Prefer a supported OpenShift monitoring path for a longer-lived environment.

## Rollback

This branch should not change the live cluster until explicitly synced through Argo CD. If a validation sync regresses the demo:

```bash
oc patch application 010-openshift-ai-platform-foundation -n openshift-gitops \
  --type merge -p '{"spec":{"source":{"targetRevision":"main"}}}'

oc patch application 040-governed-models-as-a-service -n openshift-gitops \
  --type merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
```

Patch only the affected applications. Do not bulk-reset all stages unless the
failure affects shared platform state.
