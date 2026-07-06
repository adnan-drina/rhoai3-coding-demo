# Validation Checklist

Use this checklist before approving an uninstall plan, decommission runbook, or
live uninstall.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Uninstall is clearly distinguished from shutdown or GPU scale-down.
- The official CLI procedure is used as the product uninstall source.
- The plan lists removed resources and retained resources separately.
- User-created resources are not deleted without explicit approval.
- PVC data backup is confirmed before uninstall.

## Pre-Uninstall Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc whoami
oc get application -n openshift-gitops
oc get subscription,csv,installplan -n redhat-ods-operator
oc get dsci,dsc -A
oc get ns | rg "redhat-ods|rhods"
oc get pvc -A | rg "redhat-ods|rhods|datascience|pipeline|model|workbench"
```

Check:

- target cluster has been confirmed by the user
- ArgoCD Applications that manage RHOAI resources are suspended, removed, or
  retargeted before uninstall
- PVC backup requirement is addressed
- user-created projects and CRs are listed before removal begins

## Official Uninstall Review

Live uninstall commands are destructive. Use
`examples/official-cli-uninstall-sequence.md` only after explicit approval.

Check:

- deletion ConfigMap is created in `redhat-ods-operator`
- `api.openshift.com/addon-managed-odh-delete=true` label is applied
- `redhat-ods-applications` deletion is observed before deleting
  `redhat-ods-operator`
- `redhat-ods-operator` namespace deletion is intentional and approved

## Post-Uninstall Verification

Run only after following the OpenShift safety guard:

```bash
oc get subscriptions --all-namespaces | rg rhods-operator || true
oc get namespaces | rg "redhat-ods|rhods" || true
oc get dsci,dsc -A || true
```

Check:

- `rhods-operator` Subscription is absent
- `redhat-ods-applications`, `redhat-ods-monitoring`,
  `redhat-ods-operator`, and relevant `rhods-notebooks` namespaces are absent
- retained user projects and CRs are reviewed and either preserved, exported,
  or deleted with explicit approval
- follow-up GitOps state matches the post-uninstall cluster state

## Fail Conditions

- Uninstall commands are run when the user asked only for shutdown or cost
  reduction.
- ArgoCD remains actively syncing RHOAI install resources during uninstall.
- PVC backup is skipped.
- Retained user resources are bulk-deleted without approval.
- Uninstall output, backups, kubeconfigs, or tokens are committed.
