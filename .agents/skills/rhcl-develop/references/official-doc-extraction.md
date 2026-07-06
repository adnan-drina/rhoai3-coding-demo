# Official Doc Extraction

Use this extraction to keep Connectivity Link API development content grounded
in the official RHCL 1.4 documentation. When implementation needs exact CRD
fields or RBAC rules, verify the active cluster schema before authoring
manifests.

## Console Plugin

The `kuadrant-console-plugin` is enabled via Administration > Cluster Settings >
Configuration > Console operator.config.openshift.io > Console plugins tab.

OCP 4.20+ supports full API management (gateway status, route objects, policy
management, API product management). OCP 4.19 supports gateway and policy
visibility with limited creation capability but no API management.

UI elements are displayed or hidden based on Kubernetes RBAC. Cluster
administrators see all features; developers and API owners are
namespace-scoped.

Console navigation sections:

- **Connectivity Link**: Overview, Policies, API Products, Policy Topology.
- **Connectivity Link API Catalog** (OCP 4.20+): API Key Approvals, My API
  Keys.

## API Management (Technology Preview)

API management with the OpenShift web console is a Technology Preview feature
in RHCL 1.4 on OCP 4.20+. Technology Preview features are not supported with
Red Hat production SLAs and might not be functionally complete.

### Custom Resource Definitions

- **APIProduct** (`devportal.kuadrant.io`): wraps an existing `HTTPRoute` CR
  with business context including human-readable name, documentation links,
  contact information, and access policies. Setting `publishStatus: Published`
  makes the API discoverable in the catalog.
- **APIKey** (`devportal.kuadrant.io`): represents actual API access credentials
  in the consumer namespace. Created by the controller when an access request
  is approved.
- **APIKeyRequest** (`devportal.kuadrant.io`): shadow resource in the API owner
  namespace enabling discovery without exposing API key values. Managed by the
  controller; must not be created or modified manually.
- **APIKeyApproval** (`devportal.kuadrant.io`): represents an approval or
  rejection action on an `APIKeyRequest`. Created by API owners and
  administrators.

### Authentication Methods

**API key authentication**: uses Kubernetes secrets to store credentials.
Suitable for internal APIs, development environments, or scenarios requiring
fine-grained access control. Supports automatic approval (immediate key
issuance) and manual approval (pending review by API owner).

**OIDC/JWT authentication**: delegates credential management to an external
identity provider. No `APIKey` resources are created. `AuthPolicy` CR validates
incoming requests. Suitable for enterprise SSO integration. Authentication
details (issuer URL, token endpoint) are surfaced in `APIProduct` status via
OIDC discovery.

An `OIDCPolicy` object can be created in the web console but is experimental
and not supported. Use `AuthPolicy` for OIDC authentication.

## API Workflows

### Publishing an API

Prerequisites:

- Console plugin enabled
- `HTTPRoute` CR routing traffic to API service
- `AuthPolicy` CR protecting the API
- `api-owner` role bound in namespace

Workflow:

1. Navigate to Connectivity Link > API Products.
2. Create APIProduct: set spec URL, documentation link, select HTTPRoute.
3. Choose approval mode (automatic or manual).
4. Authentication method is auto-discovered from `AuthPolicy`.
5. Verify: API visible in catalog, description clear, docs links working,
   auth requirements visible.

### Consuming an API

Prerequisites:

- Console plugin enabled
- `api-consumer` role bound in namespace
- API published in catalog

Workflow:

1. Browse API Products page for matching APIs.
2. Navigate to Connectivity Link API Catalog > My API Keys.
3. Select API Product, tier, enter key name and use case.
4. Click Request.
5. Wait for approval (automatic = immediate; manual = pending).
6. Retrieve credentials after approval.

Verification (API key method):

```bash
curl -H "Authorization: Bearer <api_key>" \
  https://<api_hostname>/<api_path>
```

For OIDC/JWT: obtain token from identity provider, use `Authorization: Bearer
<jwt_token>` header.

### Managing Access (Manual Approval)

Prerequisites:

- `api-owner` or `api-admin` role
- API published with manual approval
- Pending access requests

Workflow:

1. Navigate to Connectivity Link API Catalog > API Key Approvals.
2. Review requester, API product, use case, tier.
3. Approve or reject (single or bulk).
4. Add optional comments.

## RBAC

### Cluster Roles

**api-catalog-browser**: cluster-wide read access to `apiproducts`,
`planpolicies`, `authpolicies`, `ratelimitpolicies`, `httproutes`, `gateways`.
API groups: `devportal.kuadrant.io`, `extensions.kuadrant.io`, `kuadrant.io`,
`gateway.networking.k8s.io`. Verbs: get, list, watch.

Important: cluster role binding grants cluster-wide read access. No way to
limit catalog browsing to specific namespaces.

**api-consumer**: create and manage `apikeys` and `secrets` in assigned
namespaces. API groups: `devportal.kuadrant.io`, core (`""`). Verbs: get, list,
watch, create, update, patch, delete.

**api-owner**: publish APIs and manage consumer access. Includes cluster-wide
catalog read plus namespace-scoped write for `apiproducts`,
`apikeyapprovals`, and read for `apikeyrequests`. Does not grant access to
consumer `APIKey` or Secret resources.

**api-admin**: cluster-wide management. Same permissions as `api-owner` but
cluster-wide, plus `APIKey` write access for troubleshooting. Intentional
limitation: no secret read permissions in consumer namespaces.

### API Key Value Protection

Architectural isolation protects key values:

1. Consumer creates Secret with API key value, then creates `APIKey`
   referencing that Secret.
2. Controller creates `APIKeyRequest` shadow in owner namespace (no key value).
3. Owner creates `APIKeyApproval`.
4. Controller creates enforcement Secret in Connectivity Link namespace
   (consumer cannot access).
5. Owners and administrators do not see consumer key values.

### Role Binding Requirements

**Consumer**: requires both `ClusterRoleBinding` for `api-catalog-browser` (all
published APIs visible) and `RoleBinding` for `api-consumer` in their
namespace.

**Owner**: requires `RoleBinding` for `api-owner` in their team namespace.
Write operations namespace-scoped; read operations cluster-wide.

**Administrator**: requires `ClusterRoleBinding` for `api-admin`.

### RBAC Verification Commands

Verify consumer catalog browsing:

```bash
oc auth can-i list apiproducts \
  --as-group=<consumer_group> \
  --all-namespaces
```

Verify consumer key management in namespace:

```bash
oc auth can-i create apikeys \
  --as-group=<consumer_group> \
  -n <consumer_namespace>
```

Verify consumer isolation (should return "no"):

```bash
oc auth can-i create apikeys \
  --as-group=<consumer_group> \
  -n <other_namespace>
```

Verify owner product creation:

```bash
oc auth can-i create apiproducts \
  --as-group=<owner_group> \
  -n <owner_namespace>
```

Verify owner cannot access consumer keys (should return "no"):

```bash
oc auth can-i get apikeys \
  --as-group=<owner_group> \
  -n <consumer_namespace>
```

Verify admin cluster-wide access:

```bash
oc auth can-i list apikeys \
  --as-group=<admin_group> \
  --all-namespaces
```

## Demo-Specific Notes

The following are project constraints, not claims from the official docs:

- RHCL is held at `rhcl-operator.v1.3.4` per `docs/PLATFORM_BASELINE.md`.
  API management is a 1.4 Technology Preview feature and may not be available
  at the held operator version.
- Do not claim API management features are available until the operator version
  and OCP version are confirmed to support them.
- Do not commit real API keys, secrets, or identity provider credentials.
