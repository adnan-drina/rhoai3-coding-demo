# API Tier Review Patterns

## Manifest Review Worksheet

Use this shape when reviewing a new GitOps resource:

```text
Resource: DataScienceCluster/default-dsc
apiVersion: datasciencecluster.opendatahub.io/v1
Tier: Tier 2
Support note: acceptable for durable demo GitOps; review on minor upgrades.
Official source: RHOAI API Tiers table and DataScienceCluster docs.
Decision: keep.
```

```text
Resource: Kserve component CR
apiVersion: kserves.components.platform.opendatahub.io/v1alpha1
Tier: Tier 4
Support note: component-owned/internal API; avoid direct customer dependency.
Official source: RHOAI API Tiers table.
Decision: replace with DataScienceCluster configuration unless official docs
require direct configuration.
```

```text
Resource: LlamaStackDistribution/rag
apiVersion: llamastackdistributions.llamastack.io/v1alpha1
Tier: Beta
Support note: Technology Preview; label README and presentation content.
Official source: RHOAI API Tiers table and Llama Stack docs.
Decision: allowed for demo only with TP labeling.
```

## README Support Note

Use concise support posture text when a step uses non-GA or non-stable APIs:

```text
Support posture: This step uses the LlamaStackDistribution API, which is listed
as Beta in the active Red Hat OpenShift AI API Tiers table. Treat the capability
as Technology Preview and verify migration guidance before upgrading the demo
baseline.
```

## Upgrade Note

Use this shape when preparing for a RHOAI baseline upgrade:

```text
API tier review:
- Recheck Red Hat OpenShift AI API Tiers for the target release.
- List all Tier 2, Tier 4, Beta, Alpha, and unresolved APIs used by active
  GitOps resources.
- Confirm whether fields used in current manifests still exist with:
  oc explain <kind>.<group> --api-version=<group/version> --recursive
```
