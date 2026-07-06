# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub GKE installation content
grounded in official Red Hat sources. When implementation needs exact CR fields,
verify against the official documentation before authoring manifests.

## Operator-Based Installation on GKE

### Prerequisites

- Red Hat Container Registry credentials (`registry.redhat.io`).
- Google Cloud CLI (`gcloud`) installed.
- `kubectl` CLI access to GKE cluster with developer or admin permissions.
- GKE Autopilot or GKE Standard cluster running.

### Platform Differences vs OpenShift

On GKE the most notable differences over an OpenShift-based installation:

- The OLM framework and the Red Hat Container Registry are not built-in.
- The Red Hat Container Registry pull-secret is not managed globally.
- Ingresses replace OpenShift Routes to expose the application.

### Connect to GKE Cluster

```shell
gcloud container clusters get-credentials <cluster_name> --location=<cluster_location>
```

### Install the Operator via OLM

Create the operator namespace:

```shell
kubectl create namespace rhdh-operator
```

Create a pull secret:

```shell
kubectl -n rhdh-operator create secret docker-registry rhdh-pull-secret \
    --docker-server=registry.redhat.io \
    --docker-username=<redhat_user_name> \
    --docker-password=<redhat_password> \
    --docker-email=<email>
```

Create a CatalogSource:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: redhat-catalog
spec:
  sourceType: grpc
  image: registry.redhat.io/redhat/redhat-operator-index:v4.21
  secrets:
  - "rhdh-pull-secret"
  displayName: Red Hat Operators
```

Create an OperatorGroup:

```yaml
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: rhdh-operator-group
```

Create a Subscription:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhdh
  namespace: rhdh-operator
spec:
  channel: fast
  installPlanApproval: Automatic
  name: rhdh
  source: redhat-catalog
  sourceNamespace: rhdh-operator
  startingCSV: rhdh-operator.v1.10.1
```

Wait for the Operator deployment and patch with pull secret:

```shell
until kubectl -n rhdh-operator get deployment rhdh-operator &>/dev/null; do
  echo -n .
  sleep 3
done
echo "RHDH Operator Deployment created"

kubectl -n rhdh-operator patch deployment \
    rhdh-operator --patch '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"rhdh-pull-secret"}]}}}}' \
    --type=merge
```

Verification:

```shell
kubectl get deployment -n rhdh-operator
```

### Provision Custom Configuration

Store secrets in a `secrets.txt` file (one `KEY=value` per line).

Create the `app-config.yaml` ConfigMap with `baseUrl` settings:

```yaml
app:
  title: Red Hat Developer Hub
  baseUrl: https://<my_developer_hub_domain>
backend:
  auth:
    externalAccess:
      - type: legacy
        options:
          subject: legacy-default-config
          secret: "${BACKEND_SECRET}"
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

The `baseUrl` is **required** for the Red Hat Developer Hub to function
correctly. Frontend and backend services cannot communicate properly without it.

Enable dynamic plugins via `dynamic-plugins.yaml`:

```yaml
includes:
  - dynamic-plugins.default.yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github
    disabled: false
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

Provision to the cluster:

```shell
kubectl create namespace my-rhdh-project
kubectl create configmap my-rhdh-app-config --from-file=app-config.yaml --namespace=my-rhdh-project
kubectl create configmap dynamic-plugins-rhdh --from-file=dynamic-plugins.yaml --namespace=my-rhdh-project
kubectl create secret generic my-rhdh-secrets --from-file=secrets.txt --namespace=my-rhdh-project
```

### Provision Pull Secret in Instance Namespace

On GKE the pull secret is not managed globally. Create it in the RHDH instance
namespace and patch the default ServiceAccount:

```shell
kubectl -n <my-rhdh-namespace> create secret docker-registry my-rhdh-pull-secret \
    --docker-server=registry.redhat.io \
    --docker-username=<redhat_user_name> \
    --docker-password=<redhat_password> \
    --docker-email=<email>

kubectl patch serviceaccount default \
    -p '{"imagePullSecrets": [{"name": "my-rhdh-pull-secret"}]}' \
    -n <my-rhdh-namespace>
```

### Backstage CR

Minimal Backstage custom resource:

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: my-rhdh-custom-resource
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
    extraFiles:
      mountPath: /opt/app-root/src
    route:
      enabled: true
  database:
    enableLocalDb: true
