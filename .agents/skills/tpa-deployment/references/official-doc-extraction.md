# Official Doc Extraction

Use this extraction to keep RHTPA deployment content grounded in official Red
Hat sources. When implementation needs exact CR fields, verify against the
installed Operator CRDs with `oc explain` or `oc get crd` before authoring
GitOps manifests.

## RHEL Deployment (Ansible)

### Prerequisites

- Red Hat Enterprise Linux 9.3 or later.
- Red Hat Hybrid Cloud Console account.
- Configured OIDC provider (Red Hat SSO or Amazon Cognito).
- Storage provider (Red Hat OpenShift Data Foundation or Amazon S3).
- Available PostgreSQL or Amazon RDS database instance.

### Procedure

1. Log in to the Red Hat Hybrid Cloud Console.
2. Navigate to Services > Red Hat Ansible Automation Platform.
3. Expand Automation Hub > Collections.
4. Search for `rhtpa` and select the `trusted_profile_analyzer` collection.
5. Follow the Documentation tab for the `tpa_single_node` role.

The `tpa_single_node` role contains all configuration parameters for
single-node RHTPA deployment on RHEL.

## OpenShift Resource Recommendations

| Resource | Baseline |
|----------|----------|
| CPU cores | 4 |
| RAM | 8 GB |
| Database storage | 45 GB |
| Object storage | 45 GB |

Object storage sizing formula: initial SBOM count x average document size +
daily update rate x 365 x average size + 20% buffer.

Example: 10,000 SBOMs at 500 KB = 5 GB initial. 100 updates/day at 500 KB =
18.25 GB/year growth. Total with 20% buffer: ~28 GB.

## OLM Operator Deployment

### Prerequisites

- Red Hat OpenShift Container Platform 4.17 or later.
- `cluster-admin` role on the OpenShift web console.
- Configured OIDC provider (Red Hat SSO or AWS Cognito).
- Storage provider (ODF or AWS S3).
- Available PostgreSQL or Amazon RDS database instance.

### Procedure

1. Navigate to the Red Hat Trusted Profile Analyzer Operator page in
   OperatorHub.
2. Under the Details tab, click Create instance on the
   `TrustedProfileAnalyzer` tile.
3. Select YAML view on the Create TrustedProfileAnalyzer page.
4. Copy the OIDC provider, storage, and importer sections from the applicable
   Helm values template (AWS or Red Hat services) and paste under `spec`.
5. Update values for your environment.
6. Click Create.

## Helm Deployment With AWS

### Prerequisites

- OpenShift Container Platform 4.17 or later.
- Ingress with publicly trusted HTTPS certificates.
- AWS account with S3, RDS (PostgreSQL), and Cognito.
- S3 bucket named `trustify-UNIQUE_ID` (globally unique across all AWS
  accounts and regions).

### Required Secrets

#### Storage Credentials (AWS)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: storage-credentials
  namespace: trusted-profile-analyzer
type: Opaque
data:
  aws_access_key_id: <BASE64_ACCESS_KEY>
  aws_secret_access_key: <BASE64_SECRET_KEY>
```

#### OIDC CLI Client Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: oidc-cli
  namespace: trusted-profile-analyzer
type: Opaque
data:
  client-secret: <BASE64_SECRET>
```

#### PostgreSQL Standard User Credentials

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgresql-credentials
  namespace: trusted-profile-analyzer
type: Opaque
data:
  db.host: <BASE64_HOST>
  db.name: <BASE64_DBNAME>
  db.user: <BASE64_USER>
  db.password: <BASE64_PASSWORD>
  db.port: <BASE64_PORT>
```

#### PostgreSQL Admin Credentials

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: postgresql-admin-credentials
  namespace: trusted-profile-analyzer
type: Opaque
data:
  db.host: <BASE64_HOST>
  db.name: <BASE64_DBNAME>
  db.user: <BASE64_USER>
  db.password: <BASE64_PASSWORD>
  db.port: <BASE64_PORT>
```

### Helm Install Procedure

```shell
oc login --token=TOKEN --server=SERVER_URL_AND_PORT
oc new-project trusted-profile-analyzer

export NAMESPACE=trusted-profile-analyzer
export APP_DOMAIN_URL=-$NAMESPACE.$(oc -n openshift-ingress-operator \
  get ingresscontrollers.operator.openshift.io default \
  -o jsonpath='{.status.domain}')

helm repo add openshift-helm-charts https://charts.openshift.io/
helm repo update

helm upgrade --install redhat-trusted-profile-analyzer \
  openshift-helm-charts/redhat-trusted-profile-analyzer \
  -n $NAMESPACE \
  --values values-rhtpa.yaml \
  --values values-importers.yaml \
  --set-string appDomain=$APP_DOMAIN_URL
```

