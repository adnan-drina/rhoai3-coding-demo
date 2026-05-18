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
- [Red Hat OpenShift AI Self-Managed 3.4 MaaS documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/govern_llm_access_with_models-as-a-service/govern_llm_access_with_models-as-a-service)
- [Installing and deploying Red Hat OpenShift AI Self-Managed 3.4](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install)
- [Red Hat OpenShift AI Self-Managed life cycle](https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle)
- [Red Hat OpenShift AI supported configurations](https://access.redhat.com/articles/rhoai-supported-configs)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/sources/Source - Govern LLM Access with Models-as-a-Service OpenShift AI 3.4.md`
- `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/configurations/OpenShift AI Models-as-a-Service Baseline.md`
- `/Users/adrina/Sandbox/rh-brain/Red Hat Brain/wiki/concepts/Models-as-a-Service.md`

Key source findings:

- Red Hat OpenShift AI 3.4 documentation now describes a 3.4 GA release.
- The 3.4 install guide keeps `DataScienceCluster` as the component install and management API.
- The operator follows sequential OLM updates when moving across intermediate versions.
- Models-as-a-Service is present in the Red Hat OpenShift AI 3.4 documentation, but the release notes identify Model-as-a-Service integration as Technology Preview.
- OpenShift AI 3.4 changes the MaaS access model from 3.3 tiers and ConfigMaps to subscriptions, groups, API keys, and custom resources.
- vLLM runtime support for MaaS, MaaS observability dashboard, external models, and external OIDC authentication are documented as Technology Preview features.
- AI Available Assets integration with MaaS is documented as Developer Preview in the 3.4 release notes.

## Current Repo Baseline

The repository is already partially aligned with the target 3.4 platform:

- Stage 010 installs `rhods-operator` from `stable-3.4` with `startingCSV: rhods-operator.3.4.0`.
- Stage 010 uses `DSCInitialization`, `DataScienceCluster`, and the 3.x `Auth` resource.
- Stage 030 uses `LLMInferenceService` and the 3.4 model-serving story.
- Stage 040 assumes operator-owned `maas-api` and `maas-controller`.
- Stage 040 no longer reintroduces the previous upstream `maas-controller` deployment or `maas-api` image override.
- Stage 070 and Stage 100+ consume MaaS through generated OpenAI-compatible endpoint configuration.

The repository is not fully cleaned up for the 3.4 MaaS model yet. It still
contains deliberate compatibility resources and historical wording from the
3.3 tier-based MaaS implementation. Those resources must be reviewed and
removed only after live validation confirms the 3.4 subscription-based path
covers the same behavior.

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
- Treat subscriptions, groups, API keys, `MaaSSubscription`, and `MaaSAuthPolicy` as the target RHOAI 3.4 MaaS vocabulary.
- Treat tiers, `tier-to-group-mapping`, tier-named ServiceAccounts, and `alpha.maas.opendatahub.io/tiers` annotations as 3.3 compatibility debt unless a current 3.4 schema check proves they are still required.

## MaaS 3.3 Design Debt Audit

The RHOAI 3.4 upgrade must remove design ambiguity between the old tier-based
MaaS implementation and the 3.4 subscription-based product model. This branch
does not remove functional manifests yet; it records what needs to be cleaned
up and in what order.

| Area | Current repo evidence | Why it exists | 3.4 cleanup target |
|------|-----------------------|---------------|--------------------|
| Tier mapping | `gitops/stages/030-private-model-serving/base/governance/tier-to-group-mapping.yaml` and `alpha.maas.opendatahub.io/tiers` annotations on `LLMInferenceService` manifests | Compatibility with the older webhook and 3.3 tier model | Remove the ConfigMap and tier annotations after `LLMInferenceService` create/update validates without them on the target 3.4 build. |
| Tier-named users and groups | `tier-free-users`, `tier-premium-users`, and `tier-enterprise-users` in Stage 040 | Demo personas were modeled as access tiers | Replace documentation and, after live validation, manifests with subscription consumer groups that map to `MaaSSubscription` access. |
| Manual gateway policy | Manual `RateLimitPolicy`, `TokenRateLimitPolicy`, `TelemetryPolicy`, and AuthPolicy patches | Made 3.3 gateway, token-limit, and telemetry behavior explicit | Prefer product-created policy from `MaaSSubscription` and `MaaSAuthPolicy` when validation proves it covers the demo. Keep only demo-specific patches that are still required. |
| Manual per-model RBAC | `gitops/stages/040-governed-models-as-a-service/base/models/rbac.yaml` grants tier ServiceAccounts model read access | Older MaaS gateway authorization expected tier ServiceAccounts | Remove or replace with product-managed authorization after validating the 3.4 controller-generated access path. |
| Tokens bridge | `gitops/stages/040-governed-models-as-a-service/base/tokens-bridge/deployment.yaml` | Maintains compatibility for Playground and older dashboard token call paths | Keep until product API key and temporary-token flows work through supported dashboard paths without empty-key or header-loss issues. |
| Observability dashboard | Community Grafana dashboard with tier-shaped metrics and compatibility recording rules | Provides visible demo showback before a supported MaaS observability path is adopted | Move to the 3.4 subscription-level MaaS observability dashboard or an OpenShift monitoring path when validated. |
| Historical upstream controller path | Completed backlog entries for upstream `maas-controller`, upstream CRDs, and `maas-api` image override | Previous 3.3 and 3.4 EA2 workaround | Keep only as historical context. Do not present it as current architecture and do not reintroduce it without a newly proven 3.4 product gap. |

## Cleanup Order

1. Update documentation to describe the target 3.4 design as subscription-based MaaS access, not tier-based access.
2. Add or tighten validation that proves the cluster is using operator-owned `maas-api` and `maas-controller` images from `registry.redhat.io/rhoai/`.
3. Validate 3.4 `MaaSSubscription`, `MaaSAuthPolicy`, API key, temporary API key, and dashboard paths against the live sandbox.
4. Remove tier annotations and the `tier-to-group-mapping` ConfigMap only after `LLMInferenceService` apply and MaaS model discovery still pass.
5. Replace tier-named groups, manual RBAC, and manual gateway policies with subscription/group-based resources or product-generated policy after the live path is proven.
6. Replace or retire the tokens bridge only after the dashboard and Playground can mint non-empty keys through supported 3.4 paths.
7. Replace the community Grafana/tier dashboard with the product MaaS observability dashboard or another Red Hat-supported observability path when it is validated for the demo.

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
