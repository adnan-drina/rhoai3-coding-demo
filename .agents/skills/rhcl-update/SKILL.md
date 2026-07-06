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
  Use when updating Red Hat Connectivity Link within the 1.3.x line or
  understanding upgrade constraints. Covers supported configurations, OCP
  version compatibility, dependent operator versions, and the web console
  update procedure. Note: RHCL 1.4.0 is deprecated per official 1.4 release
  notes; the demo stays pinned at rhcl-operator.v1.3.4. Do NOT upgrade to 1.4.
---

# RHCL Update

Use this skill to ground Connectivity Link update decisions in official RHCL 1.3
documentation for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## RHCL 1.4.0 Deprecation Warning

RHCL 1.4.0 is deprecated. Per the official 1.4 release notes
(RHBA-2026:25234), clusters running 1.4.0 may experience authentication
failures, API key management errors, gateway instability, or gateway pod memory
pressure due to integration incompatibilities across OCP and Service Mesh
combinations.

Official guidance:

- **New installations:** Do NOT install RHCL 1.4.0.
- **Existing 1.3.x installations:** Pin the Connectivity Link and its dependent
  operators to the latest 1.3.z release. Prevent upgrades to 1.4.0.

This demo pins `rhcl-operator.v1.3.4`. Do NOT change the Subscription to allow
automatic upgrade to 1.4.

## Demo Posture

For this demo:

- The Subscription `startingCSV` is pinned to `rhcl-operator.v1.3.4`.
- Update approval should be `Manual` to prevent unintended minor-version jumps.
- The `stable` channel delivers 1.3.z patch updates; verify the channel does
  not auto-resolve to 1.4 before approving an InstallPlan.
- Before approving any InstallPlan, confirm the CSV version with
  `oc get installplan -n <ns>` and reject plans that resolve to 1.4.x.

## Supported Configurations (RHCL 1.3)

### OCP Versions

| RHCL | OCP | OSD | ROSA | ARO |
|------|-----|-----|------|-----|
| 1.3  | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.19 |

### Dependent Operators

| RHCL | Service Mesh | cert-manager Operator |
|------|-------------|----------------------|
| 1.3  | 3.2         | 1.18                 |

### Gateway API CRD Constraint

On OCP 4.19+, if updating from a previous OCP version that contains Gateway API
CRDs, ensure those resources exactly match the Gateway API version supported by
your OCP version before updating RHCL.

## Lifecycle

With the release of RHCL 1.4, maintenance support for 1.3 was shortened:
maintenance support for 1.3 ends with the release of RHCL 1.5 (previously
announced as ending with 1.6). See the Red Hat Connectivity Link Life Cycle
Policy for current support dates.

## Update Procedure (1.2.x to 1.3)

Prerequisites:

- RHCL 1.2.x installed on OCP 4.19 or later.
- OCP version compatible with RHCL 1.3 (see table above).

Steps (web console):

1. Navigate to **Ecosystem > Installed Operators > Red Hat Connectivity Link**.
2. Ensure the **Update channel** is set to `stable`.
3. If **Update approval** is `Automatic`, the update installs immediately.
4. If **Update approval** is `Manual`, click **Install**.
5. Wait for the Connectivity Link Operator deployment to complete.
6. Verify RHCL 1.3 is installed and running.

## Validation Signals

```bash
oc get csv -n <ns> | grep connectivity
oc get sub -n <ns> -o yaml | grep -E 'currentCSV|installedCSV|startingCSV'
oc get installplan -n <ns>
```

Healthy state: CSV phase is `Succeeded`, installedCSV matches the expected
1.3.z version, and no pending InstallPlans resolve to 1.4.x.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - a 1.3.z patch update within the pinned line
   - verifying supported configuration (OCP, Service Mesh, cert-manager)
   - blocking an unintended upgrade to 1.4
   - understanding the lifecycle and support window for 1.3
4. For Subscription or InstallPlan changes, verify the target CSV version.
5. Validate with the commands above.

## Related Skills

- `rhcl-install` for Connectivity Link core operator installation.
- `rhcl-configure` for gateway policy deployment.
- `rhcl-mcp-config` for MCP server registration (RHCL 1.4 Tech Preview).
- `rhcl-troubleshoot` for diagnostics and recovery.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
