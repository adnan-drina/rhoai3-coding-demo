# Official Documentation Extraction

## Product Concept

Model catalog sources control which provider-backed model entries are visible
to data scientists and AI engineers in the OpenShift AI model catalog.
Administrators can add, edit, preview, enable, disable, and delete catalog
sources and can filter source contents through model visibility patterns.

For regulated enterprise demos, treat this as a governance surface:

- source selection controls which providers appear in the catalog
- visibility patterns control which model names appear from a provider
- enabling a source exposes its matching models to users
- disabling a source removes its models from the catalog while keeping source
  configuration

## Dashboard Source View

Dashboard path:

```text
Settings -> Model resources and operations -> Model catalog settings
```

The source table includes:

- source name
- organization for Hugging Face sources
- model visibility status
- source type: Hugging Face repository or YAML file
- enable toggle
- validation status for enabled non-default sources

Default source names are:

- Red Hat AI
- Red Hat AI validated
- Other

Catalog sources can be filtered by source name, organization, model visibility,
source type, and enabled status.

## Enablement And Validation

New sources can remain disabled while details and visibility settings are
reviewed. Enabling a source makes matching models available to users and starts
source validation. Validation can show starting, successful, or failed
connection state.

Disable a source when its models should disappear from the catalog without
removing the source configuration.

## Model Visibility Patterns

Visibility settings support include and exclude patterns with wildcards.
OpenShift AI applies include patterns first, then applies exclude patterns to
the included set.

Pattern rules:

- Hugging Face source patterns use the model name without the organization
  prefix.
- YAML source patterns must use the full model name prefix including the
  organization.
- Use Preview before enabling or saving a source with changed patterns.

Examples from the official workflow:

- include `Llama*` to include model names that start with `Llama`
- exclude `Llama-2*` to remove Llama 2 models
- exclude `*DeepSeek*` to remove models whose names contain `DeepSeek`

## Hugging Face Source Limits

Hugging Face repository sources have these boundaries:

- public non-gated models only
- no private or gated models that require API keys or secret management
- connected environments only; disconnected environments are not supported
- cluster needs external network access to Hugging Face
- Red Hat does not validate or guarantee third-party model security
- deployment time can increase with model size and network speed

Use the Hugging Face organization URL slug in the Allowed organization field,
for example `meta-llama` or `ibm-granite`.

## YAML Source Requirements

YAML file sources can be uploaded or pasted through the dashboard. The YAML must
contain model definitions with model name, description, and deployment
information.

Custom YAML catalog sources configured in OpenShift use the
`model-catalog-sources` ConfigMap in the `rhoai-model-registries` namespace.
The ConfigMap `data.sources.yaml` entry contains a `catalogs` list.

Catalog entries include:

- `name`: user-friendly source name
- `id`: unique source ID
- `type`: use `yaml`
- `enabled`: whether the source is enabled; defaults to true
- `properties.yamlCatalogPath`: location of the catalog source file
- `labels`: optional labels displayed in the catalog

The custom catalog YAML can be stored in the same ConfigMap and referenced from
`properties.yamlCatalogPath`.

Custom model catalog sources are not supported on `s390x`.

## Add, Manage, And Delete

Add source:

- dashboard path: Settings -> Model resources and operations -> Model catalog
  settings
- click Add a source
- choose Hugging Face repository or YAML file
- optionally configure visibility patterns and Preview
- optionally enable the source
- verify the source appears in settings and, when enabled, reaches Connected
- verify models in AI hub -> Catalog

Manage source:

- use Manage source from the source list
- update name, organization, YAML file, visibility settings, or enablement
- save and verify catalog output

Delete source:

- only user-added sources can be deleted
- default catalog sources cannot be deleted
- deletion removes the source and its models from the catalog

## Verification Surfaces

Dashboard:

```text
Settings -> Model resources and operations -> Model catalog settings
AI hub -> Catalog
```

Read-only OpenShift checks:

```bash
oc get configmap model-catalog-sources -n rhoai-model-registries -o yaml
oc get namespace rhoai-model-registries
```

For live clusters, run these only after applying the repo's OpenShift safety
guard.
