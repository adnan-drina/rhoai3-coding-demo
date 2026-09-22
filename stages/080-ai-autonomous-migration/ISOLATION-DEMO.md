# Isolation demo — the release condition for v10

The architect made a live two-workspace test the condition for starting v10
(review of 39792496, 2026-09-22). This procedure has not yet been qualified live. It executes the agreed validation; it introduces no human approval gate.

**Preconditions.** v9 is closed and its evidence archived; the golden is
published; stage 050 is synced (the RHDH template, the skeleton, the dispatcher
trigger, `provision-migration-run`, the provisioner RBAC and
`migration-fixture-credentials`); the shared pre-per-run stack is retired
(see docs/OPERATIONS.md, Stage 080 run isolation) and nothing in `wksp-ai-developer` still carries a
namespace-wide `mount-to-devworkspace` for parity.

**The two disposable runs.** Adversarially similar names, on purpose — this is
the collision the reviewed design lost to:

```
A = iso-demo-v10
B = iso-demo-v10-retry
```

Both are legal RHDH template names, and `B` starts with `A`. Use the same approved frozen legacy URL as v10, with autoStartMigration=false. No M3 migration workers run. Before the reset tests, materialize the decided schema/seed through the normal frozen-input bootstrap producers in both disposable workspaces and retain their receipts. Missing reset assets make the reset test INCONCLUSIVE; a printed reset plan is never a substitute.

From the repository root, establish the guard before any live command:

```bash
set -euo pipefail
source scripts/lib.sh
load_env
check_oc_logged_in
WS=wksp-ai-developer
BLD=app-platform-build
```

Use the full qualified platform/golden commits throughout.

**Recording.** Keep the output of every numbered step. Print credential key
names only; encoded Secret values are credentials too. Credential comparisons
hash the values in-process and emit only the digest.

---

## Step 0 — a clean start

```bash
oc get secret,deploy,svc,cm -n "$WS" -l rhoai3.io/purpose=stage-080-parity
oc get cm -n "$WS" -o name | grep '^configmap/migration-run-' || echo "no receipts"
```

**PASS** no previous run resources are listed, and no `migration-run-*`
receipt exists for `A` or `B`. The platform-owned `migration-fixture-credentials`
source Secret is expected: it has no workspace automount labels and is copied
by the provisioner into each run's targeted Secret. **FAIL** anything is left: retire it (§Step 9)
before starting, then choose new run names. A retired identity is not reused.

---

## Step 1 — scaffold A, and hold B back (delayed provisioning)

Scaffold **A only** from the app-migration template. Then, *before* opening any
workspace:

```bash
oc get pipelinerun -n "$BLD" -l rhoai3.redhat.com/migration-run=iso-demo-v10
oc get cm migration-run-iso-demo-v10 -n "$WS" -o jsonpath='{.data.phase}{"\n"}'
oc get deploy iso-demo-v10-parity-postgres -n "$WS"
```

**PASS** exactly one PipelineRun, Succeeded; `phase` is `provisioned`; the
Deployment exists and becomes Available. **FAIL** more than one PipelineRun for
one scaffolding push, or no receipt: provisioning is not bound to the
scaffolding event.

**Delayed provisioning.** Open A's workspace *while the database Deployment is
still progressing* (or scale it to 0 first: `oc scale deploy
iso-demo-v10-parity-postgres -n "$WS" --replicas=0`, open the workspace, then
scale back to 1). In the workspace:

```bash
cat /projects/modernized/.hermes/RUN-RESOURCES-STATUS
```

**PASS** ownership may be OK while the assigned database is starting; ownership
is not readiness. Resource-dependent gates must refuse or block until the
server is ready. Auto-start is disabled for these disposable runs. Also test
missing secrets by invoking the gate in an isolated process with the datasource
variables removed: RUN_RESOURCES_MISSING must block reset/startup/parity before
connecting. Static analysis may continue. Never interpret an ownership status
as a successful database connection.

Restore the replica count before continuing.

---

## Step 2 — scaffold B, and check the targeting did not overlap

Scaffold **B**. Then, without opening its workspace:

```bash
for r in iso-demo-v10 iso-demo-v10-retry; do
  for s in "$r-parity-db" "$r-parity-credentials"; do
    echo "== $s"
    oc get secret "$s" -n "$WS" \
      -o jsonpath='include={.metadata.annotations.controller\.devfile\.io/mount-to-devworkspace-include}{"\n"}watch={.metadata.labels.controller\.devfile\.io/watch-secret}{"\n"}mount={.metadata.labels.controller\.devfile\.io/mount-to-devworkspace}{"\n"}onstart={.metadata.annotations.controller\.devfile\.io/mount-on-start}{"\n"}'
    oc get secret "$s" -n "$WS" \
      -o go-template='keys={{range $k,$v := .data}}{{$k}} {{end}}{{"\n"}}'
  done
done
```

