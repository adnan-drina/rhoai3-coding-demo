# Fresh-Environment Redeploy Review Notes (working file)

Working notes for the 2026-07 fresh-environment redeploy and RHOAI 3.4
alignment pass. Delete this file when the pass is complete; durable outcomes
move to BACKLOG.md, TROUBLESHOOTING.md, and stage READMEs.

## Status

- [x] Working tree committed (guard, stage 070 Continue VSIX, skills taxonomy)
- [ ] Commits pushed to origin/main (push denied by permission mode — needs user approval; Argo deploys from GitHub main, so this blocks deployment)
- [ ] New cluster credentials in .env (environment provisioning; update OPENSHIFT_API_URL, OPENSHIFT_PASSWORD, RHOAI_EXPECTED_API_SERVER)
- [x] Static validation green: bash -n all scripts, validate-stage-flow.sh

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

## Per-stage deploy log

(filled in as each stage deploys on the fresh cluster)
