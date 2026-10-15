# Platform Baseline

This file states where the demo's product targets live and how they change. It does not list versions.

## Product versions

Each product has one documentation version, tied to the Git pin that selects it (Subscription channel,
`startingCSV`, or the operator policy minimum). Both live in
[`.agents/references/red-hat-doc-map.yaml`](../.agents/references/red-hat-doc-map.yaml). Print them with:

```bash
python3 scripts/shared/check-doc-links.py --versions
```

`scripts/shared/check-doc-links.py` fails when a pin and the map disagree, and when a converted skill or a
component README links to another documentation version. Upgrade a product by changing its pin, its
`docs_version` and its skills in one change, then run the checker. Products with no Git pin (for example
OpenShift itself, which is installed outside Git) carry the reason in the map.

The live cluster inventory and the fresh-environment contract are in
[OPERATIONS](OPERATIONS.md#fresh-environment-baseline-2026-10-05).

## Version match rule

Use the official Red Hat documentation version that the map gives for the product, never `latest` or another
version. The exception is a product Red Hat publishes only unversioned (the map records it, for example
`1-latest`). Record any other exception in the skill or document that needs it.

## Lifecycle policy

- Operators follow the Subscription channel and approval set in Git. The operator policy check
  (`scripts/platform/check-operator-policy.py`) holds the minimum installed versions.
- ODF follows the OpenShift minor version (`stable-4.22` on OpenShift 4.22), as the ODF update guidance requires.
- The baseline pins product documentation and operator lifecycle policy only. It does not pin generated operand
  images, copied CSV content or operator-created Deployments. If an operand is incompatible with the installed
  operator or CRD, change the Subscription policy or a documented CR field, not the generated fields.

## ODF demo storage intent

The demo starts with the minimum ODF footprint needed by RHOAI:

- Standalone Multicloud Object Gateway (MCG/NooBaa) for S3-compatible object storage used by model artifacts,
  AI Pipelines, MLflow, evaluation evidence and other RHOAI object-store integrations.
- `ObjectBucketClaim` resources for project-scoped buckets and their generated ConfigMaps and Secrets.
- A full ODF StorageCluster (Ceph block and file) only as an explicit decision, when the demo needs ODF RWO/RWX
  PVCs beyond the cluster's own storage classes.

## Source hierarchy

1. Official Red Hat product documentation at the map's version.
2. Official Red Hat articles, blogs and product messaging, for narrative and examples.
3. `/Users/adrina/Sandbox/rh-brain/Red Hat Brain`, read-only research input.
4. The repo's implementation, scripts and READMEs.
5. Live schema checks such as `oc explain` and `oc get crd`.

Official documentation is the source of truth for supported configuration. Do not invent CR fields, API
versions, annotations or operator settings.

## Skill metadata policy

Product skills carry `metadata.product` and `metadata.docs-version` matching the map, and link to versioned
official sections instead of copying them. Author them with `project-red-hat-doc-skill-authoring`.