```

Extended example with dynamic plugins, RBAC, and external PostgreSQL:

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <my-rhdh-custom-resource>
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
         - name: my-rhdh-app-config
         - name: rbac-policies
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      secrets:
         - name: <my_product_secrets>
         - name: my-rhdh-database-secrets
    extraFiles:
      mountPath: /opt/app-root/src
      secrets:
        - name: my-rhdh-database-certificates-secrets
          key: postgres-crt.pem, postgres-ca.pem, postgres-key.key
    route:
      enabled: true
  database:
    enableLocalDb: false
```

Apply the CR:

```shell
kubectl apply --filename=my-rhdh-custom-resource.yaml --namespace=my-rhdh-project
```

### Expose via Ingress

On GKE, create a Google-managed certificate, FrontendConfig, and Ingress.

ManagedCertificate:

```yaml
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: my-rhdh-certificate-name
spec:
  domains:
    - <my_developer_hub_domain>
```

FrontendConfig for HTTPS redirect:

```yaml
apiVersion: networking.gke.io/v1beta1
kind: FrontendConfig
metadata:
  name: my-ingress_security_config
spec:
  sslPolicy: gke-ingress-ssl-policy-https
  redirectToHttps:
    enabled: true
```

Ingress with GCE class, static IP, managed certificate, and frontend config:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-rhdh-ingress
  annotations:
    kubernetes.io/ingress.class: "gce"
    kubernetes.io/ingress.global-static-ip-name: <ADDRESS_NAME>
    networking.gke.io/managed-certificates: my-rhdh-certificate-name
    networking.gke.io/v1beta1.FrontendConfig: my-ingress_security_config
spec:
  ingressClassName: gce
  rules:
    - host: <my_developer_hub_domain>
      http:
        paths:
        - path: /
          pathType: Prefix
          backend:
            service:
              name: my-rhdh-custom-resource
              port:
                name: http-backend
```

Prerequisites for GKE Ingress:

- Reserved static external Premium IPv4 Global IP address (not attached to any
  VM).
- Domain name configured with DNS `A` record pointing to the reserved IP.
- DNS propagation can take up to one hour.
- ManagedCertificate provisioning can take a couple of hours.

Deploy all resources:

```shell
kubectl -n my-rhdh-project apply -f managed-certificate.yaml
kubectl -n my-rhdh-project apply -f frontend-config.yaml
kubectl -n my-rhdh-project apply -f rhdh-ingress.yaml
```

Access at `https://<my_developer_hub_domain>` after certificate provisioning.

## Helm Chart Installation on GKE

### Prerequisites

- Red Hat Container Registry subscription.
- `kubectl`, `gcloud` CLI, and Helm 3 installed.
- GKE Autopilot or GKE Standard cluster running.
- Domain name configured with reserved static IP and DNS `A` record.
- System meets minimum sizing requirements.

### Procedure

Add the Helm repo:

```shell
helm repo add openshift-helm-charts https://charts.openshift.io/
```

Create a pull secret:

```shell
kubectl -n <your_namespace> create secret docker-registry rhdh-pull-secret \
    --docker-server=registry.redhat.io \
    --docker-username=<user_name> \
    --docker-password=<password> \
    --docker-email=<email>
```

Create ManagedCertificate and FrontendConfig (same as Operator method above).

Create `values.yaml`:

```yaml
global:
  host: <rhdh_domain_name>
route:
  enabled: false
upstream:
  service:
    type: NodePort
  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: gce
      kubernetes.io/ingress.global-static-ip-name: <ADDRESS_NAME>
      networking.gke.io/managed-certificates: <rhdh_certificate_name>
      networking.gke.io/v1beta1.FrontendConfig: <ingress_security_config>
    className: gce
  backstage:
    image:
      pullSecrets:
      - rhdh-pull-secret
    podSecurityContext:
      fsGroup: 2000
  postgresql:
    image:
      pullSecrets:
      - rhdh-pull-secret
    primary:
      podSecurityContext:
        enabled: true
        fsGroup: 3000
  volumePermissions:
    enabled: true
```

Install:

```shell
helm -n <your_namespace> install -f values.yaml <your_deploy_name> \
  openshift-helm-charts/redhat-developer-hub \
  --version 1.10.1
```

Verification:

```shell
kubectl get deploy <your_deploy_name>-developer-hub -n <your_namespace>
kubectl get service -n <your_namespace>
kubectl get ingress -n <your_namespace>
```

Wait for ManagedCertificate provisioning (can take a couple of hours).

Upgrade:

```shell
helm -n <your_namespace> upgrade -f values.yaml <your_deploy_name> \
  openshift-helm-charts/redhat-developer-hub --version <UPGRADE_CHART_VERSION>
```

Delete:

```shell
helm -n <your_namespace> delete <your_deploy_name>
```
