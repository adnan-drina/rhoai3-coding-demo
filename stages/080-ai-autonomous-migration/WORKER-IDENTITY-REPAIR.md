# Migration-worker identity repair — Stage 050

Publish the reviewed repair through Stage 050 GitOps, then qualify disposable
workspaces using the procedure below. Actual v11 creation remains the user's
manual handoff after qualification. Closed v10 stays untouched.

## Why disableCreation is not used

Installed DevWorkspace Operator **0.43.0** accepts
`config.workspace.serviceAccount.disableCreation` and `serviceAccountName`
(`oc explain` and server-side dry-run). The controller still calls
`rbac.SyncRBAC` **before** that branch
(`controllers/workspace/devworkspace_controller.go`). `SyncRBAC` adds
`common.ServiceAccountName()` to operator-owned `devworkspace-default-role`,
which is namespace-wide Secret mutation, ConfigMap mutation, `pods/exec`, and
DevWorkspace patch. Setting `serviceAccountName` (required when creation is
disabled) makes **that** account the subject. disableCreation only skips
creating the ServiceAccount object.

Live Che `DevWorkspaceOperatorConfig/devworkspace-config` has
`disableCreation: false`. Restricted pod-override fields are unset, so
`pod-overrides.spec.serviceAccountName` is allowed. Always-restricted fields
remain `containers` / `initContainers`.

## What this repair does

The platform provisioner creates `<run>-worker` ServiceAccount, Role, and
RoleBinding in `wksp-ai-developer`, labelled `rhoai3.io/migration-run=<run>`.
Retirement deletes those kinds by the same label. The factory destfile selects
that ServiceAccount with `pod-overrides`. DWO still generates `workspace*-sa`
and binds **that** leftover account to `devworkspace-default-role`. The worker
pod must not mount it.

Che injects `controller.devfile.io/scc: container-build`. DWO binds that SCC to
the generated SA, not the pod-overrides SA. The worker Role therefore grants
`use` of that named SCC. The provisioner has a ClusterRole limited to the same
named SCC so Kubernetes privilege-escalation checks allow copying it.

GitOps does not patch `devworkspace-default-role`. Existing v10, v9, and
`agentic-coolstore` objects are not named in this change.

## Permission matrix

Identities in a **new** migration worker pod:

| Principal | How it appears | Secrets (other run) | Own receipt / lock | RBAC / SA / DWOC | Own DevWorkspace | pods/exec | ConfigMap `devspace-ai-tools-init` | container-build SCC |
|---|---|---|---|---|---|---|---|---|
| Pod ServiceAccount `<run>-worker` | `spec.serviceAccountName` via destfile pod-overrides; projected token | deny | deny | deny | deny | deny | get only | use |
| Leftover `workspace*-sa` | DWO-generated; bound to `devworkspace-default-role`; **not** the pod identity | yes (default role) | yes | no create of Roles; DW patch yes | patch/update | create | yes | use (DWO bind) |
| `~/.kube/config` | destfile replacement Config (`tokenFile` of the projected SA token). Not `oc login`. Missing token or a failed write refuses dest-init; leftover users/contexts are removed. dest-init `ensure_in_cluster_kubeconfig` keeps an existing file; this bind runs first in the same postStart. | same as pod SA | same | same | same | same | same | same |
| Human `ai-developer` | `wksp-edit-ai-developer` ClusterRole `edit`; Che dashboard | outside worker boundary | outside | outside | start/stop/restart | outside | outside | `devspaces-user-container-build` |
| `migration-run-provisioner` | SA only in `app-platform-build` (not selectable from the workspace namespace). Its Role in `wksp-ai-developer` is **namespace-wide** get/list/create/patch/update/delete on secrets, configmaps, services, serviceaccounts, deployments, roles and rolebindings. `rhoai3.io/migration-run` labels constrain what the Task script creates, lists and deletes; they are not `resourceNames` and do not limit API authorization. | **yes, any Secret in the namespace** | yes, any ConfigMap | yes, any SA/Role/RoleBinding in the namespace | no DevWorkspace verbs | no | yes | use (named SCC ClusterRole, so it can grant that rule) |
| Operator `devworkspace-default-role` | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged | n/a |

