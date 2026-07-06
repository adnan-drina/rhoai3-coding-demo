# Official Doc Extraction

Use this extraction to keep RHDH preview and emerging capability content
grounded in official Red Hat sources.

## Content Scope

This guide covers emerging, evolving, and supplemental capabilities in Red Hat
Developer Hub. Content may cover newly introduced features, features still
maturing, or supported functionality not yet fully documented in core
documentation. Individual features retain their respective support status.

## Argo CD Notifications Integration with RHDH

### Overview

Configures Argo CD to send notifications directly to the RHDH Notifications
plugin when application sync events occur. The flow is:

1. Argo CD application sync event triggers the notifications controller.
2. Controller sends webhook POST with auth token to Backstage endpoint.
3. Notification appears in the RHDH UI for the mapped entity.

### Prerequisites

- `cluster-admin` permissions on OpenShift Container Platform.
- Write access to RHDH source code or configuration.
- Argo CD installed with notifications controller enabled.
- Network connectivity from Argo CD namespace to RHDH endpoint.

### Part 1: Enable Notifications Plugin in RHDH

#### Step 1: Enable Dynamic Plugins

Add to `app-config.yaml` or custom RHDH ConfigMap:

```yaml
dynamicPlugins:
  frontend:
    backstage-plugin-notifications:
      enabled: true
  backend:
    backstage-plugin-notifications-backend:
      enabled: true
```

#### Step 2: Configure External Access Token

Configure a static token for Argo CD authentication:

```yaml
backend:
  auth:
    externalAccess:
      - type: static
        options:
          token: ${ARGOCD_NOTIFICATION_TOKEN}
          subject: argocd-notifications
```

Use a strong, randomly generated token stored securely.

### Part 2: Argo CD Configuration

#### Step 1: Enable Notifications Controller

For OpenShift GitOps:

```bash
oc patch argocd openshift-gitops -n openshift-gitops --type merge -p '
{
  "spec": {
    "notifications": {
      "enabled": true
    }
  }
}'
```

#### Step 2: Create Notifications Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: argocd-notifications-secret
  namespace: openshift-gitops
type: Opaque
stringData:
  backstage-token: '<token-matching-ARGOCD_NOTIFICATION_TOKEN>'
```

#### Step 3: Configure Webhook Service and Triggers

**For OpenShift GitOps** — use `NotificationsConfiguration` CR (the operator
manages `argocd-notifications-cm` and will overwrite direct edits):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: NotificationsConfiguration
metadata:
  name: default-notifications-configuration
  namespace: openshift-gitops
spec:
  context:
    argocdUrl: <ARGOCD_URL>
  services:
    service.webhook.backstage: |
      url: <BACKSTAGE_URL>/api/notifications/notifications
      headers:
      - name: Content-Type
        value: application/json
      - name: Authorization
        value: Bearer $backstage-token
  templates:
    template.app-sync-succeeded-backstage: |
      webhook:
        backstage:
          method: POST
          body: |
            {
              "recipients": {
                "type": "entity",
                "entityRef": "{{index .app.metadata.annotations \"backstage.io/entity-ref\"}}"
              },
              "payload": {
                "title": "{{.app.metadata.name}} - Sync Succeeded",
                "description": "Application synced successfully.",
                "link": "{{.context.argocdUrl}}/applications/{{.app.metadata.name}}",
                "severity": "low",
                "topic": "argocd.sync.succeeded"
              }
            }
    template.app-sync-failed-backstage: |
      webhook:
        backstage:
          method: POST
          body: |
            {
              "recipients": {
                "type": "entity",
                "entityRef": "{{index .app.metadata.annotations \"backstage.io/entity-ref\"}}"
              },
              "payload": {
                "title": "{{.app.metadata.name}} - Sync Failed",
                "severity": "high",
                "topic": "argocd.sync.failed"
              }
            }
    template.app-health-degraded-backstage: |
      webhook:
        backstage:
          method: POST
          body: |
            {
              "recipients": {
                "type": "entity",
                "entityRef": "{{index .app.metadata.annotations \"backstage.io/entity-ref\"}}"
              },
              "payload": {
                "title": "{{.app.metadata.name}} - Health Degraded",
                "severity": "high",
                "topic": "argocd.health.degraded"
              }
            }
    template.app-deployed-backstage: |
      webhook:
        backstage:
          method: POST
          body: |
            {
              "recipients": {
                "type": "entity",
                "entityRef": "{{index .app.metadata.annotations \"backstage.io/entity-ref\"}}"
              },
              "payload": {
                "title": "{{.app.metadata.name}} - Deployed",
                "severity": "low",
                "topic": "argocd.deployed"
              }
            }
  triggers:
    trigger.on-sync-succeeded-backstage: |
      - when: app.status.operationState.phase in ['Succeeded']
        send: [app-sync-succeeded-backstage]
    trigger.on-sync-failed-backstage: |
      - when: app.status.operationState.phase in ['Error', 'Failed']
        send: [app-sync-failed-backstage]
    trigger.on-health-degraded-backstage: |
      - when: app.status.health.status == 'Degraded'
        send: [app-health-degraded-backstage]
    trigger.on-deployed-backstage: |
      - when: app.status.operationState.phase in ['Succeeded'] and app.status.health.status == 'Healthy'
        send: [app-deployed-backstage]
```

