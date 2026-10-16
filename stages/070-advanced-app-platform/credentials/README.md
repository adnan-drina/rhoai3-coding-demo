# Credential rotation

Explicit operator rotation of the Stage 070 integration credentials, never part of a routine sync. Run one component
at a time against the exact deployed, published revision, with a new report path each time:

```bash
stages/070-advanced-app-platform/credentials/rotate.sh COMPONENT --revision <deployed commit> \
  --report <new file outside Git> --execute
```

It refuses unless the checkout's Stage 070 source equals that published revision and every Stage 070 Application is
reconciled at it, `--execute` is given and the report file does not exist. `--repo-url` defaults to `GIT_REPO_URL`.
The report (mode 600) holds the verification results only, never a credential. A partial result needs diagnosis
before any rerun; preserve earlier reports. The follow-up restarts and checks are in `docs/OPERATIONS.md` (Stage 070
security review follow-up).

| Component | When to run | What changes |
|---|---|---|
| `gitlab_oidc` | GitLab's platform-realm OIDC client secret must change | Keycloak client `gitlab` secret, Secret `gitlab-system/gitlab-oidc`; restarts the GitLab webservice |
| `scm_client` | The SCM provisioner client secret must change | Keycloak client `stage070-scm-provisioner`, Secret `gitlab-system/stage070-scm-provisioner` |
| `publisher` | The Developer Hub publisher token must change | New `rhdh-publisher` token (same scopes and expiry) in `rhdh/gitlab-publisher` and `rhdh/rhdh-gitlab`; old token revoked |
| `devspaces_oauth` | The Dev Spaces GitLab OAuth secret must change | GitLab application secret renewed; Secret `openshift-devspaces/gitlab-oauth-config` |
| `sonar` | The SonarQube control token must change | New `platform-provisioner` token in `app-platform-build/sonarqube-credentials`; previous token revoked |
| `sonar_projects` | A project analysis token is still owned by the SonarQube administrator | Re-minted under `platform-provisioner`; project Secret and workspace mirrors updated; administrator copy revoked |
| `delivery_writers` | Before a project's `gitlab-delivery-writer` reaches its 90-day expiry | GitLab self-rotation of each project access token (new 90-day expiry) |
| `argo` | Developer Hub's Argo CD reader token must change | Deletes `openshift-gitops/rhdh-local-user` so the GitOps operator issues a new token; copies it to `rhdh/rhdh-secrets` |
| `mta` | The MTA MaaS API key must change | New key for `mta-maas-provisioner` (subscription `mta-migration-ai`) in `openshift-mta/kai-api-keys`; old key revoked; no inference |
| `annotation_copy --secret NS/NAME` | A Secret still carries a `last-applied-configuration` copy | Removes that annotation only; checks UID, data and type unchanged; rotates nothing |

The GitLab root API steps (`publisher`, `devspaces_oauth`) mint a one-day root token in the Ready GitLab toolbox and
revoke it on exit.