Worker Role rules actually granted:

1. `get` ConfigMap `devspace-ai-tools-init` — destfile postStart fallback when the volume is empty (BACKLOG least-privilege GET).
2. `use` SCC `container-build` — required for the admitted workspace pod profile.

The worker Role does not add the following permissions:

- Secret get/list/create/patch/update/delete. Effective access is additive:
  the existing `devspace-maas-key-workspace-readers` group binding grants GET
  on **only** `maas-devspace-api-keys` and `workspace-maas-credentials`.
  Preserve and report this named MaaS exception; it grants no other-run parity
  Secret access and no Secret list or mutation.
- ConfigMap create/patch/update/delete, including receipts and locks.
- DevWorkspace get/patch/update (lifecycle stays with the platform/user; destfile hostAlias merge is Operator `patch-workspace-maas-route.sh`).
- ServiceAccount, Role, RoleBinding, DWOC create/bind.
- `pods/exec` and pod create.
- Cross-run reads via `resourceNames` omission.

Shared automounts the worker consumes without RBAC get: `workspace-maas-credentials`, git credentials, `workspace-sonar-credentials`, `<run>-parity-db`, `<run>-parity-credentials`. Platform fixture source `migration-fixture-credentials` stays unmounted.

The MaaS automount does not require an API GET, but the existing group binding
still permits it. Validate effective permissions, not just the new Role.

## Precise claim

Restricting **new** migration workers does **not** revoke existing legacy
workspace accounts still bound to `devworkspace-default-role` (`workspace*-sa`
for v10, v9, `agentic-coolstore`, and any leftover generated SA DWO creates
beside a new worker). Those accounts keep namespace-wide Secret access until
their workspaces are deleted and DWO removes them from the default RoleBinding.
A PASS on a disposable new worker is not a PASS for v10.

## Land-time tests

```bash
python3 stages/080-ai-autonomous-migration/assert-worker-permissions.py
python3 stages/080-ai-autonomous-migration/assert-run-isolation.py
python3 stages/080-ai-autonomous-migration/provision-migration-run.test.py
python3 stages/080-ai-autonomous-migration/bind-pod-kubeconfig.test.py
```

These tests read manifests and execute the destfile kubeconfig fragment locally.
They do not claim workspace isolation.

## Disposable-workspace validation plan (after GitOps sync, before v11)

Use two **new** names, auto-start off. Do not reuse v10, do not launch
`spring-petclinic-rest-legacy-v11`, do not rerun the full 13-check isolation
packet until this focused plan PASSes.

Use fresh names such as `iso-worker-b` / `iso-worker-b-retry`. The September 23
`iso-worker-a` / `iso-worker-a-retry` trial was retired; do not reuse its
tombstones. Its standalone Job proved limited permissions but both directly
created DevWorkspaces failed postStart. It did **not** qualify IDE startup.

Stage 050 provides three running-workspace slots per user: preserved v10 plus
the two disposable workspaces. Confirm the live limit before opening them;
never stop v10 to make space. Start A alone first. Only start B after A has
completed the functional checks in step 7. Use the normal Developer Hub and
Dev Spaces creation flow, including its editor and operator configuration.

1. Sync Stage 050. Confirm `devworkspace-default-role` uid/resourceVersion are
   unchanged from the 2026-09-07 object, and v10's SA is still a subject of
   `devworkspace-default-rolebinding`.
2. Scaffold both repositories from the Application migration template with
   auto-start migration **off**. Wait until
   receipts are `provisioned` and `<run>-worker` SA/Role/RoleBinding exist
   **before** opening their Dev Spaces links. For the internal MaaS route,
   stop the newly created workspace through Dev Spaces, run the guarded
   `scripts/patch-workspace-maas-route.sh`, then start it. Never patch a running
   workspace during postStart. Initial no-agent IDE startup can use the public
   route; qualification and migration use the internal route.
