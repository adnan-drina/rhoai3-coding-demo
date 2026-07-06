---
name: rhdh-techdocs-config
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring the TechDocs plugin for reading and managing technical
  documentation in Red Hat Developer Hub. Covers TechDocs builder modes, storage
  backends (AWS S3, OpenShift Data Foundation), CI/CD generation, add-ons
  (ReportIssue, TextSize, LightBox), third-party add-on packaging, and custom
  add-on creation. Do NOT use for general RHDH configuration (use
  rhdh-configure), appearance customization (use rhdh-customize), or upgrade
  procedures (use rhdh-upgrade).
---

# RHDH TechDocs Config

Use this skill to configure the TechDocs plugin for Red Hat Developer Hub 1.10
grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers TechDocs concepts,
builder modes, storage configuration, CI/CD pipeline generation, preinstalled
and external add-ons, third-party add-on installation, and custom add-on
creation.

## TechDocs Overview

The TechDocs plugin is preinstalled and enabled by default. It provides:
- Docs-like-code approach (Markdown stored alongside code)
- MkDocs-based static HTML site generation
- Built-in navigation and search
- Extensible via add-ons

## Builder Modes

- **local** (default, not for production) — built-in builder generates HTML
- **external** (production) — CI/CD pipeline generates docs, stores in cloud
  storage

## Storage Backends

### AWS S3

Required IAM permissions on bucket:
- `s3:ListBucket` on `arn:aws:s3:::<bucket_name>`
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`,
  `s3:DeleteObjectVersion` on `arn:aws:s3:::<bucket_name>/*`

### OpenShift Data Foundation

Uses `ObjectBucketClaim` CR with `storageClassName: openshift-storage.noobaa.io`.

```yaml
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: <rhdh_bucket_claim_name>
spec:
  generateBucketName: <rhdh_bucket_claim_name>
  storageClassName: openshift-storage.noobaa.io
```

Creating the OBC auto-generates a ConfigMap and Secret with access info.

### ODF with Helm chart

```yaml
upstream:
  backstage:
    extraEnvVarsSecrets:
      - <rhdh_bucket_claim_name>
    extraEnvVarsCM:
      - <rhdh_bucket_claim_name>
```

### ODF with Operator

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <name>
spec:
  application:
    extraEnvs:
      configMaps:
        - name: <rhdh_bucket_claim_name>
      secrets:
        - name: <rhdh_bucket_claim_name>
```

## TechDocs Plugin Configuration

### Helm chart example

```yaml
global:
  dynamic:
    includes:
      - 'dynamic-plugins.default.yaml'
  plugins:
    - disabled: false
      package: ./dynamic-plugins/dist/backstage-plugin-techdocs-backend-dynamic
      pluginConfig:
        techdocs:
          builder: external
          generator:
            runIn: local
          publisher:
            type: awsS3
            awsS3:
              bucketName: '${BUCKET_NAME}'
              credentials:
                accessKeyId: '${AWS_ACCESS_KEY_ID}'
                secretAccessKey: '${AWS_SECRET_ACCESS_KEY}'
              endpoint: 'https://${BUCKET_HOST}'
              region: '${BUCKET_REGION}'
              s3ForcePathStyle: true
```

For Operator deployment, wrap the same plugin config inside a ConfigMap
referenced by `spec.application.dynamicPluginsConfigMapName` in the Backstage CR.
See `references/official-doc-extraction.md` for the full Operator example.

## CI/CD Generation

```bash
npm install -g @techdocs/cli
pip install "mkdocs-techdocs-core==1.*"
techdocs-cli generate --no-docker
techdocs-cli publish --publisher-type awsS3 \
  --storage-name <bucket/container> \
  --entity <Namespace/Kind/Name>
```

## TechDocs Add-ons

| Add-on | Package | Type |
|--------|---------|------|
| ReportIssue | `backstage-plugin-techdocs-module-addons-contrib` | Preinstalled |
| TextSize | `backstage-plugin-techdocs-module-addons-contrib` | External |
| LightBox | `backstage-plugin-techdocs-module-addons-contrib` | External |

### Enable external add-ons (Operator)

```yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-plugin-techdocs-module-addons-contrib
    disabled: false
    pluginConfig:
      dynamicPlugins:
        frontend:
          backstage.plugin-techdocs-module-addons-contrib:
            techdocsAddons:
              - importName: ReportIssue
              - importName: TextSize
              - importName: LightBox
```

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the TechDocs task:
   - Configure storage backend (AWS S3 or ODF)
   - Set up CI/CD pipeline for doc generation
   - Enable/configure TechDocs add-ons
   - Install third-party add-ons
3. Apply configuration to the appropriate resource.
4. Restart RHDH pod to apply changes.
5. Verify static files appear in storage and docs render in the UI.

## Related Skills

- `rhdh-configure` — Config maps, secrets, and infrastructure configuration
- `rhdh-customize` — Appearance and feature customization
- `rhdh-upgrade` — Upgrade procedures
- `odf-object-bucket-claims` — ODF ObjectBucketClaim details

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
