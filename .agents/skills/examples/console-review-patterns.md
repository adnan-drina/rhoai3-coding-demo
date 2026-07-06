# Console Review Patterns

## Console Access Review

```text
Task: Verify OpenShift web console access
Source: OCP Web console guide
Checks:
- console URL discovered with oc whoami --show-console
- browser support confirmed
- user identity provider and permissions understood
- console cluster operator healthy
- web console route reachable
Decision: pass, document issue, or escalate to authentication/route review
```

## Console Configuration Shape

Use this only as a review shape. Verify the exact field and API behavior before
authoring GitOps resources.

```yaml
apiVersion: config.openshift.io/v1
kind: Console
metadata:
  name: cluster
spec:
  authentication:
    logoutRedirect: <verified-url-or-empty-string>
```

## Console Operator Customization Shape

Use this only as a review shape. `consoles.operator.openshift.io/cluster` is
the operator resource, not the same resource as
`console.config.openshift.io/cluster`.

```yaml
apiVersion: operator.openshift.io/v1
kind: Console
metadata:
  name: cluster
spec:
  customization:
    customProductName: <verified-product-name>
```

## ConsoleLink Shape

```yaml
apiVersion: console.openshift.io/v1
kind: ConsoleLink
metadata:
  name: <link-name>
spec:
  href: <verified-url>
  location: HelpMenu
  text: <link-text>
```

## ConsolePlugin Review Shape

```yaml
apiVersion: console.openshift.io/v1
kind: ConsolePlugin
metadata:
  name: <plugin-name>
spec:
  backend:
    service:
      name: <service-name>
      namespace: <service-namespace>
      port: <service-port>
    type: Service
```

Review the active docs and cluster schema before using proxy, authorization, or
Content Security Policy fields.

## Web Terminal Review Note

```text
Before installing or using the web terminal:
- confirm the Web Terminal Operator source and channel
- if using a manual Subscription, name it web-terminal
- record that DevWorkspace Operator is installed as a dependency
- verify terminal namespaces allow ingress from openshift-console and
  openshift-operators when network policies exist
- do not remove DevWorkspace Operator unless no other Operator depends on it
```

## Quick Start Content Note

```text
Quick starts are guided UI tutorials with tasks, steps, and check-your-work
modules. Use them for short operational guidance only. Keep demo concepts,
architecture, and narrative flow in README and presentation content.
```