3. Confirm each Running pod `spec.serviceAccountName` is `<run>-worker`, not
   `workspace*-sa`. Record that `workspace*-sa` still exists and is still a
   default-role subject.
4. From **inside** each tooling container, collect every kube credential:
   projected token, `~/.kube/config`, env `KUBECONFIG`, and any extra token
   file. Repeat the matrix below for **each** credential (`oc auth can-i
   --token` / curl with that bearer). Do not print token or Secret data.
5. Effective-permission matrix (expect **no** unless noted):

   | Check | Expect |
   |---|---|
   | get Secret `<other>-parity-db` / `petclinic-parity-postgres` | no |
   | list Secrets | no |
   | get/patch ConfigMap `migration-run-<own>` and `<own>-lock` | no |
   | get ConfigMap `devspace-ai-tools-init` | yes |
   | create/patch Role, RoleBinding, ServiceAccount | no |
   | patch DevWorkspace (own or other), including pod-overrides / DWOC attribute | no |
   | `create pods --subresource=exec` (own or other) | no |
   | create pods / PipelineRuns in `app-platform-build` | no |
   | get Secrets `workspace-maas-credentials` / `maas-devspace-api-keys` via API | yes (existing named group grant; no data output) |

6. Regain-via-configuration attempts from inside the worker (expect deny on
   live API; destfile git edits must not apply until a **user** recreates):

   - patch own DevWorkspace `pod-overrides` to drop `serviceAccountName` or
     point at `workspace*-sa`;
   - set `controller.devfile.io/devworkspace-config` to a DWOC with
     `disableCreation` + `serviceAccountName` of the generated SA;
   - bind `<run>-worker` to `devworkspace-default-rolebinding`;
   - create a new SA and RoleBinding to the default role.

   Recreate-from-destfile after stripping pod-overrides is a **user/platform**
   path, not a worker self-elevation. Record it if exercised; do not treat a
   user-applied destfile strip as this repair passing.

7. Functional still-works checks on one disposable workspace: IDE Ready,
   MaaS env present (`MAAS_API_KEY` / `MAAS_API_BASE_URL` names only), git and
   sonar mounts, `stamp-run-resources.py --verify`, `/projects/legacy` read-only,
   Operator hostAlias merge still contains `serviceAccountName`, reset, stop,
   start. After restart, `~/.kube/config` must be a replacement Config whose
   only user is `current-pod` with `tokenFile` of the projected SA token — not
   a merged leftover context. A failed bind must fail dest-init, not keep the
   previous file.

8. Retire both runs. Confirm labelled SA/Role/RoleBinding are gone; receipts
   are tombstones; v10 SA/bindings unchanged.

### Retained startup failure

The September 23 controller logged exit 137 as “Commands forcefully killed by
SIGKILL due to timeout”. The retained events place failure within seconds of
tooling start. That message alone does not establish timer expiry, OOM, or a
workspace quota eviction. Do not increase timeouts on this evidence alone.
Start a fresh disposable through Dev Spaces **Open in Debug mode**, which sets
the DevWorkspace metadata annotation; a devfile attribute is not that switch.
Before retry/retirement, retain the admitted pod lifecycle, container exit
status, `/tmp/poststart-{stdout,stderr}.txt`, DWO logs and timestamped events.
Capture safe metadata only; redact credentials from hook output. If startup
still fails, classify it using those artifacts before changing startup code.

Reference: [DWO v0.43 postStart wrapper](https://github.com/devfile/devworkspace-operator/blob/v0.43.0/pkg/library/lifecycle/poststart.go).

When this plan PASSes, requalify **all 13** isolation checks against the
resulting Stage 050 revision using `ISOLATION-DEMO.md` names
`iso-v11-final` / `iso-v11-final-retry`. Until then, do not launch v11.
