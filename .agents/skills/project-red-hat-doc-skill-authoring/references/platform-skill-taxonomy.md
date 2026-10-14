# Platform Skill Taxonomy

Naming and ownership of Red Hat product skills. Versions, pins and book →
skill routes live in `.agents/references/red-hat-doc-map.yaml`; this file does
not repeat them.

## Product families

| Product | Map key | Prefix | `metadata.skill-group` |
|---|---|---|---|
| Red Hat OpenShift AI Self-Managed | `rhoai` | `rhoai-` | `RHOAI Platform` |
| OpenShift Container Platform | `ocp` | `ocp-` | `OpenShift Platform` |
| OpenShift Dev Spaces | `ocp_devspaces` | `ocp-devspaces-` | `OpenShift Platform` |
| OpenShift Lightspeed | `ocp_lightspeed` | `ocp-lightspeed-` | `OpenShift Platform` |
| OpenShift Pipelines | `ocp_pipelines` | `ocp-pipelines-` | `OpenShift Platform` |
| OpenShift Data Foundation | `odf` | `odf-` | `OpenShift Data Foundation` |
| Connectivity Link | `rhcl` | `rhcl-` | `Connectivity Link` |
| Developer Hub | `rhdh` | `rhdh-` | `Developer Hub` |
| Migration Toolkit for Applications | `mta` | `mta-` | `Application Modernization` |
| Advanced Developer Suite (SSC) | `rhads` | `rhads-` | `Trusted Software Supply Chain` |
| Trusted Profile Analyzer | `tpa` | `tpa-` | `Trusted Software Supply Chain` |

The checker attributes a skill to a family by the longest matching prefix
(`ocp-devspaces-` before `ocp-`), and `metadata.product` must equal that map key.

## Naming

- Stable capability names, never versions: `odf-object-bucket-claims`, not
  `odf-4-22-obc`.
- Flat folders under `.agents/skills/<skill-name>/`; documentation hierarchy
  belongs in the map, not in folders.
- Name by product capability, not by demo stage.

## Frontmatter

```yaml
---
name: <prefix>-<capability>
metadata:
  author: rhoai3-coding-demo
  version: <skill semver>
  product: <map key>
  docs-version: "<map docs_version>"
  skill-group: "<group above>"
description: >
  <Repo-specific positive triggers; negative triggers naming the other skill.>
---
```

The former keys `platform-family`, `platform-baseline: "repo"` and
`ocp-baseline: "repo"` carried no version and are dropped when a skill is
converted.

## New family

1. Add the product to the map with `docs_slug`, `docs_version`, `pin`,
   `deployed`, and routes.
2. Add a row here and to the `AGENTS.md` Shared Skills table.
3. Add a rule file only if the family needs always-on posture or cross-family
   handoffs.
