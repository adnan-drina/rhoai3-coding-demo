# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Lightspeed |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation version | 1.0 |
| Documentation category | About |
| Official guide | About OpenShift Lightspeed |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/about/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/about/index |
| Capture date | 2026-07-06 |

## Captured Sections

From About OpenShift Lightspeed:

- Chapter 1: About OpenShift Lightspeed
  - 1.1 OpenShift Lightspeed overview (supported interfaces, product coverage, product exceptions)
  - 1.2 OpenShift requirements (cluster resource requirements, telemetry behavior)
  - 1.3 Large language model (LLM) requirements (SaaS providers: OpenAI, Azure OpenAI, IBM watsonx; self-hosted: RHOAI, RHEL AI; vLLM 0.8.4+)
  - 1.4 FIPS support (x86_64, ppc64le, s390X)
  - 1.5 Supported architecture (x86_64)
  - 1.6 Disconnected mode (image mirroring with oc mirror)
  - 1.7 About data use (cluster data added to messages, privacy limitations)
  - 1.8 About data, telemetry, transcript, and feedback collection (redaction layer)
  - 1.9 Remote health monitoring overview (transcript collection, feedback collection, disabling data collection via OLSConfig CR)
  - 1.10 Additional resources

## Source Boundaries

This skill covers the "About OpenShift Lightspeed" guide only. It provides
conceptual understanding of the product, supported LLM providers, resource
requirements, data handling, and telemetry. It does not cover:

- Installation and operator setup (separate guide)
- OLSConfig CR configuration beyond data collection fields (separate guide)
- Day-2 operations and administration (separate guide)
- Troubleshooting (separate guide)
- Integration patterns with specific LLM providers beyond prerequisites

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| OLSConfig | `ols.openshift.io/v1alpha1` |

## Related Official Sources To Add Later

- Installing OpenShift Lightspeed
- Configuring OpenShift Lightspeed
- Operating OpenShift Lightspeed
- Troubleshooting OpenShift Lightspeed