**PASS** for each secret: `include` is the run's own name with **no** comma and
**no** `*`; `watch=true`; `mount=true`; `onstart=true`. **FAIL** any include
contains `iso-demo-v10,iso-demo-v10-*` or any wildcard — that is defect 2, and
B would receive A's database.

```bash
oc get secret -n "$WS" -l controller.devfile.io/mount-to-devworkspace=true \
  -o custom-columns=NAME:.metadata.name,INCLUDE:'.metadata.annotations.controller\.devfile\.io/mount-to-devworkspace-include'
```

**PASS** every parity database or fixture Secret has a non-empty, exact include.
**FAIL** any such Secret has none: it mounts into every workspace. Other shared
platform Secrets must be accounted for separately; they are not run credentials.

---

## Step 3 — the workspaces receive only their own

**First, confirm the workspace NAME.** Exact binding means the DevWorkspace's
own name must equal the run name; a factory URL that derives or suffixes it
would leave a workspace with no secrets at all (which fails closed, but as a
`RUN_RESOURCES_MISSING`, not as a wrong database). This is the most likely
surprise on a first exact-bound run, so measure it before anything else:

```bash
oc get devworkspace -n "$WS" -o custom-columns=NAME:.metadata.name,PHASE:.status.phase
```

**PASS** the two DevWorkspaces are named exactly `iso-demo-v10` and
`iso-demo-v10-retry`. **FAIL** either carries a suffix or a derived name:
record the actual name — the include annotation must be made to bind *that*
name, still exactly, and the provisioner takes the name from the same template
value, so a mismatch is a template defect, not a reason to widen the pattern.

Open B's workspace. In **each** workspace:

```bash
env | grep -c '^PETCLINIC_DB_URL='            # expect 1
python3 - <<'PY'
import os
url = os.environ.get("PETCLINIC_DB_URL", "")
# host only: never print the whole URL, and never the password
print("host:", url.split("//",1)[-1].split("/",1)[0].split(":")[0] if url else "(absent)")
print("receipt run:", dict(p.split("=",1) for p in os.environ.get("PARITY_RUN_RECEIPT","").split(";") if "=" in p).get("run","(absent)"))
print("workspace:", os.environ.get("DEVWORKSPACE_NAME","(absent)"))
PY
cat /projects/modernized/.hermes/RUN-RESOURCES-STATUS
```

**PASS** in A the host is `iso-demo-v10-parity-postgres...`, the receipt run is
`iso-demo-v10`, the workspace is `iso-demo-v10`, and the status is `result=ok`.
In B all three say `iso-demo-v10-retry`. **FAIL** B's host or receipt names A —
that is the collision — or `PETCLINIC_DB_URL` appears more than once (two
sources for one name).

Fixture identities, by presence only:

```bash
env | grep -c '^PETCLINIC_ADMIN_CREDENTIAL=\|^PETCLINIC_INVALID_CREDENTIAL='  # expect 2
```

**PASS** 2 in each workspace. **FAIL** 0 — the fixture secret was not delivered
(check `watch-secret` on `<run>-parity-credentials`).

---

## Step 4 — cross-run reset attempts are refused BEFORE connecting

In **B's** workspace, point the reset at **A's** database and try each
destructive mode:

```bash
cd /projects/modernized
A_URL="jdbc:postgresql://iso-demo-v10-parity-postgres.wksp-ai-developer.svc:5432/parity"
for mode in "" "--variant identity-disabled" "--revert-variant identity-disabled"; do
  rc=0
  PETCLINIC_DB_URL="$A_URL" \
    bash .hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root . $mode || rc=$?
  echo "rc=$rc"
  test "$rc" -ne 0
done
```

**PASS** every invocation exits non-zero, prints `RUN_RESOURCES_MISMATCH`, and
the message says the refusal happened before connecting. **FAIL** any of them
reaches a JDBC driver, a `javac`, or the `ResetDb` runner.

Now the other counterexamples, each of which passed the reviewed check:

```bash
for U in \
  "jdbc:postgresql://iso-demo-v10-retry-parity-postgres.other-ns.svc:5432/parity" \
  "jdbc:postgresql://iso-demo-v10-retry-parity-postgres.wksp-ai-developer.svc:5432/somebody-else" \
  "jdbc:postgresql://iso-demo-v10-retry-parity-postgres-old.wksp-ai-developer.svc:5432/parity" \
  "jdbc:postgresql://elsewhere.wksp-ai-developer.svc:5432/parity?ApplicationName=iso-demo-v10-retry-parity-postgres" ; do
  PETCLINIC_DB_URL="$U" python3 -c "
import sys; sys.path.insert(0,'.hermes/lib')
from pathlib import Path; from planner import run_identity as r
v = r.check(Path('.')); print(v.code)"
done
```

**PASS** four lines, each `RUN_RESOURCES_MISMATCH`. **FAIL** any `OK`.

And the unstamped case:

```bash
cp migration.yaml /tmp/migration.yaml.bak
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("migration.yaml"); t = p.read_text()
p.write_text(re.sub(r"(?ms)^resources:\n(?:[ \t].*\n|\n)*", "", t))
PY
rc=0
bash .hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root . || rc=$?
cp /tmp/migration.yaml.bak migration.yaml
echo "rc=$rc"
test "$rc" -ne 0
```

**PASS** non-zero, `RUN_RESOURCES_UNASSIGNED`, including after the destination has already been stamped. **FAIL** it resets anything.

---

## Step 5 — resetting, restarting and retiring A leaves B untouched

Set `A_POD` and `B_POD` to the tooling pods identified by the actual workspace
labels. Record B's database and workspace identity before touching A:

```bash
oc get pod -n "$WS" -l app=iso-demo-v10-retry-parity-postgres \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,START:.status.startTime
oc get pod "$B_POD" -n "$WS" \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,START:.status.startTime
```

Seed a distinctive marker in **B's reset-owned public schema** after its initial
verified reset. An accidental reset of B must remove this marker, so placing it
in a separate schema would invalidate the test. Use the assigned database pod from B's provisioning receipt; these
commands are for disposable isolation runs only.

```bash
B_DB_POD=$(oc get pod -n "$WS" -l app=iso-demo-v10-retry-parity-postgres -o jsonpath='{.items[0].metadata.name}')
oc exec -i -n "$WS" "$B_DB_POD" -- bash -c '
  export PGPASSWORD="$POSTGRESQL_PASSWORD"
  psql -h 127.0.0.1 -U "$POSTGRESQL_USER" -d "$POSTGRESQL_DATABASE" -v ON_ERROR_STOP=1
' <<'SQL'
CREATE TABLE public.isolation_probe_marker (value text NOT NULL);
INSERT INTO public.isolation_probe_marker VALUES ('B-must-survive-A');
SQL
# Include rows and sequence state; strip only pg_dump's random restore-session
# guard, if present. Those two directives are not database content.
b_data_digest() {
  oc exec -n "$WS" "$B_DB_POD" -- bash -c '
    export PGPASSWORD="$POSTGRESQL_PASSWORD"
    pg_dump -h 127.0.0.1 -U "$POSTGRESQL_USER" -d "$POSTGRESQL_DATABASE" \
      --no-owner --no-privileges --data-only
  ' | sed '/^\\restrict /d; /^\\unrestrict /d' | shasum -a 256 | awk '{print $1}'
}
B_BEFORE=$(b_data_digest)
# Hash in-process; do not emit .data or encoded values.
b_credentials_digest() {
  oc get secret iso-demo-v10-retry-parity-db iso-demo-v10-retry-parity-credentials \
    -n "$WS" -o json | python3 -c 'import json,sys,hashlib; d=json.load(sys.stdin); rows=sorted((x["metadata"]["name"],x["data"]) for x in d["items"]); print(hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())'
}
B_CREDENTIALS_BEFORE=$(b_credentials_digest)
```

Now, in **A's** workspace, reset A; then restart A's database:

```bash
# in A
bash .hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root .
# from a terminal with cluster access
oc delete pod -n "$WS" -l app=iso-demo-v10-parity-postgres
```

Re-check B:

```bash
oc get pod -n "$WS" -l app=iso-demo-v10-retry-parity-postgres \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,START:.status.startTime
oc get pod "$B_POD" -n "$WS" \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,START:.status.startTime
# Read B without resetting it. Repeat after A's retirement in step 8.
test "$(b_data_digest)" = "$B_BEFORE"
test "$(b_credentials_digest)" = "$B_CREDENTIALS_BEFORE"
```

**PASS** B's data and credential digests match and both its database and workspace pod UIDs/start times are unchanged. **FAIL** B's pod restarted, or B's workspace restarted:
nothing A does may reach B.

*(A database pod loss makes the affected measurements inconclusive and requires
a fresh verified reset — never stale acceptance. That is ADR-022, and it
applies to A here.)*

---

