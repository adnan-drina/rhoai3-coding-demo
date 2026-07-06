# Source Capture

## Captured Source

- Product: Red Hat OpenShift AI
- Baseline: use the active version in `docs/PLATFORM_BASELINE.md`
- Source title: Red Hat OpenShift AI: API Tiers
- Captured from: user-provided Red Hat API Tiers excerpt in this repo work
  session
- Retrieved: 2026-06-10

## Related Official Sources

- Red Hat OpenShift AI Self-Managed documentation landing page:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/
- Red Hat OpenShift AI Self-Managed Life Cycle:
  https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle
- Red Hat OpenShift AI: Supported Configurations for 3.x:
  https://access.redhat.com/articles/rhoai-supported-configs-3.x

## Sections Captured

- API deprecation and removal policy statements
- API Tier 1, Tier 2, Tier 4, Beta, and Alpha definitions
- customer-accessible endpoint API version tier table
- KServe `*.serving.kserve.io/v1alpha1` footnote

## Source Boundaries

- API tier describes compatibility and support posture for an API surface.
- API tier is not the same as a component support phase such as GA, Technology
  Preview, Developer Preview, Limited Availability, EUS, or EOL.
- Component-specific skills and official product docs still decide how a field,
  CR, endpoint, image, or workflow should be configured.
- The tier table should be rechecked whenever `docs/PLATFORM_BASELINE.md`
  changes or when Red Hat updates the supported configurations article.
