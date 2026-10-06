# Stage 060 native runtime candidate

Review-only customer configuration; not wired into the active Application.

Source NVIDIA/OpenShell 6648bd0c290efbc41ba131ee9831ee45cd431f94 (v0.1.2).
Native chart OCI ghcr.io/nvidia/openshell/helm-chart, version 0.1.2, digest
sha256:7a714bbbbcef7b5ed8dac599e89e89df12eb623fa4454d22f89df41d6f047e2a.
Verify the OCI artifact before passing its cached directory/archive to render.sh.
The source chart stays untouched; post-render.sh applies customer Kustomize
patches and the two workspace prerequisites. Generated manifests remain private.

```
OPENSHELL_CHART_PATH=/path/to/verified/chart ./render.sh > /private/tmp/openshell.yaml
```

The native chart creates a single StatefulSet/private ClusterIP gateway, SQLite
on its native 1Gi RWO claim, and native TLS/JWT generation Job. PVC retention is
explicit. Namespace openshell is owned by the candidate at Sync wave -30; no manual namespace bootstrap is needed. The deployment owner
must verify the default storage class provides local/block storage (not NFS),
PVC permissions, and backup compatibility. Customer resources own only configuration;
native chart/controller continue to own operands.

Native cluster workload CRUD is removed from the gateway ClusterRole. Namespace
watch/read, node discovery, RuntimeClass/PriorityClass read and TokenReview remain.
All sandbox/supervisor Pod, bootstrap Secret, Service and NetworkPolicy operations
are scoped by Roles to openshell-admin and openshell-developer. No namespace create
or delete, additional SCC, capabilities, anonymous access or SPIFFE grants.
Namespace-assigned UID/GID admission is used (fixed 1000 settings removed). Gateway
JWT Secret is group-readable 0440; verify admitted fsGroup, projected peer token and
key readability. Certgen also needs restricted-v2 admission qualification.

## Dynamic gates before apply

- Install the exact reviewed native OLM candidate: agent-sandbox-operator,
  preview-0.9, agent-sandbox-operator.v0.9.0, redhat-operators. Manual InstallPlan
  approval; verify bundle/controller digest, served Sandbox schema and controller
  ownership before approval. This file is a candidate, not permission to install.
- Existing identity reconciliation must supply ConfigMap
  stage060-openshell-identity key issuer in namespace openshell. Issuer is injected
  through the documented OPENSHELL_OIDC_ISSUER override, with audience
  openshell-gateway and explicit role claim/admin/user role overrides. A missing
  ConfigMap fails Pod startup. No private issuer URL is committed.
- Prove the gateway Rust TLS client trusts the actual issuer. If a custom CA is
  needed, use the native documented CA mount with the verified CA; do not invent
  a bundle or enable insecure TLS. Current candidate deliberately has no guessed CA.
- Create and retain Secret stage060-openshell-credentials key key-encryption-key,
  containing the native encoded 32-byte KEK. Never rotate it independently of the
  persisted credential database; do not generate random KEK during offline render.
- Native PKI Job owns retained TLS/JWT Secrets. Verify its completion and gateway
  SAN/CA validation before authenticated requests. Do not place generated keys in Git.
- Offline preflight is disabled only because helm template cannot discover APIs.
  Deployment must explicitly verify supported Agent Sandbox API/controller readiness.
- Workload kernel settings remain a separate sandbox configuration gate: restricted-v2,
  namespace UID/GID, RuntimeDefault, drop ALL, pod-local
  net.ipv4.ip_unprivileged_port_start=0 and legacy_read_only supervisor mode.
  The passed host probe does not demonstrate that the gateway applies these defaults
  to a dispatched sandbox. Qualify the real native dispatch before OpenCode acceptance.

## Native workspace and single-owner bootstrap

Workspace/Member are native persisted gateway API objects, NOT Kubernetes CRDs.
Operator mode maps Workspace name exactly to pre-created namespace. Both names
fit the 19-character native limit. Namespace labels form the discovery allowlist;
Kubernetes RBAC is independently restricted to the two namespaces.

Using platform-bootstrap authentication only, perform GetWorkspace before
CreateWorkspace, and ListWorkspaceMembers before AddWorkspaceMember. Reconcile
by canonical workspace name and actual OIDC sub. Do not infer sub from username
or OpenShift User UID. Proto JSON requests for native openshell.v1.OpenShell RPCs:

```
CreateWorkspace: {"name":"openshell-admin","labels":{"owner":"ai-admin"}}
CreateWorkspace: {"name":"openshell-developer","labels":{"owner":"ai-developer"}}
AddWorkspaceMember: {"workspaceScope":{"workspace":"openshell-admin"},"principalSubject":"<verified ai-admin OIDC sub>","role":"WORKSPACE_ROLE_USER"}
AddWorkspaceMember: {"workspaceScope":{"workspace":"openshell-developer"},"principalSubject":"<verified ai-developer OIDC sub>","role":"WORKSPACE_ROLE_USER"}
```

