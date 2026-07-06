# Validation Checklist

Use this checklist when reviewing OpenShift web console guidance, Console
Operator manifests, console customizations, dynamic plugins, web terminal
configuration, or quick start content.

## Source And Baseline

- The OpenShift baseline is read from `docs/PLATFORM_BASELINE.md`.
- The Web console source URL points to the matching OCP documentation version.
- API versions, fields, labels, route names, and plugin schemas are verified
  against official docs, `oc explain`, CRDs, or the active cluster.
- RHOAI dashboard behavior is reviewed with `rhoai-dashboard-*` skills.
- Authentication and user/group assumptions are reviewed with OCP
  authentication guidance.

## Manifest Review

- `console.config.openshift.io/cluster` and
  `consoles.operator.openshift.io/cluster` are not confused.
- `ConsoleLink`, `ConsolePlugin`, `ConsoleQuickStart`, `ConfigMap`, `Secret`,
  route, and ingress customizations use verified API groups and field shapes.
- Console branding assets are stored in the documented namespace and respect
  documented size and format limits.
- Route and TLS customizations reference existing or planned secrets and
  hostnames.
- Dynamic plugin assets, service proxy settings, token forwarding, and CSP
  directives are explicitly reviewed.
- Web Terminal Operator and DevWorkspace dependency behavior are documented.
- Quick start content uses the official quick start structure and does not
  duplicate long-form demo documentation.
- Disabling the console is not proposed unless explicitly requested.

## Live Read-Only Checks

Run these only after the live-cluster guard is satisfied:

```bash
oc whoami --show-console
oc get co console
oc get console.config.openshift.io cluster -o yaml
oc get consoles.operator.openshift.io cluster -o yaml
oc get pods -n openshift-console
oc get route -n openshift-console
oc get consolelinks.console.openshift.io
oc get consoleplugins.console.openshift.io
oc get consolequickstarts.console.openshift.io
```

For web terminal review:

```bash
oc get subscription -A | grep -i web-terminal
oc get subscription -A | grep -i devworkspace
oc get pods -n openshift-operators
oc get devworkspaces -A
```

## Live Operation Review

- The repo environment guard is satisfied before live commands.
- Console customization, plugin enablement, web terminal installation, route
  customization, and disabling the console have explicit user approval.
- Any GitOps-managed console resource has an owner and rollback note.
- Console changes are validated in a browser and with cluster operator status.
- Dynamic plugins are tested with and without the plugin enabled.
- Web terminal network-policy requirements are reviewed before debugging
  startup failures.
- DevWorkspace cleanup does not remove resources needed by other Operators.

## Fail Conditions

Stop and correct the work if any of these are true:

- A console CR field or API group is invented or copied from a different OCP
  version without verification.
- OpenShift web console customization is used to describe RHOAI dashboard
  behavior.
- A dynamic plugin forwards user tokens without explicit authorization review.
- A custom route or download route references an unverified TLS secret.
- A quick start is proposed as the only documentation for a demo capability.
- The web terminal is removed without checking DevWorkspace dependencies.
- The console is disabled without explicit user approval.
