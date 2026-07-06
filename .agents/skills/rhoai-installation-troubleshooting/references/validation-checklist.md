# Validation Checklist

Use this checklist before approving installation troubleshooting guidance,
diagnostic notes, or live remediation plans.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Each symptom maps to an official error signal from the troubleshooting
  chapter.
- Local remediation is proposed only where the official chapter provides one.
- Support escalation is preserved where Red Hat says to contact support.
- Raw logs, must-gather archives, credentials, and kubeconfigs are not
  committed.

## Readonly Evidence Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get subscription,csv,installplan -n redhat-ods-operator
oc get pods -n redhat-ods-operator
oc get events -n redhat-ods-operator --sort-by=.lastTimestamp
oc get dsci,dsc -A
oc logs -n redhat-ods-operator -l name=rhods-operator --tail=200
```

If the install is GitOps-managed, also check the relevant ArgoCD Application:

```bash
oc get application -n openshift-gitops
oc describe application <rhoai-install-app> -n openshift-gitops
```

Check:

- Operator Subscription and CSV status are captured.
- Failing pod logs include the exact official error signal when possible.
- Event output is captured for image pull failures.
- DSCI/DSC existence and state are captured.
- GitOps sync or health failures are separated from product install failures.

## Support Case Evidence

Before recommending Red Hat Support, collect or request:

- failing symptom and exact error message
- OpenShift AI version and install channel
- OpenShift version and infrastructure platform
- relevant Operator pod logs
- Events from `redhat-ods-operator`
- DSC and DSCI YAML with secrets removed
- must-gather output according to Red Hat guidance

## Live Remediation Review

- Do not run destructive commands unless the user explicitly asks for live
  remediation.
- For reinstall failure, verify the Operator is uninstalled before deleting the
  leftover `Auth` custom resource.
- After any live fix, create or update the GitOps follow-up so the cluster and
  repo do not drift.
- If the official resolution is Red Hat Support, do not make up a local fix.

## Fail Conditions

- A local remediation is proposed for a support-escalation symptom without
  official backing.
- `Auth` is deleted without confirming reinstall context and user intent.
- Image pull failures are treated as a RHOAI manifest bug without event or
  registry/network evidence.
- Unsupported infrastructure is ignored or worked around.
- Raw must-gather archives or sensitive logs are committed.