Member roles remain USER; human owners do not receive workspace ADMIN or platform
ADMIN. Only platform bootstrap creates/deletes workspaces and changes membership.
Verify exactly one intended human member in each workspace; remove no unrelated
membership automatically. Owners create/access/cancel their owned sandbox within
their working set; foreign member and unauthenticated probes must fail. Native
workspace delete preserves operator namespace; archive outputs and explicitly
cancel/delete owned sandbox before any separate retained-state deletion. Never use
namespace deletion as a workspace reset. Gateway PVC/KEK/PKI survive rollback.

## Static validation

Native Helm lint and helm template plus Kustomize post-render succeeded locally.
Shell syntax passed. No cluster writes or live runtime/tenant/controller claim.

## Argo native PKI lifecycle

All native certgen prerequisites (SA, Role, RoleBinding) have their Helm hook
annotations removed and are ordinary Sync wave -20 resources. The three customer
Namespaces run at Sync wave -30. The native generate-certs Job becomes an explicit
Argo Sync hook at wave -10, with BeforeHookCreation,HookSucceeded deletion. Gateway
resources remain wave 0. This avoids a PreSync Job depending on Sync prerequisites.
Certgen uses restricted non-root/RuntimeDefault/drop-ALL admission, and its
Secret GET rule names only the native server/client/JWT Secrets; CREATE must remain
namespace-scoped because Kubernetes cannot restrict CREATE using resourceNames.

The complete render stream must be transformed: Helm --post-renderer excludes
hook manifests from stdin, so render.sh pipes full helm template output through
Kustomize. Plain Argo Helm rendering does not run this script automatically. The
deployment owner must integrate the reviewed full-stream rendering mechanism or
publish its deterministic rendered output under the single Argo owner; do not
install a separate Helm release or manually apply resources. Controller candidate
is a separate Kustomize directory; manual OLM approval and readiness remain gates.
Do not add an Argo hook elsewhere while leaving unconverted native Helm hooks.

At source v0.1.2 certgen reads all three Secret names before creation: all present
is SkipExists; existing complete TLS pair without JWT adds only JWT; other partial
state is an error. There is no update/delete of existing TLS/JWT Secret material
in this path. Recreating only the Job on each sync does not rotate those keys.
Generated Secrets have no Job owner reference or Argo tracking annotation and
are not included in rendered desired resources, so Job cleanup/application prune
does not own/delete them. Namespace deletion still deletes them: gateway Namespace
uses Delete=false,Prune=false, and chart PVC retention is explicit. Back up the
namespace keys, gateway database/PVC and external KEK together. Never automate the
native error message's suggested Secret deletion; partial-state recovery requires
reviewed backup/restore or deliberate rotation with persisted-token impact.

Fresh render assertions passed: exactly one Sync certgen Job; hook-free certgen
SA/RBAC; Namespace -30 before SA/RBAC -20 before Job -10 before gateway 0; no
rendered Secret/random credential; no cluster-wide workload CRUD. These are static
ordering/source proofs, not live Argo sync or certificate validation evidence.

Sources: NVIDIA/OpenShell v0.1.2 crates/openshell-server/src/certgen.rs;
https://argo-cd.readthedocs.io/en/stable/user-guide/helm/ ;
https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/ .

## Checked-in integration contract

The candidate root kustomization includes rendered/ (26 native/customer resources,
exactly one per file) and controller/ (three reviewed OLM resources). It is ready
for the existing stage Application to consume after the outstanding gates; no new
Argo plugin or independent Helm owner. Native controller-owned operands are never
rendered by this customer configuration. Native release namespace is assigned by
Kustomize; the two workspace namespaces keep their separate resource identities.

Run regenerate.py with Python/PyYAML (already used by repository validation), Helm
and Kustomize. It validates the exact reviewed chart archive hash, runs the full
native render, applies the narrow customer post-render, refuses any Secret object,
and writes canonical one-resource YAML files. Source/chart/artifact digests are in
source-pins.json; OCI artifact digest and archive-layer hash are different identities.

```
python3 regenerate.py --chart /path/to/helm-chart-0.1.2.tgz --check
kustomize build .
```

Without --check it refreshes only rendered/; --check is read-only and fails on any
added/deleted/changed resource. Repeat generation and check succeeded with the
cached reviewed 0.1.2 archive. No CA/key/issuer URL/token is embedded in rendered/.
The old controller.yaml/workspaces.yaml multi-document inputs have been removed.