## Step 6 — editing the destination repository changes nothing

In **A's** repository, commit and push a `k8s-run/` directory containing a
Secret that claims B's name and a Job that mounts every secret in the
namespace. Wait two minutes.

```bash
oc get pipelinerun -n "$BLD" -l rhoai3.redhat.com/migration-run=iso-demo-v10
oc get application -n openshift-gitops | grep -i 'iso-demo' || echo "no Application"
oc get job,secret -n "$WS" -l rhoai3.io/migration-run=iso-demo-v10-retry \
  -o custom-columns=KIND:.kind,NAME:.metadata.name,CREATED:.metadata.creationTimestamp
```

**PASS** still exactly one PipelineRun for A (the scaffolding one); **no**
Argo CD Application over either repository; no new object under B's label; and
nothing named in A's pushed manifests exists in the cluster. **FAIL** anything
from the pushed directory reached `$WS`, or a second provisioning PipelineRun
appeared.

Also inspect the actual workspace principal (substitute A's tooling pod):

```bash
oc get sa migration-run-provisioner -n "$WS" --ignore-not-found -o name
oc get sa migration-run-provisioner -n "$BLD" -o name
WORKER_SA=$(oc get pod "$A_POD" -n "$WS" -o jsonpath='{.spec.serviceAccountName}')
oc auth can-i get secrets -n "$WS" --as="system:serviceaccount:$WS:$WORKER_SA" || true
oc auth can-i create pods -n "$WS" --as="system:serviceaccount:$WS:$WORKER_SA" || true
oc auth can-i create pipelineruns.tekton.dev -n "$BLD" --as="system:serviceaccount:$WS:$WORKER_SA" || true
```

The provisioner must exist only in the build namespace. Record actual worker
permissions and separately inspect any user token available inside the workspace.
An ability to create workloads or use a privileged user token limits the security
claim even when the repository webhook path is safe. Never generalize the default
service account's permissions to the worker.

---

## Step 7 — duplicate and reordered events cannot re-provision

Replay A's scaffolding webhook (GitHub → the repository's webhook deliveries →
Redeliver), then push an ordinary commit to A's `main`.

```bash
oc get pipelinerun -n "$BLD" -l rhoai3.redhat.com/migration-run=iso-demo-v10 \
  -o custom-columns=NAME:.metadata.name,STATUS:.status.conditions[0].reason
oc get cm migration-run-iso-demo-v10 -n "$WS" \
  -o jsonpath='{.data.phase} {.data.scaffoldCommit} {.data.provisionedAt}{"\n"}'
```

