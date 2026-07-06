# Validation Checklist

Use this checklist before accepting central authentication service GitOps,
documentation, or troubleshooting changes.

## Source And Scope

- The work references the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path, not an
  unversioned latest documentation path.
- OpenShift external OIDC provider setup is not authored from this skill.
- RHOAI user and administrator group policy remains in
  `rhoai-users-groups-access`.
- General certificate bundle behavior remains in `rhoai-certificate-management`.

## GatewayConfig Review

- The live `GatewayConfig` resource name is verified before authoring a patch.
- `GatewayConfig.spec.oidc` fields come from the official chapter or live CRD
  schema verification.
- `oidc.clientSecretRef.name` and `oidc.clientSecretRef.key` point to the
  intended Secret and key.
- The OIDC client Secret is in `openshift-ingress`.
- `providerCASecretName` is present only when the external provider requires a
  custom CA bundle.
- Examples use placeholders for issuer and client values.

## Secret And Token Review

- Real OIDC client secrets are not committed.
- Real service account bearer tokens are not committed.
- Placeholder Secret manifests are clearly dummy examples.
- Active GitOps uses the approved project secret mechanism once it exists.

## Service Account API Access Review

- Service accounts are created only in the namespace that needs API access.
- Token use is documented as credential handling, not source-controlled data.
- API calls use the correct route for the target OpenShift AI service.
- `403` responses are treated as authorization/RBAC issues unless logs show an
  authentication failure.

## Troubleshooting Review

- Dashboard login failures inspect Gateway resources and `kube-auth-proxy`
  logs.
- Dashboard or service API `403` failures verify token identity, group
  membership, and RBAC.
- Token review failures inspect service account token validity and OIDC
  provider configuration.
- Provider TLS failures verify custom CA Secret content and
  `providerCASecretName`.

## Static Checks

Run the repo whitespace check and the focused stale-marker search from
`project-rhoai-doc-chapter-skill-authoring` against this skill directory.
