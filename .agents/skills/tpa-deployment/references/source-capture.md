# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Red Hat Trusted Profile Analyzer |
| Product version | 2.2 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Deployment Guide |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html-single/deployment_guide/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_trusted_profile_analyzer/2.2/html/deployment_guide/index |
| Documentation category | Get Started |
| Capture date | 2026-07-06 |

## Captured Sections

From Deployment Guide:

- Preface
- Chapter 1: Select your installation platform
  - 1.1 Installing Trusted Profile Analyzer by using Ansible
  - 1.2 Resource recommendations for deploying on OpenShift
  - 1.3 Installing Trusted Profile Analyzer using the Operator Lifecycle Manager
  - 1.4 Installing Trusted Profile Analyzer by using Helm with Amazon Web Services
  - 1.5 Installing Trusted Profile Analyzer by using Helm with Red Hat services
- Appendix A: RHTPA with AWS values file template
- Appendix B: RHTPA with Red Hat services values file template
- Appendix C: RHTPA importer values file template

## Source Boundaries

This skill captures:

- Installation platform selection (RHEL vs OpenShift)
- Ansible-based RHEL deployment prerequisites and procedure
- OLM Operator installation on OpenShift
- Helm chart deployment with AWS infrastructure
- Helm chart deployment with Red Hat services infrastructure
- Resource sizing recommendations
- Required Kubernetes Secrets (storage, OIDC, database credentials)
- Helm values file templates (AWS, Red Hat services, importers)
- Post-installation console URL retrieval

This skill does not capture:

- Managed service quick start (separate guide)
- Release notes and known issues (separate guide)
- Post-deployment administration (separate guide)
- SBOM/VEX document management workflows (separate guide)
- TPA API reference or CLI usage beyond installation
- Detailed OIDC provider setup (Red Hat SSO or Cognito)
- Detailed ODF or S3 bucket provisioning
- PostgreSQL/RDS instance provisioning

## API Versions and CRDs

| Kind | API Group | Notes |
|------|-----------|-------|
| `TrustedProfileAnalyzer` | Provided by RHTPA Operator (OLM) | CR for operator-managed deployment |
| `Secret` | `v1` | Storage, OIDC, and database credentials |

Unresolved: The exact `apiVersion` and `apiGroup` for `TrustedProfileAnalyzer`
CR are not specified in the deployment guide text. Verify on a cluster with the
Operator installed:

```shell
oc api-resources | grep -i trustify
oc get crd | grep -i trust
```

## Related Official Sources To Add Later

- Red Hat Trusted Profile Analyzer 2.2 Quick start guide
- Red Hat Trusted Profile Analyzer 2.2 Release notes
- Red Hat Trusted Profile Analyzer 2.2 Administration guide