**For standard Argo CD** — edit `argocd-notifications-cm` ConfigMap directly
with the same service, template, and trigger entries.

### Part 3: Enable Notifications for Applications

Add annotations to each Argo CD Application:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-application
  namespace: openshift-gitops
  annotations:
    backstage.io/entity-ref: 'component:default/my-application'
    notifications.argoproj.io/subscribe.on-sync-succeeded-backstage.backstage: ''
    notifications.argoproj.io/subscribe.on-sync-failed-backstage.backstage: ''
    notifications.argoproj.io/subscribe.on-health-degraded-backstage.backstage: ''
    notifications.argoproj.io/subscribe.on-deployed-backstage.backstage: ''
```

Subscription annotation format:
`notifications.argoproj.io/subscribe.<trigger-name>.<service-name>`

### Troubleshooting

**Notifications not appearing:**
- Verify controller is running: `kubectl get pods -n openshift-gitops | grep notification`
- Check controller logs: `kubectl logs -n openshift-gitops -l app.kubernetes.io/name=argocd-notifications-controller --tail=50`
- Verify webhook service config: `kubectl get configmap argocd-notifications-cm -n openshift-gitops -o jsonpath='{.data.service\.webhook\.backstage}'`
- Verify application annotations: `kubectl get application <name> -n openshift-gitops -o jsonpath='{.metadata.annotations}' | jq .`

**"notification service 'backstage' is not supported":**
- OpenShift GitOps: edited ConfigMap directly instead of NotificationsConfiguration CR.
- Missing `service.webhook.backstage` key.
- Solution: use NotificationsConfiguration CR for OpenShift GitOps.

**Webhook returns 400 Bad Request / "not valid JSON":**
- Template name conflicts with Argo CD defaults (which use email format).
- Solution: use custom template/trigger names with `-backstage` suffix.

**Link shows broken URL:**
- `{{.context.argocdUrl}}` template variable not configured.
- Solution: add context configuration with the Argo CD route URL.

**Authentication errors (401):**
- Restart notifications controller after secret changes:
  `kubectl rollout restart deployment -n openshift-gitops -l app.kubernetes.io/name=argocd-notifications-controller`

### Security Considerations

1. Use strong, randomly generated tokens with sufficient entropy.
2. Rotate tokens periodically (update both Argo CD secret and Backstage config).
3. Use HTTPS for Backstage in production.
4. Consider NetworkPolicies restricting which pods can reach Backstage.
