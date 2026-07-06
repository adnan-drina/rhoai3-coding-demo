# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Lightspeed |
| Product version | 1.0 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html-single/install/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_lightspeed/1.0/html/install/index |
| Documentation category | Installing |
| Official guide | Install |
| Capture date | 2026-07-06 |

## Captured Sections

From Install:

- Chapter 1: Installing OpenShift Lightspeed
  - 1.1 Large language model (LLM) overview
    - 1.1.1 Red Hat Enterprise Linux AI with OpenShift Lightspeed
    - 1.1.2 Red Hat OpenShift AI with OpenShift Lightspeed
    - 1.1.3 IBM watsonx with OpenShift Lightspeed
    - 1.1.4 OpenAI with OpenShift Lightspeed
    - 1.1.5 Microsoft Azure OpenAI with OpenShift Lightspeed
  - 1.2 About subscription requirements
  - 1.3 About adding Operators to a cluster
    - 1.3.1 Installing the OpenShift Lightspeed Operator from the OperatorHub
    - 1.3.2 Installing the OpenShift Lightspeed Operator from the software catalog

## Source Boundaries

This skill captures the Operator installation procedure from the official
Install guide for Red Hat OpenShift Lightspeed 1.0.

It covers:

- LLM provider overview and requirements for each supported provider
- Subscription and account requirements
- Operator installation via OperatorHub (OCP 4.16-4.19)
- Operator installation via software catalog (OCP 4.20+)

It does not cover:

- OLSConfig CR creation and customization (expected in Configuring guide)
- LLM provider credential Secret creation (expected in Configuring guide)
- Service configuration and tuning (expected in Configuring guide)
- Uninstallation procedures (expected in a separate guide or Configuring guide)
- OpenShift Lightspeed concepts and architecture (expected in About guide)
- Day-2 operations and monitoring (expected in Operations guide)
- Troubleshooting and diagnostics (expected in Troubleshooting guide)

## API Versions Documented

No CRDs or CR API versions are defined in the Install guide. The OLSConfig CR
API version is expected in the Configuring guide.

## Related Official Sources To Add Later

- Red Hat OpenShift Lightspeed 1.0 About documentation
- Red Hat OpenShift Lightspeed 1.0 Configuring documentation (OLSConfig CR,
  LLM secrets, service tuning)
- Red Hat OpenShift Lightspeed 1.0 Operations documentation
- Red Hat OpenShift Lightspeed 1.0 Troubleshooting documentation
- Red Hat OpenShift Lightspeed 1.0 Upgrade documentation
