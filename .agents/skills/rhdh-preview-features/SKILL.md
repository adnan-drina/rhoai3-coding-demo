---
name: rhdh-preview-features
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when checking Red Hat Developer Hub Technology Preview, Developer Preview,
  or emerging and supplemental capabilities not yet fully covered in core
  documentation, including Argo CD notification integration with the RHDH
  Notifications plugin. Do NOT use for GA features, core configuration,
  installation, or product concepts (use rhdh-about, rhdh-release-notes).
---

# RHDH Preview Features

Use this skill to ground Red Hat Developer Hub preview and emerging capability
discussions in the official RHDH 1.10 supplemental documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Support Scope

### Technology Preview

Not fully supported under Red Hat Subscription Level Agreements. May not be
functionally complete. Not intended for production use. Red Hat will attempt to
resolve issues as the feature matures toward GA. See Technology Preview support
scope.

### Developer Preview

Not supported by Red Hat in any way. Not functionally complete or
production-ready. No SLA. Provides early access to functionality that may be
included in a future product offering. See Developer Preview support scope.

## Emerging Capabilities

### Argo CD Notifications Integration with RHDH

Configures Argo CD to send notifications directly to the RHDH Notifications
plugin when application sync events occur.

**Prerequisites:**
- `cluster-admin` permissions on OpenShift.
- Write access to RHDH source code or configuration.
- Argo CD installed with notifications controller enabled.
- Network connectivity from Argo CD namespace to RHDH endpoint.

**RHDH Configuration:**
1. Enable `backstage-plugin-notifications` (frontend) and
   `backstage-plugin-notifications-backend` (backend) dynamic plugins.
2. Configure a static external access token under
   `backend.auth.externalAccess` with type `static` and subject
   `argocd-notifications`.

**Argo CD Configuration:**
1. Enable the notifications controller (`spec.notifications.enabled: true`
   on the ArgoCD CR for OpenShift GitOps).
2. Create `argocd-notifications-secret` with the Backstage token.
3. Configure webhook service `service.webhook.backstage` pointing to
   `<BACKSTAGE_URL>/api/notifications/notifications`.
4. For OpenShift GitOps: use `NotificationsConfiguration` CR (the operator
   manages the ConfigMap directly). For standard Argo CD: edit
   `argocd-notifications-cm` ConfigMap directly.

**Trigger and Template Naming:**
Use custom names with `-backstage` suffix to avoid conflicts with default
templates. Example triggers:
- `on-sync-succeeded-backstage`
- `on-sync-failed-backstage`
- `on-health-degraded-backstage`
- `on-deployed-backstage`

**Application Annotations:**
Each Argo CD Application needs:
- `backstage.io/entity-ref: 'component:default/<name>'`
- `notifications.argoproj.io/subscribe.<trigger>.backstage: ''`

See `references/official-doc-extraction.md` for complete configuration
examples, troubleshooting, and security considerations.

## Workflow

1. Read `references/official-doc-extraction.md` for full details.
2. Identify whether the capability is Technology Preview, Developer Preview,
   or supplemental.
3. Do not treat preview features as production-ready.
4. Check `rhdh-release-notes` for the current support level of each feature.

## Related Skills

- `rhdh-about` — RHDH concepts, architecture, sizing, and deployment methods.
- `rhdh-release-notes` — RHDH 1.10 new features, fixes, known issues.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
