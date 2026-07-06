# Official Doc Extraction

Use this extraction to keep RHCL update content grounded in the official RHCL
1.4 source. The update page is minimal and dominated by a deprecation notice.

## Update Availability Statement

The official RHCL 1.4 update page states that you can update Red Hat
Connectivity Link from one version to the next if your supported configuration
meets the requirements of the version you want to update to.

## RHCL 1.4.0 Deprecation Warning

The official page carries a Warning-level notice:

> Red Hat Connectivity Link 1.4.0 is deprecated. OpenShift Container Platform
> clusters running Connectivity Link 1.4.0 might experience authentication
> failures, API key management errors, gateway instability, or gateway pod
> memory pressure because of integration changes that are not fully compatible
> on all supported OpenShift Container Platform and OpenShift Service Mesh
> combinations.

## Official Recommended Actions

The official page prescribes two actions based on scenario:

1. **New customers**: Do not install Red Hat Connectivity Link 1.4.0.
2. **Upgrade customers**: Pin Connectivity Link and its dependent Operators to
   the latest Red Hat Connectivity Link 1.3.z release. Prevent upgrades to
   Connectivity Link 1.4.0.

The phrase "pin Connectivity Link and its dependent Operators" indicates that
the hold applies not only to the RHCL operator itself but also to dependent
operators (Authorino, DNS, Limitador) whose versions may be coupled to the
RHCL release train.

## Implications for This Repo

The official deprecation directly validates the demo's compatibility hold:

- The `docs/PLATFORM_BASELINE.md` hold at `rhcl-operator.v1.3.4` aligns with
  the official guidance to pin to the latest 1.3.z release.
- Stage 040 GitOps management of dependent operator Subscriptions with manual
  approval and 1.3.x `startingCSV` values aligns with the official guidance
  to pin dependent Operators.
- The official warning's mention of authentication failures, API key management
  errors, gateway instability, and gateway pod memory pressure are the specific
  failure modes that the Stage 040 regression gates should detect.

## Content Not Available in This Source

The official RHCL 1.4 update page does not provide:

- Step-by-step update procedures or operator lifecycle commands
- Subscription channel, `startingCSV`, or `installPlanApproval` guidance
- Rollback procedures from 1.4.0 to 1.3.z
- Compatibility matrix for OCP versions, Service Mesh versions, or Istio
  versions
- Dependent operator version coordination details
- Timeline or criteria for a supported 1.4.x patch release

These gaps mean that update implementation must rely on:

- RHCL release notes for version-specific compatibility
- RHCL installation guide for operator and Subscription management
- OLM documentation for InstallPlan approval and Subscription pinning
- Live cluster verification with `oc get subscription`, `oc get installplan`,
  and `oc get csv` commands

## Verification Before Any Update Action

Before changing RHCL operator versions, verify:

- Current RHCL operator Subscription, channel, and installed CSV
- Current dependent operator Subscriptions and installed CSVs
- Pending InstallPlans and their target CSVs
- RHCL release notes for the target version
- OCP and Service Mesh version compatibility for the target RHCL version
- Stage 040 MaaS Gateway health: gateway pods, Authorino, auth policies,
  rate limit policies, API key management, and Playground connectivity
