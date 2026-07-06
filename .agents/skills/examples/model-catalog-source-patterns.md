# Model Catalog Source Patterns

## Dashboard Paths

```text
OpenShift AI dashboard -> Settings -> Model resources and operations -> Model catalog settings
OpenShift AI dashboard -> AI hub -> Catalog
```

## Hugging Face Source Review

Use this shape when documenting a governed Hugging Face source:

```text
Source name: Reviewed Llama Family
Source type: Hugging Face repository
Allowed organization: meta-llama
Initial state: disabled until Preview and compliance review complete
Include models: Llama*
Exclude models: Llama-2*, *DeepSeek*
Verification:
- Model catalog settings shows the source and validation status.
- AI hub -> Catalog shows only reviewed matching models after enablement.
```

Hugging Face visibility patterns use the model name without the organization
prefix.

## YAML Source Review

Use this shape when documenting a governed YAML source:

```text
Source name: ACME Approved Models
Source type: YAML file
Initial state: disabled until YAML provenance and Preview review complete
Label: ACME Approved
Include models: acme-approved/*
Exclude models: *experimental*
Verification:
- Model catalog settings shows the source and validation status.
- AI hub -> Catalog shows ACME Approved models after enablement.
```

YAML visibility patterns must use the full model name prefix including the
organization.

## ConfigMap Shape

Minimal custom YAML catalog source shape for GitOps review:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: model-catalog-sources
  namespace: rhoai-model-registries
data:
  sources.yaml: |-
    catalogs:
    - name: ACME Approved Models
      id: acme_approved_models
      type: yaml
      enabled: false
      properties:
        yamlCatalogPath: acme-approved-models.yaml
      labels:
      - ACME Approved
  acme-approved-models.yaml: |-
    <reviewed model catalog YAML>
```

Keep `enabled: false` until the catalog source content and visibility patterns
are reviewed.
