# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md` plus the supporting Red Hat lifecycle and preview-scope
sources.

## Update Channel Purpose

Update channels specify which Red Hat OpenShift AI minor version the Operator
tracks for updates. The installed Operator Subscription records the channel and
uses it to track and receive updates. Changing the Subscription channel starts
tracking updates from the new channel.

## Channel Matrix

| Channel family | Release frequency | Support window from chapter | Recommended environment |
|----------------|-------------------|-----------------------------|-------------------------|
| `fast` or `fast-x.y` | Monthly | One month full support | Production environments that need latest product features |
| `stable` | Every three months | Three months full support | Production environments prioritizing stability over newest features |
| `stable-x.y` | Every three months | Seven months full support | Production environments that need a numbered GA planning window |
| `eus-x.y` | Every nine months | Seven months full support plus eleven months Extended Update Support | Enterprise environments that cannot upgrade within seven months |
| `alpha` | Monthly | One month full support in the table, but early-access features are not covered by production SLAs | Development environments testing early-access functionality |

The chapter says to use `fast` or `fast-x.y` with automatic updates to avoid
monthly manual upgrades when choosing latest product features.

The chapter says `embedded` and `beta` are legacy channels that should not be
selected for new Operator installations.

## Project Interpretation

For this feature-forward demo:

- prefer `fast-3.x` or the active `fast-x.y` channel family when available
- use automatic install-plan approval when the goal is continuous access to
  latest monthly product features
- verify channel availability from the OLM catalog before committing GitOps
- if the lifecycle page or catalog shows the fast channel is unavailable for
  the active release, use the current documented supported channel instead
- document technology-preview or developer-preview status per component; do
  not rely on channel choice alone to imply support posture

The user-provided lifecycle context notes that channel availability can change
across RHOAI releases. It specifically includes guidance that later 3.x
installations may use `stable-3.x` even when older releases used `fast`.
Therefore, this skill requires catalog verification before hard-coding
`fast-3.x`.

## Preview Support Boundaries

Technology Preview features provide early access to product innovations, are
not fully supported under Red Hat SLAs, might not be functionally complete, and
are not intended for production use.

Developer Preview content is not fully tested, is not intended for production,
is not supported by Red Hat, and might have no migration path to GA.

For this demo, preview features are acceptable when they are intentionally part
of the story, clearly labeled, and sourced from official release notes or
component documentation.

## Unresolved Items

This chapter does not define:

- the RHOAI Operator package name
- exact Subscription manifest fields beyond channel intent
- which channel names are present in a specific cluster catalog
- which features are Technology Preview in a given release

Use the relevant install chapter, release notes, and OLM catalog checks before
writing final GitOps.
