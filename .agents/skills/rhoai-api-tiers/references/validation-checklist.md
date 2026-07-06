# Validation Checklist

Use this checklist when reviewing RHOAI API usage in manifests, code, docs, or
upgrade notes.

## API Identification

- Every RHOAI custom resource or endpoint has an identified API group/version,
  REST endpoint version, SDK version, or library version.
- The API is mapped to `references/api-tier-map.md` or marked unresolved.
- KServe `*.serving.kserve.io/v1alpha1` entries are checked against the
  documented footnote exceptions.

## Support Posture

- Tier 1 and Tier 2 APIs are preferred for durable GitOps and automation.
- Tier 4 APIs are not presented as stable customer-facing interfaces.
- Beta APIs are labeled Technology Preview where user-visible.
- Alpha APIs are labeled unsupported Developer Preview where user-visible.
- README and presentation language does not imply production support for
  Technology Preview, Developer Preview, Tier 4, or unresolved APIs.

## Manifest Review

- Direct manifests against Tier 4 component APIs have an official-doc reason or
  are replaced with a higher-level supported API.
- `DataScienceCluster` and `DSCInitialization` changes use their Tier 2 APIs
  instead of direct component-owned Tier 4 APIs when possible.
- `ServingRuntime`, `InferenceService`, `LLMInferenceService`, and
  `LLMInferenceServiceConfig` are classified by their explicit Tier 2 entries,
  not by the KServe wildcard.
- `OdhDashboardConfig` use is explicitly labeled Alpha if it is part of
  user-visible configuration.

## Upgrade Review

- Non-Tier 1 API dependencies are called out in upgrade notes.
- The tier table has been rechecked when `docs/PLATFORM_BASELINE.md` changes.
- Any API not found in the map has a verification command or research task.

## Fail Conditions

Stop and correct the work if any of these are true:

- A Tier 4 API is described as stable or customer-supported without evidence.
- A Beta API is presented without Technology Preview labeling.
- An Alpha API is presented as supported.
- A `v1alpha1` API is classified only by its suffix instead of the Red Hat tier
  table.
- A README claims support posture without linking to the active baseline or
  official Red Hat source.