The Helm chart is idempotent and can be re-run to apply configuration changes.

### AWS Values File Template (Appendix A)

Key top-level sections in `values-rhtpa.yaml`:

```yaml
appDomain: $APP_DOMAIN_URL

ingress:
  className: openshift-default
  additionalAnnotations:
    "haproxy.router.openshift.io/timeout": "5m"

authenticator:
  type: cognito

storage:
  type: s3
  region: REGION
  bucket: trustify-UNIQUE_ID
  accessKey:
    valueFrom:
      secretKeyRef:
        name: storage-credentials
        key: aws_access_key_id
  secretKey:
    valueFrom:
      secretKeyRef:
        name: storage-credentials
        key: aws_secret_access_key

database:
  sslMode: require
  host/port/name/username/password:
    valueFrom: secretKeyRef -> postgresql-credentials

createDatabase:
  name/username/password:
    valueFrom: secretKeyRef -> postgresql-admin-credentials

migrateDatabase:
  username/password:
    valueFrom: secretKeyRef -> postgresql-admin-credentials

modules:
  createDatabase:
    enabled: true
  migrateDatabase:
    enabled: true

oidc:
  issuerUrl: https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID
  clients:
    frontend:
      clientId: FRONTEND_CLIENT_ID
    cli:
      clientId: CLI_CLIENT_ID
      clientSecret:
        valueFrom:
          secretKeyRef:
            name: oidc-cli
            key: client-secret
```

## Helm Deployment With Red Hat Services

### Prerequisites

Same as AWS path, except:

- Red Hat SSO replaces Cognito as OIDC provider.
- ODF S3-compatible storage replaces AWS S3.
- Self-managed PostgreSQL replaces Amazon RDS.

### Required Secrets

Same Secret names and structure as the AWS path, with different keys for
storage credentials:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: storage-credentials
  namespace: trusted-profile-analyzer
type: Opaque
data:
  user: <BASE64_ACCESS_KEY>
  password: <BASE64_SECRET_KEY>
```

### Red Hat Services Values File Template (Appendix B)

Differences from the AWS template:

- No `authenticator.type` field (defaults to generic OIDC).
- `storage.region` is set to `S3_ENDPOINT_URL` (ODF endpoint).
- Storage secret keys are `user` and `password` instead of `aws_access_key_id`
  and `aws_secret_access_key`.
- `oidc.issuerUrl` is `OIDC_ISSUER_URL` (Red Hat SSO Keycloak realm).

## Importer Values File Template (Appendix C)

Default importers configured via `values-importers.yaml`:

| Importer | Type | Source | Default state |
|----------|------|--------|---------------|
| `redhat-sboms` | sbom | `https://access.redhat.com/security/data/sbom/beta/` | disabled |
| `redhat-csaf` | csaf | `redhat.com` | disabled |
| `cve` | cve | `https://github.com/CVEProject/cvelistV5` | enabled |
| `osv-github` | osv | `https://github.com/github/advisory-database` (path: `advisories`) | enabled |
| `quay-redhat-user-workloads` | quay | `quay.io` (namespace: `redhat-user-workloads`) | disabled |

All importers use a `1d` sync period. Red Hat SBOMs and CSAF importers use
`fetchRetries: 50`. The Red Hat SBOM importer requires a GPG key from
`https://access.redhat.com/security/data/97f5eac4.txt`.

## Validation

### Verify Console URL

```shell
oc -n $NAMESPACE get route --selector app.kubernetes.io/name=server \
  -o jsonpath='https://{.items[0].status.ingress[0].host}{"\n"}'
```

### Verify Pods

```shell
oc -n trusted-profile-analyzer get pods
```

### Verify Helm Release

```shell
helm -n trusted-profile-analyzer list
helm -n trusted-profile-analyzer status redhat-trusted-profile-analyzer
```

### Verify OLM Operator

```shell
oc get csv -n openshift-operators | grep -i trust
oc get TrustedProfileAnalyzer -A
```

## Boundaries

- This extraction covers deployment procedures only.
- Post-deployment administration, user management, SBOM lifecycle, and API
  usage belong in separate skills.
- OIDC provider setup (Keycloak realm creation, Cognito user pool
  configuration) is outside the scope of this guide.
- ODF bucket provisioning and PostgreSQL/RDS instance creation are outside the
  scope of this guide.
- The exact `apiVersion` for the `TrustedProfileAnalyzer` CRD is not stated in
  the deployment guide text; verify with `oc get crd | grep trust` after
  Operator installation.
