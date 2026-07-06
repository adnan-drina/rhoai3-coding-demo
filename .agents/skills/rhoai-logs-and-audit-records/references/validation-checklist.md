# Validation Checklist

Use this checklist before approving RHOAI Operator logger or audit-record
changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Source capture points to the Administer Chapter 13 URL, not the older install
  chapter path.
- Logger configuration is limited to `DSCI.spec.devFlags.logmode`.
- Development logging is documented as temporary unless an explicit persistent
  reason exists.
- Audit examples target DSC and DSCI changes only.
- Raw audit logs are not committed unless sanitized and approved.

## Logger Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc explain dscinitialization.spec.devFlags
oc get dsci default-dsci -o yaml
oc get pods -l name=rhods-operator -n redhat-ods-operator
```

Check:

- `logmode` is unset, empty, `prod`, or `production` for normal operation.
- `logmode` is `devel` or `development` only for explicit temporary debugging.
- Any persistent GitOps setting matches the README or operations notes.
- Operator pods exist in `redhat-ods-operator` before log streaming commands
  are used.

## Audit Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc auth can-i get nodes/log --all-namespaces
oc adm node-logs --role=master --path=kube-apiserver/
```

Check:

- cluster-admin access is available
- audit log availability is confirmed for the active cluster type
- full request-body review is attempted only when audit policy captures request
  bodies
- filters exclude read-only verbs and the OpenShift AI Operator service account
  when looking for user-driven configuration changes
- any saved audit output is written to local temporary storage, not committed
  repo paths

## Fail Conditions

- A GitOps change sets `development` logging without documenting why it is
  persistent.
- A live `oc patch dsci` command is run without the OpenShift safety guard.
- Audit review claims full changed-resource content without a
  `WriteRequestBodies` or broader audit policy.
- Raw audit logs containing user, token, URL, or object payload details are
  committed.
- General model, pipeline, notebook, or application logs are documented as if
  this Operator-focused chapter covered them.