**PASS** an ordinary push starts **no** provisioning PipelineRun (the filter
requires branch creation); a redelivered scaffolding event either starts
nothing or starts a run that reports `reprovisioned` and changes neither
`scaffoldCommit` nor the generated password (A's workspace keeps working).
**FAIL** `provisionedAt` moves with a new `scaffoldCommit`, or A's workspace
loses its database.

---

## Step 8 — retire A, and account for everything

Archive A's evidence first. Then:

```bash
oc create -n "$BLD" -f - <<'EOF'
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: retire-iso-demo-v10-
spec:
  pipelineRef:
    name: provision-migration-run
  taskRunTemplate:
    serviceAccountName: migration-run-provisioner
  params:
    - name: run-name
      value: iso-demo-v10
    - name: scaffold-commit
      value: retire
    - name: mode
      value: retire
EOF
```

Then:

```bash
oc get secret,deploy,svc -n "$WS" -l rhoai3.io/migration-run=iso-demo-v10 -o name
oc get cm migration-run-iso-demo-v10 -n "$WS" -o jsonpath='{.data.phase}{"\n"}'
oc get secret -n "$WS" | grep '^iso-demo-v10-' | grep -v retry || echo "none left"
```

**PASS** the PipelineRun succeeds; **nothing** is listed under A's label — no
generated secret, Deployment or Service; the receipt says `retired`. **FAIL**
any generated secret survives: that is defect 5, and it is exactly what the
reviewed design left behind.

Confirm B is still whole:

```bash
oc get deploy,svc,secret -n "$WS" -l rhoai3.io/migration-run=iso-demo-v10-retry -o name
# in B's workspace
cat /projects/modernized/.hermes/RUN-RESOURCES-STATUS
```

**PASS** B's five objects are present and B's status still says `result=ok`.

**Resurrection.** Push another commit to A's `main`, and redeliver A's original
scaffolding webhook.

```bash
oc get pipelinerun -n "$BLD" -l rhoai3.redhat.com/migration-run=iso-demo-v10
oc get secret -n "$WS" -l rhoai3.io/migration-run=iso-demo-v10 -o name
```

**PASS** no new object exists for A. If a PipelineRun was started at all, it
**failed** with `REFUSED: iso-demo-v10 was retired`. **FAIL** any of A's
resources comes back.

---

## Step 9 — cleanup preserves retirement

Retire B through the same platform Pipeline after saving the final B comparisons.
Stop and remove the two disposable workspaces through their normal lifecycle.
Preserve both tombstone ConfigMaps and the evidence packet. Never delete a
receipt to reuse a retired identity; use new names for a later demonstration.

## The exits this demo measures

| Exit (ADR-022 / ADR-023 / governance) | Proved by |
|---|---|
| Two concurrent runs receive different servers and different secrets | Steps 2, 3 |
| A missing or mismatched binding blocks the relevant captures | Steps 1, 3, 4 |
| Wrong-target operations refuse **before** connecting | Step 4 |
| Resetting, restarting or retiring one run leaves the other's data and workspace unchanged | Steps 5, 8 |
| Each workspace receives only its assigned fixture Secret | Steps 2, 3 |
| Repository edits cannot alter another run's resources | Step 6 |
| Workspace identities cannot read another run's credentials or invoke the privileged provisioner | Step 6 |
| Duplicate or reordered events cannot alter a run | Step 7 |
| Retirement accounts for every generated resource | Step 8 |
| Post-retirement pushes cannot resurrect a run | Step 8 |

Any FAIL is a v10 blocker. Record the step, the exact output and the finding;
do not work around it in the cluster.


## Additional mandatory checks from the second review

- The new `run_identity.test.py` and `provision-migration-run.test.py` must pass
  on the release tree. The latter executes the actual shipped shell against a
  concurrent API fixture; it is supporting evidence, not the live result.
- Re-deliver two provisioning events concurrently for A. Both may eventually
  succeed under the lock, or a bounded waiter may report RUN_RESOURCES_BUSY.
  Passwords must not rotate. Then overlap provisioning with retirement on a
  disposable run: final state is retired, all generated resources are absent,
  and subsequent provisioning refuses. Preserve event/TaskRun timestamps.
- Inspect `migration-run-<run>-lock` on a busy outcome. It names the holder
  TaskRun. Never remove it while the holder can still write. A crash can leave
  the lock: establish terminal TaskRun/pod state before platform recovery. There
  is no timed lock expiry that admits two simultaneous writers. A `retiring`
  receipt is durable intent and refuses provisioning even after lock recovery.
- Repeat B's data/credential/pod comparison **after A's retirement**, without
  resetting B. An unchanged plan is insufficient. Retain the marker result and
  logical dump digest, not database rows or credential bytes.
- Change receipt port, workspace, engine and scaffold independently in an
  isolated workspace process. Each must refuse before connecting. Clear
  DEVWORKSPACE_NAME or give another workspace's name: refuse. Remove the
  resource declaration after stamping: refuse even without receipt variables.
- Inspect the actual workspace service account and any user identity exposed
  to workers. Record their ability to read secrets, create workloads and create
  provisioning PipelineRuns; testing the `default` service account alone says
  nothing about the active worker. Do not call this a tenant security boundary.
- Resolve image references from the Task and compare the receipt and running
  pods. Floating tags fail qualification. The exact workspace name must equal
  its assignment and the operator-provided DEVWORKSPACE_NAME.
- Preserve tombstones. Do not reuse retired run identities. Cleanup must never
  delete receipt ConfigMaps to make re-delivery succeed.

## Evidence packet consumed by v10-preflight.sh

Retain timestamped command results, TaskRuns, non-secret resource metadata and
before/after digests. The receipt summarizes these measured results; it is not
an approval or a substitute for executing a check. Never write PASS for an
unexecuted check. Store `isolation-receipt.json` beside its evidence, with:

- `schema`: `rhoai3.run-isolation/v1`;
- `platform_commit`, `golden_commit`: full qualified commits;
- `images.databaseImage`, `images.provisionerImage`: the exact Task digests;
- `checks`: each named check below with PASS, FAIL or INCONCLUSIVE;
- `evidence`: nonempty rows `{path, sha256}` for the retained evidence files.

Required check names: `secret_binding`, `wrong_targets`, `assignment_removal`,
`receipt_fields`, `delayed_resources`, `data_independence`,
`credential_independence`, `workspace_independence`, `repository_non_authority`,
`duplicate_delivery`, `overlapping_retirement`, `retirement`, `workspace_identity`.
The preflight refuses missing results, anything other than PASS, different
release/image pins, or changed/missing evidence. No signature field is used.
