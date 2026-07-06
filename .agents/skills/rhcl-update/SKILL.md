---
name: rhcl-update
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when updating or upgrading Red Hat Connectivity Link to a newer version,
  including operator updates, migration steps, and compatibility considerations.
  Do NOT use for installing (use rhcl-install), configuring (use
  rhcl-configure), or troubleshooting (use rhcl-troubleshoot).
---

# RHCL Update

Use this skill to ground Red Hat Connectivity Link update and upgrade guidance
in the official RHCL 1.4 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## RHCL 1.4.0 Deprecation Notice

The official RHCL 1.4 update page carries a critical deprecation warning:

> Red Hat Connectivity Link 1.4.0 is deprecated. OpenShift Container Platform
> clusters running Connectivity Link 1.4.0 might experience authentication
> failures, API key management errors, gateway instability, or gateway pod
> memory pressure because of integration changes that are not fully compatible
> on all supported OpenShift Container Platform and OpenShift Service Mesh
> combinations.

Red Hat advises:

- **New customers**: Do not install Red Hat Connectivity Link 1.4.0.
- **Upgrade customers**: Pin Connectivity Link and its dependent Operators to
  the latest Red Hat Connectivity Link 1.3.z release. Prevent upgrades to
  Connectivity Link 1.4.0.

## Demo Update Posture

For this RHOAI demo:

- The platform baseline holds RHCL at `rhcl-operator.v1.3.4` per
  `docs/PLATFORM_BASELINE.md`.
- Stage 040 GitOps-manages the RHCL dependency Subscriptions for Authorino,
  DNS, and Limitador with manual approval and 1.3.x `startingCSV` values.
- Do not approve RHCL 1.4.x InstallPlans until Red Hat publishes a supported
  replacement path and the Stage 040 MaaS Gateway, dashboard, API-key,
  local-model, external-model, and Playground regression gates pass.

## Known Risks from RHCL 1.4.0

The official update page documents these risks for clusters running 1.4.0:

- Authentication failures
- API key management errors
- Gateway instability
- Gateway pod memory pressure

These originate from integration changes not fully compatible across all
supported OCP and OpenShift Service Mesh combinations.

## Update Prerequisites

Before considering any RHCL version change:

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Verify current Subscription state and installed CSV version.
3. Verify dependent operator Subscriptions (Authorino, DNS, Limitador).
4. Review the RHCL release notes for the target version.
5. If the target is 1.4.x, stop: the version is deprecated per official docs.

## Workflow

1. Read `references/source-capture.md` and confirm the baseline version.
2. Read `references/official-doc-extraction.md` for extracted product behavior.
3. Identify whether the task concerns:
   - Evaluating an RHCL version upgrade path
   - Pinning or holding RHCL operator Subscriptions
   - Managing RHCL dependency operator versions
   - Recovering from an unintended upgrade to 1.4.0
4. For Subscription management, verify all InstallPlan approval policies,
   `startingCSV` values, and dependent operator channel configurations.
5. For live operations, use the repo environment guard and pair this skill
   with `rhoai-troubleshoot` or `validate-demo-step`.

## Verification Commands

```bash
# Check RHCL operator Subscription and installed CSV
oc get subscription -n redhat-connectivity-link-operator \
  -o custom-columns='NAME:.metadata.name,CSV:.status.installedCSV,APPROVAL:.spec.installPlanApproval'

# Check for pending InstallPlans
oc get installplan -n redhat-connectivity-link-operator \
  -o custom-columns='NAME:.metadata.name,CSV:.spec.clusterServiceVersionNames[*],APPROVED:.spec.approved'

# Check dependent operator Subscriptions
oc get subscription -n redhat-connectivity-link-operator \
  -o custom-columns='NAME:.metadata.name,CHANNEL:.spec.channel,CSV:.spec.startingCSV,APPROVAL:.spec.installPlanApproval'
```

## Related Skills

- Use `rhcl-install` for initial Connectivity Link installation.
- Use `rhcl-configure` for deploying and configuring Connectivity Link
  components.
- Use `rhcl-troubleshoot` for diagnosing Connectivity Link issues.
- Use `rhoai-maas-governance` for MaaS Gateway configuration that depends on
  the RHCL stack.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
