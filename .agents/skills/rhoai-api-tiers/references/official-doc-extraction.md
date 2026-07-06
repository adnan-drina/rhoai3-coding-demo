# Official Documentation Extraction

## API Deprecation Model

For Red Hat OpenShift AI, APIs are stable within a major release for at least
nine months from the announcement of deprecation. APIs can still be deprecated
and removed within a major release, and Red Hat can provide a longer
deprecation window than the minimum.

Use this model for upgrade planning:

- do not assume every API survives for a full major release
- check release notes, supported configurations, and component docs before
  upgrading across minor versions
- record customer-facing dependencies on non-Tier 1 APIs in README or
  operations notes

## Tier Meanings

| Tier | Meaning | Demo handling |
|------|---------|---------------|
| Tier 1 | Stable within a major release for at least 18 months | Preferred for durable GitOps, docs, and automation |
| Tier 2 | Stable within a major release for at least 9 months | Acceptable, but review on minor upgrades |
| Tier 4 | No compatibility; can change at any point; not intended outside OpenShift AI components | Avoid direct customer dependence unless official docs require it |
| Beta | Technology Preview APIs; Red Hat provides at least a manual migration path for breaking changes | Label as Technology Preview and keep isolated |
| Alpha | Unsupported Developer Preview APIs; no backward compatibility guarantees | Avoid for core flows unless explicitly accepted |

## Review Principles

- API tier is a support and compatibility classification, not a schema.
- A version suffix such as `v1alpha1` is not enough to classify posture. Use the
  Red Hat tier table.
- Treat Tier 4 component APIs as internal by default. A direct manifest against
  a Tier 4 API needs official documentation and a clear reason.
- If a component skill says a capability is Technology Preview, the README or
  runbook must say so even if the CRD is present on the cluster.
- If an API is not in the tier map, mark it unresolved and verify through
  current Red Hat docs, release notes, CRD metadata, or Red Hat Support.

## KServe v1alpha1 Footnote

The captured source says all APIs in `*.serving.kserve.io/v1alpha1` are Alpha
except:

- `inferenceservice`
- `llminferenceserviceconfigs`
- `llminferenceservices`
- `servingruntime`

Those exceptions are listed separately in the API tier map and must not be
classified from the wildcard alone.

## Argo API Note

The table classifies `*.argoproj.io/v1alpha1` as Tier 4 in the RHOAI API tier
context. This does not by itself define support for a separately installed
OpenShift GitOps or Argo CD product. For this demo, continue to manage Argo CD
Applications through the project GitOps policy, but do not present RHOAI's
embedded or component-owned Argo APIs as stable RHOAI customer APIs.
