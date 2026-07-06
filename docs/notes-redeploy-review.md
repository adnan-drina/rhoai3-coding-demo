# Fresh-Environment Redeploy Review Notes (working file)

Working notes for the 2026-07 fresh-environment redeploy and RHOAI 3.4
alignment pass. Delete this file when the pass is complete; durable outcomes
move to BACKLOG.md, TROUBLESHOOTING.md, and stage READMEs.

## Status

- [x] Working tree committed (guard, stage 070 Continue VSIX, skills taxonomy)
- [x] Commits pushed to origin/main (through ae43e99, script refactor included)
- [ ] New cluster credentials in .env (environment provisioning; update OPENSHIFT_API_URL, OPENSHIFT_PASSWORD, RHOAI_EXPECTED_API_SERVER)
- [x] Static validation green: bash -n all scripts, validate-stage-flow.sh

## Script refactor completed pre-deploy (commits 5e27296, ae43e99)

- validate-lib.sh: load_env before guard (fixes exit-43 on every stage
  validate), Ready-condition pod counting, unified check_argocd_app
  semantics (sync drift WARN, Progressing WARN, else FAIL), new
  check_secret_value and check_http_code helpers
- validate-demo-flow.sh: mapfile removed (bash 3.2 on macOS)
- bootstrap.sh: bounded wait_until, ArgoCD patches fail loudly
- deploy scripts: shared apply_stage_app; audit-maas-cleanup.sh now guarded
- First live bootstrap+validate run on the fresh cluster must confirm all
  of this end-to-end.

## Stage 010 static findings (pre-deploy)

1. **Serverless/Knative likely unnecessary (RHOAI 3.4).** KServe Serverless
   mode was deprecated in 2.25 and retired in 3.0; only standard (raw)
   deployment remains. Stage 010 still installs the Serverless operator and
   KnativeServing (`base/serverless/`), with a comment claiming Knative is
   needed even in RawDeployment mode — that claim matches 2.x, not 3.4.
   Nothing else in the repo references knative. Plan: deploy the fresh
   cluster without serverless and validate KServe + MaaS end-to-end; if
   green, remove `base/serverless/`, the kustomization entries, and the
   KnativeServing checks in stage 010 validate.sh (lines 33-37).
2. **OAuth IdP list is replaced, not merged.** `users/oauth.yaml` sets
   `spec.identityProviders` to only `demo-htpasswd`, but the comment says
   "alongside existing providers". The list is atomic — syncing wipes any
   IdP the sandbox ships with. Check `oc get oauth cluster -o yaml` on the
   fresh cluster before first sync; if RHDP provisions its own IdP, merge it
   into the manifest or drop the claim from the comment.
3. **bootstrap.sh robustness (minor).** Untimed `until` loops after operator
   subscription; ArgoCD patches fall through to `log_warn` on failure (a
   failed health-check patch would surface later as sync-wave hangs).
   Candidate: bounded retries that fail loudly.
4. **GitOps operator channel pin `gitops-1.15`** — verify this is still the
   supported channel for OCP on the fresh cluster
   (`oc get packagemanifest openshift-gitops-operator -o jsonpath='{.status.channels[*].name}'`).

## Verified reference points

- RHOAI 3.0 release notes: Serverless/ModelMesh retired; migrate to
  RawDeployment before upgrading to 3.x.
- Stage 010 already uses 3.x-native APIs: DataScienceCluster v2, DSCI v2,
  services.platform.opendatahub.io/v1alpha1 Auth, MaaS dashboard flags.

## Image pin policy (user directive 2026-07-06)

Only pin images where product documentation recommends pinning; otherwise
let the RHOAI/product operators manage image versions and lifecycle.

Audit result:
- stage 030 `models/*.yaml` pin `rhaii/vllm-cuda-rhel9@sha256:...` — remove
  at stage 030 deploy and confirm the RHOAI KServe controller injects the
  supported runtime image.
- `ose-cli`, `postgresql-16:latest`, MCP date tags, Dev Spaces
  `cli-ai-tools` digest: demo-owned utility/tooling images, not
  operator-managed; keep as-is (cli-ai-tools digest is deliberate for the
  Java 21 toolchain).

## Per-stage deploy log

### Fresh environment (2026-07-06)

- Cluster: cluster-j98ml.j98ml.sandbox1570.opentlc.com, OCP 4.20.26
- Pre-flight: OAuth spec empty (no IdP-replacement risk on this cluster);
  gitops-1.19 pinned (1.15 was 6 releases behind); rhods stable-3.4
  resolves 3.4.2, startingCSV pin dropped
- bootstrap.sh: clean first run after refactor
- Stage 010: deployed without serverless (validation of the 3.x removal)

(filled in as each stage deploys on the fresh cluster)
