# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Chapter 10. Configuring a central authentication service for an external OIDC identity provider |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/configuring-external-oidc-provider_managing-rhoai |
| Documentation category | Administer |
| Retrieved date | 2026-06-10 |
| Sections used | 10.1 About the central authentication service; 10.2 Configuring OpenShift AI to use an external OIDC provider; 10.3 Accessing OpenShift AI APIs by using a service account token; 10.4 Using a custom certificate authority bundle; 10.5 Troubleshooting central authentication service problems |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active product baseline and documentation category index |
| OpenShift documentation linked from the official chapter | Supplemental source for direct OIDC and OAuth identity-provider configuration |
| OpenShift Gateway API documentation linked from the official chapter | Supplemental source for Gateway API support behavior |

## Source Boundaries

- Product configuration truth: official Red Hat OpenShift AI 3.4 chapter above.
- OpenShift identity-provider configuration truth: official OpenShift
  documentation for the active cluster version.
- Demo policy: no real OIDC client secrets, service account bearer tokens, or
  provider credentials are committed to this repository.
- Verification: readonly `oc get`, `oc describe`, `oc logs`, and schema checks
  listed in this skill.
- Not authoritative: upstream Gateway API, OIDC provider, or identity-provider
  vendor documentation unless explicitly labeled as supplemental.

## Unresolved Or Environment-Specific Items

- Exact `GatewayConfig` resource name in the active cluster.
  Verification: `oc get gatewayconfigs`.
- Final GitOps secret mechanism for OIDC client secrets.
  Verification: align with the project secret pattern when active GitOps is
  rebuilt.
- External OIDC provider details: issuer URL, client ID, client secret, realm
  name when the provider requires one, and redirect URI registration.
  Verification: obtain from the approved provider configuration for the active
  environment.
