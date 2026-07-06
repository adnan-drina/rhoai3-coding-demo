# Extraction Rules

Use these rules to convert official Red Hat documentation into skill knowledge.

## Extract

Capture these facts when present:

- component purpose in one or two sentences
- supported, Technology Preview, Developer Preview, deprecated, or unsupported
  posture
- prerequisites and cluster assumptions
- required operators, namespaces, subscriptions, and dependencies
- CRDs, API groups, kinds, spec fields, status fields, labels, and annotations
- Operator channel, catalog source, CSV, and install mode details
- Red Hat registry images, validated artifacts, storage drivers, or
  product-provided resources
- install, configure, use, upgrade, migrate, backup, restore, and remove
  workflows
- validation commands and expected healthy signals
- common failure modes explicitly described by docs
- boundaries between product feature and custom demo integration

## Product-Family Emphasis

For `ocp-*` skills, prioritize:

- cluster-scoped APIs and operators
- networking, ingress, routes, Gateway API, authentication, RBAC, monitoring,
  logging, nodes, MachineSets, storage classes, and OpenShift GitOps
- security context, SCC, namespace, and cluster-admin implications
- interactions with the live demo environment guard

For `odf-*` skills, prioritize:

- ODF Operator installation and update behavior
- `StorageCluster`, backing storage, storage classes, and Ceph health
- object storage, ObjectBucketClaims, NooBaa/Multi-Cloud Gateway, S3 endpoints
- PVC behavior, RWX/RWO access modes, encryption, backup/restore, and
  capacity planning
- interactions with RHOAI workbenches, pipelines, model storage, registries,
  and object-store connections

For `rhoai-*` skills, use the existing RHOAI component extraction standard and
component roadmap.

## Do Not Extract As Product Truth

Do not promote these into skill instructions without verification:

- upstream Kubernetes, Ceph, NooBaa, KServe, Kubeflow, or community docs fields
  not confirmed by Red Hat docs or installed schema
- examples from old product versions
- guessed default values
- UI behavior observed in screenshots but not documented
- blog snippets that conflict with official product docs
- existing legacy demo code that has not been tied back to official docs

## Skill Mapping

Before mapping extracted content, read
`.agents/references/red-hat-doc-map.yaml` and classify the source by product,
version, category, book, and chapter topic. Use the mapped skill when the route
is `active`, create the planned flat skill when the route is `planned`, and
update the map when a new route is needed.

| Extracted content | Generated skill location |
|-------------------|--------------------------|
| component purpose, when to use | `SKILL.md` intro and description |
| positive and negative triggers | `SKILL.md` frontmatter description |
| source metadata | `references/source-capture.md` |
| detailed product behavior | `references/official-doc-extraction.md` |
| verification and review checklist | `references/validation-checklist.md` |
| small demo snippets | `examples/` |

## Ambiguity Handling

If official docs do not confirm a detail, write:

```markdown
Unresolved: <field or behavior>
Verification: `oc explain <kind>.<field>` or `oc get crd <name> -o yaml`
Do not use in GitOps until verified.
```

Do not silently omit unresolved product-critical items; generated skills must
make uncertainty visible.
