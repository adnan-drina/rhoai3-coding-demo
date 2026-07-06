# Validation Checklist

Use this checklist when reviewing RHOAI update-channel policy or Subscription
GitOps.

## Channel Choice

- Desired support posture is documented: feature-forward, stable GA,
  version-pinned GA, EUS, or early-access development.
- Feature-forward demo installs prefer `fast-3.x` or active `fast-x.y` only
  when verified in the active OLM catalog.
- If `fast-3.x` is unavailable, the chosen fallback channel is documented and
  sourced from the catalog or lifecycle page.
- `alpha` is used only for explicit early-access development, not as a default
  demo channel.
- `embedded` and `beta` are not used for new installations.
- Technology Preview and Developer Preview features are labeled in README and
  GitOps review notes.

## GitOps Review

- Subscription channel matches the documented channel policy.
- `installPlanApproval` is `Automatic` only when continuous updates are intended.
- Manual approval is documented if chosen.
- Operator package name, catalog source, and namespace are sourced from the
  install chapter or verified OLM catalog, not inferred from this skill.
- README, operations docs, and GitOps manifests agree on channel choice.

## Readonly Cluster Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
# Find the RHOAI operator package name if it is not already known.
oc get packagemanifest -n openshift-marketplace | rg -i "openshift ai|rhoai|rhods"

# Replace <package> with the verified package name.
oc get packagemanifest <package> -n openshift-marketplace \
  -o jsonpath='{range .status.channels[*]}{.name}{"\n"}{end}'

# Check the installed Subscription channel and approval strategy.
oc get subscription -A | rg -i "openshift ai|rhoai|rhods"
oc get subscription <subscription-name> -n <operator-namespace> \
  -o jsonpath='{.spec.channel}{"\n"}{.spec.installPlanApproval}{"\n"}'
```

## Fail Conditions

- A manifest hard-codes `fast-3.x` without catalog verification.
- A manifest uses `embedded` or `beta` for a new installation.
- README claims production support for Technology Preview or Developer Preview
  content.
- GitOps channel choice conflicts with `docs/PLATFORM_BASELINE.md` or the
  active lifecycle page.
- A channel is selected only because it existed in a previous RHOAI release.
