# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub AKS installation content
grounded in official Red Hat sources. When implementation needs exact CR fields,
verify against the official documentation before authoring manifests.

## Operator-Based Installation on AKS

### Prerequisites

- Red Hat Container Registry credentials (`registry.redhat.io`).
- `kubectl` CLI access to AKS cluster with developer or admin permissions.
- Microsoft Azure account with AKS cluster running.

### Platform Differences vs OpenShift

On AKS the most notable differences over an OpenShift-based installation:

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

On AKS the pull secret is not managed globally. Create it in the RHDH instance
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

On AKS, create a Kubernetes Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-rhdh-ingress
  namespace: my-rhdh-project
spec:
  ingressClassName: webapprouting.kubernetes.azure.com
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-rhdh-custom-resource
                port:
                  name: http-backend
```

Deploy and access:

```shell
kubectl -n my-rhdh-project apply -f rhdh-ingress.yaml
```

Access at `https://<app_address>` where `<app_address>` is the Ingress address.

## Helm Chart Installation on AKS

### Prerequisites

- Microsoft Azure account with active subscription.
- Azure CLI, `kubectl`, and Helm 3 installed.
- Developer or admin permissions on the cluster.
- System meets minimum sizing requirements.

### AKS-Specific Considerations

- **Permissions**: Set `fsGroup` in `PodSpec.securityContext` to avoid
  `Permission denied` errors.
- **Ingress**: Enable the Routing add-on (NGINX-based Ingress Controller):
  `az aks approuting enable --resource-group <rg> --name <cluster>`
- **Ingress address**: Retrieve with:
  `kubectl get svc nginx --namespace app-routing-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`

### Procedure

Add the Helm repo:

```shell
helm repo add openshift-helm-charts https://charts.openshift.io/
```

Create namespace and pull secret:

```shell
DEPLOYMENT_NAME=<redhat-developer-hub>
NAMESPACE=<rhdh>
kubectl create namespace ${NAMESPACE}
kubectl config set-context --current --namespace=${NAMESPACE}

kubectl -n $NAMESPACE create secret docker-registry rhdh-pull-secret \
    --docker-server=registry.redhat.io \
    --docker-username=<redhat_user_name> \
    --docker-password=<redhat_password> \
    --docker-email=<email>
```

Create `values.yaml`:

```yaml
global:
  host: <app_address>
route:
  enabled: false
upstream:
  ingress:
    enabled: true
    className: webapprouting.kubernetes.azure.com
    host:
  backstage:
    image:
      pullSecrets:
        - rhdh-pull-secret
    podSecurityContext:
      fsGroup: 3000
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
helm -n $NAMESPACE install -f values.yaml $DEPLOYMENT_NAME \
  openshift-helm-charts/redhat-developer-hub --version 1.10.1
```

Verification:

```shell
kubectl get deploy $DEPLOYMENT_NAME -n $NAMESPACE
```
