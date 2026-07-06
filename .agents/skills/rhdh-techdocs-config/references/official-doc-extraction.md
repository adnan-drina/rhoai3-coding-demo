# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — TechDocs for Red Hat Developer Hub
Captured: 2026-07-06

---

## 1. TechDocs Concepts

The TechDocs plugin is preinstalled and enabled by default. Features:

- **Docs-like-code** — Markdown files stored alongside project code
- **MkDocs generation** — Static HTML site from Markdown
- **Central rendering** — Documentation rendered in the RHDH Docs tab
- **Metadata** — Last update date, site owner, contributors, GitHub issues,
  Slack channels, Stack Overflow tags
- **Navigation and search** — Built-in full-text search
- **Add-ons** — Extend TechDocs functionality (preinstalled and external)

---

## 2. Builder Modes

| Mode | Usage | Description |
|------|-------|-------------|
| `local` | Development only | Built-in builder generates HTML locally |
| `external` | Production | CI/CD pipeline generates docs externally |

Production setup requires:
1. External builder (`techdocs.builder: external`)
2. Cloud storage for generated files
3. CI/CD job to generate and publish docs

---

## 3. Storage Configuration

### 3.1 Amazon S3

Required IAM policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "TechDocsList",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::<bucket_name>"
        },
        {
            "Sid": "TechDocsObjects",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:DeleteObjectVersion"
            ],
            "Resource": "arn:aws:s3:::<bucket_name>/*"
        }
    ]
}
```

### 3.2 OpenShift Data Foundation

Recommended for air-gapped environments.

#### ObjectBucketClaim

```yaml
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: <rhdh_bucket_claim_name>
spec:
  generateBucketName: <rhdh_bucket_claim_name>
  storageClassName: openshift-storage.noobaa.io
```

Creating the OBC auto-generates a ConfigMap and Secret with the same name,
containing environment variables:
- `BUCKET_NAME`
- `BUCKET_HOST`
- `BUCKET_PORT`
- `BUCKET_REGION`
- `BUCKET_SUBREGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

#### Helm chart integration

```yaml
upstream:
  backstage:
    extraEnvVarsSecrets:
      - <rhdh_bucket_claim_name>
    extraEnvVarsCM:
      - <rhdh_bucket_claim_name>
```

#### Operator integration

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

---

## 4. TechDocs Plugin Configuration

### Helm chart

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

### Operator ConfigMap

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: dynamic-plugins-rhdh
data:
  dynamic-plugins.yaml: |
    includes:
      - dynamic-plugins.default.yaml
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

---

## 5. CI/CD Generation and Publishing

```bash
REPOSITORY_URL='https://github.com/org/repo'
git clone $REPOSITORY_URL
cd repo

npm install -g @techdocs/cli
pip install "mkdocs-techdocs-core==1.*"

techdocs-cli generate --no-docker

techdocs-cli publish --publisher-type awsS3 \
  --storage-name <bucket/container> \
  --entity <Namespace/Kind/Name>
```

Trigger CI when files in `docs/` directory or `mkdocs.yml` change.

---

## 6. TechDocs Add-ons

### Available add-ons

| Add-on | Package | Description | Type |
|--------|---------|-------------|------|
| ReportIssue | `backstage-plugin-techdocs-module-addons-contrib` | Select text, open issue with auto-populated template | Preinstalled |
| TextSize | `backstage-plugin-techdocs-module-addons-contrib` | Customize text size with slider/buttons | External |
| LightBox | `backstage-plugin-techdocs-module-addons-contrib` | Open images in light-box overlay | External |

The `backstage-plugin-techdocs-module-addons-contrib` package is preinstalled
and enabled by default. If disabled, all exported add-ons are also disabled.

### Install external add-ons (Operator)

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: dynamic-plugins-rhdh
data:
  dynamic-plugins.yaml: |
    includes:
      - dynamic-plugins.default.yaml
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

Reference in Backstage CR:
```yaml
spec:
  application:
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
```

### Install external add-ons (Helm chart)

```yaml
global:
  dynamic:
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

---

## 7. Third-Party Add-on Installation

Prerequisites:
- Valid `package.json` in plugin root
- Plugin packaged as dynamic plugin in OCI image
- `yarn` and Node.js/NPM installed

Steps:
```bash
yarn install
npx @red-hat-developer-hub/cli@latest plugin export
npx @red-hat-developer-hub/cli@latest plugin package \
  --tag quay.io/<user_name>/<techdocs_add-on_image>:latest
```

---

## 8. Verification

- Check Amazon S3 bucket for static site files in Objects list
- Navigate to entity Docs tab in RHDH to verify documentation renders
- Restart pod after configuration changes: Topology > Actions > Restart rollout
