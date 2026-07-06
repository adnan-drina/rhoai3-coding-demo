# Official Doc Extraction

Use this extraction to keep RHCL update content grounded in official sources.
Verify exact operator versions with `oc get csv` before changing Subscriptions.

## RHCL 1.4.0 Deprecation (from 1.4 release notes)

RHCL 1.4.0 (RHBA-2026:25234) is deprecated. Clusters running 1.4.0 may
experience:

- Authentication failures
- API key management errors
- Gateway instability
- Gateway pod memory pressure

These issues stem from integration incompatibilities across certain OCP and
Service Mesh version combinations.

Official remediation:

- **New customers:** Do not install RHCL 1.4.0.
- **Upgrade customers:** Pin Connectivity Link and its dependent operators to
  the latest RHCL 1.3.z release. Prevent upgrades to 1.4.0.

## Demo Pin Strategy

This demo pins `rhcl-operator.v1.3.4` in the Subscription CR:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: connectivity-link-operator
  namespace: <operator_ns>
spec:
  channel: stable
  installPlanApproval: Manual
  name: connectivity-link-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
  startingCSV: rhcl-operator.v1.3.4
```

Before approving any InstallPlan:

```bash
oc get installplan -n <operator_ns> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.clusterServiceVersionNames[*]}{"\n"}{end}'
```

Reject any InstallPlan that resolves to a 1.4.x CSV.

## Supported Configurations (RHCL 1.3)

### OCP Version Matrix

| RHCL | OCP | OSD | ROSA | ARO |
|------|-----|-----|------|-----|
| 1.3 | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.21, 4.20, 4.19 | 4.19 |
| 1.2 | 4.20, 4.19, 4.18 | 4.20, 4.19, 4.18 | 4.20, 4.19, 4.18 | 4.17 |
| 1.1 | 4.19, 4.18, 4.17 | 4.19, 4.18, 4.17 | 4.19, 4.18, 4.17 | 4.17 |

### Dependent Operator Matrix

| RHCL | Service Mesh | cert-manager Operator |
|------|-------------|----------------------|
| 1.3 | 3.2 | 1.18 |
| 1.2 | 3.1 | 1.17 |
| 1.1 | 3.0 | 1.15 |

### Supported Cloud Providers

AWS, GCP, Azure (all RHCL versions).

### Supported Cloud DNS Providers

Amazon Route 53, GCP DNS, Azure DNS (all RHCL versions).

### Supported On-Premise DNS

CoreDNS for on-cluster DNS zones (all RHCL versions).

### Supported Rate Limiting Data Stores

Redis Enterprise or Cloud, Amazon ElastiCache, Dragonfly Community or Cloud
(latest versions, all RHCL versions).

### Supported Identity Access Management

| RHCL | Red Hat build of Keycloak |
|------|--------------------------|
| 1.3 | 26.4 |
| 1.2 | 26.4 |
| 1.1 | 26.2 |

## Gateway API CRD Constraint

On OCP 4.19 or later, if updating from a previous OCP version that contains
Gateway API CRDs, the CRD resources must exactly match the Gateway API version
supported by the target OCP version. See the OpenShift documentation on managing
Gateway API resources.

On OCP 4.18 or older, Red Hat OpenShift Service Mesh must be used as the
Gateway API provider.

## Update Procedure (1.2.x to 1.3 via Web Console)

Prerequisites:

- RHCL 1.2.x installed on OCP 4.19 or later.

Procedure:

1. Navigate to **Ecosystem > Installed Operators > Red Hat Connectivity Link**.
2. Ensure the **Update channel** is set to `stable`.
3. If **Update approval** is `Automatic`, the update installs when the channel
   resolves the new version.
4. If **Update approval** is `Manual`, click **Install** to approve.
5. Wait for the Connectivity Link Operator deployment to complete.
6. Verify RHCL 1.3 is installed and running.

## Lifecycle Notes

Starting with RHCL 1.4, full support ends with the release of the next minor
version. Maintenance support ends with the minor version after that.

The maintenance support lifecycle for RHCL 1.3 was shortened: it now ends with
the release of RHCL 1.5 (previously announced as ending with 1.6).

## Verification Commands

```bash
oc get csv -n <operator_ns> | grep connectivity

oc get sub connectivity-link-operator -n <operator_ns> \
  -o jsonpath='{.status.installedCSV}'

oc get installplan -n <operator_ns>

oc get pods -n <operator_ns> -l app=connectivity-link-operator
```

Healthy state:

- CSV phase is `Succeeded` with a 1.3.z version.
- `installedCSV` matches the pinned `startingCSV`.
- No pending InstallPlans resolve to 1.4.x.
- Operator pod is Running and Ready.
