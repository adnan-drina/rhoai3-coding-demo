# Platform Skill Taxonomy

Use this taxonomy when creating official-doc-backed Red Hat product skills.

Use `.agents/references/red-hat-doc-map.yaml` as the routing layer between Red
Hat product documentation hierarchy and flat repo skills. The taxonomy below
defines naming and ownership; the doc map defines which product, category,
book, and chapter topic routes to which existing or planned skill.

## Product Families

| Product family | Prefix | Skill group | Metadata `platform-family` | Rule file |
|----------------|--------|-------------|-----------------------------|-----------|
| Red Hat OpenShift AI Self-Managed | `rhoai-*` | `RHOAI Platform` | `rhoai` | `.agents/rules/rhoai.md` |
| Red Hat OpenShift Container Platform | `ocp-*` | `OpenShift Platform` | `ocp` | `.agents/rules/ocp.md` |
| Red Hat OpenShift Data Foundation | `odf-*` | `OpenShift Data Foundation` | `odf` | `.agents/rules/odf.md` |

Do not create empty OCP or ODF component skills. Create the first `ocp-*` or
`odf-*` skill only when an official Red Hat source is provided and the product
baseline is pinned in `docs/PLATFORM_BASELINE.md`.

## Skill Naming

Use stable capability names:

- `ocp-etcd`
- `ocp-ai-workloads`
- `ocp-cicd-builds`
- `ocp-distributed-tracing`
- `ocp-gitops-operator`
- `ocp-machine-configuration`
- `ocp-machine-management`
- `ocp-node-feature-discovery`
- `ocp-nodes`
- `ocp-observability`
- `ocp-opentelemetry`
- `ocp-storage`
- `ocp-web-console`
- `ocp-gateway-api`
- `ocp-authentication-identity-providers`
- `odf-storagecluster`
- `odf-storage-classes`
- `odf-object-bucket-claims`
- `odf-multicloud-gateway`

Prefer names based on product capability rather than one demo stage. Avoid
version numbers in skill names.

Keep skill folders flat under `.agents/skills/<skill-name>/`. Do not create
category or product subdirectories to mirror Red Hat documentation structure;
represent that hierarchy in `.agents/references/red-hat-doc-map.yaml`.

## Frontmatter Template

```yaml
---
name: <prefix>-<capability>
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "<rhoai|ocp|odf>"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "<RHOAI Platform|OpenShift Platform|OpenShift Data Foundation>"
description: >
  <Strong trigger description tied to official Red Hat docs. Include positive
  and negative triggers.>
---
```

For ODF skills, keep `ocp-baseline: "repo"` because ODF runs on the active
OpenShift baseline and the OCP version affects API availability, operators,
storage classes, and cluster behavior.

## Inventory Updates

When adding the first skill in a new product family:

- add the family row to `AGENTS.md` if it is not already present
- add the family row to `.agents/skills/project-structure/SKILL.md`
- add the family row to `.agents/skills/project-agent-guidance/SKILL.md`
- create `.agents/rules/ocp.md` or `.agents/rules/odf.md` as a thin pointer
  to the new skills
- create or update a roadmap in
  `.agents/skills/project-structure/references/`

When adding later skills in an existing family:

- update `.agents/references/red-hat-doc-map.yaml`
- update the family rule file
- update the relevant roadmap
- update inventory counts in `project-agent-guidance`
- update `AGENTS.md` and `project-structure` if those files list explicit
  skill names
