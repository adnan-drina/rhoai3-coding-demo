# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub EKS installation content
grounded in official Red Hat sources. When implementation needs exact CR fields,
verify against the official documentation before authoring manifests.

## Operator-Based Installation on EKS

### Prerequisites

- Red Hat Container Registry credentials (`registry.redhat.io`).
- `kubectl` CLI access to EKS cluster with developer or admin permissions.
- Amazon Web Services account with EKS cluster running.

### Platform Differences vs OpenShift

On EKS the most notable differences over an OpenShift-based installation:

- The OLM framework and the Red Hat Container Registry are not built-in.
- The Red Hat Container Registry pull-secret is not managed globally.
- Ingresses replace OpenShift Routes to expose the application.

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

On EKS the pull secret is not managed globally. Create it in the RHDH instance
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

No fields are mandatory; an empty Backstage CR runs Developer Hub with default
configuration.

Apply the CR:

```shell
kubectl apply --filename=my-rhdh-custom-resource.yaml --namespace=my-rhdh-project
```

### Expose via Ingress

On EKS, create a Kubernetes Ingress with ALB annotations:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-rhdh-ingress
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-xxx:xxxx:certificate/xxxxxx
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS":443}]'
    alb.ingress.kubernetes.io/ssl-redirect: '443'
    external-dns.alpha.kubernetes.io/hostname: <my_developer_hub_domain>
spec:
  ingressClassName: alb
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

Prerequisites for EKS Ingress:

- EKS cluster with AWS Application Load Balancer (ALB) add-on installed.
- Domain name configured (Route 53 or external DNS).
- Certificate ARN from AWS Certificate Manager.
- kubeconfig context set to the EKS cluster.

Deploy and access:

```shell
kubectl -n my-rhdh-project apply -f rhdh-ingress.yaml
```

Wait until the DNS name is responsive.

## Helm Chart Installation on EKS

### Prerequisites

- EKS cluster with AWS ALB add-on installed.
- Domain name configured with certificate ARN.
- Red Hat Container Registry subscription.
- `kubectl` and Helm 3 installed.
- Working default storage class (e.g. EBS storage add-on).
- System meets minimum sizing requirements.

### Procedure

Add the Helm repo:

```shell
helm repo add openshift-helm-charts https://charts.openshift.io/
```

Create a pull secret:

```shell
kubectl create secret docker-registry rhdh-pull-secret \
    --docker-server=registry.redhat.io \
    --docker-username=<user_name> \
    --docker-password=<password> \
    --docker-email=<email>
```

Create `values.yaml`:

```yaml
global:
  host: <your Developer Hub domain name>
route:
  enabled: false
upstream:
  service:
    type: NodePort
  ingress:
    enabled: true
    annotations:
      kubernetes.io/ingress.class: alb
      alb.ingress.kubernetes.io/scheme: internet-facing
      alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:xxx:xxxx:certificate/xxxxxx
      alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS":443}]'
      alb.ingress.kubernetes.io/ssl-redirect: '443'
      external-dns.alpha.kubernetes.io/hostname: <your rhdh domain name>
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
helm install rhdh \
  openshift-helm-charts/redhat-developer-hub \
  [--version 1.10.1] \
  --values /path/to/values.yaml
```

Verification: Wait until the DNS name is responsive.
