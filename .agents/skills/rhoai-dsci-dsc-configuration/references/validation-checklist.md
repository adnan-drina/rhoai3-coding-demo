# Validation Checklist

Use this checklist before finalizing DSCI or DSC GitOps content.

## Source And Schema

- Official sources use the active RHOAI baseline.
- CR fields are present in official docs or verified with `oc explain`.
- Component-specific behavior is delegated to the matching component skill.
- API support posture is checked with `rhoai-api-tiers` when the CR is used as
  a durable demo contract.

## Namespaces

- Predefined namespaces are used unless a custom namespace reason is recorded.
- Custom application namespaces include the required label before install.
- Workbench namespace is treated as install-time configuration.

## DSC Configuration

- Every component used by the demo has explicit `Managed` or `Removed` intent.
- Kueue, model registry, workbench, and pipeline fields are validated through
  component skills before use.
- GitOps examples do not include fields copied from old backups without source
  verification.

## Live Checks

Run only after the OpenShift safety guard in `AGENTS.md` passes:

```bash
oc explain datasciencecluster.spec
oc explain dscinitialization.spec
oc get datasciencecluster -n redhat-ods-operator
oc get dscinitialization -n redhat-ods-operator
oc get pods -n redhat-ods-applications
```
