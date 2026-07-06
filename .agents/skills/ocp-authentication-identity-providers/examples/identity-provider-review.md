# Identity Provider Review Pattern

Use this pattern when reviewing planned authentication changes:

1. Confirm the target source is OCP authentication and authorization
   documentation for the active baseline.
2. Identify whether the cluster uses the built-in OAuth server or direct
   external OIDC.
3. List current providers from `oc get oauth cluster -o yaml`.
4. Verify all referenced secrets and config maps exist in `openshift-config`.
5. Confirm at least one long-lived cluster-admin recovery method exists before
   proposing disruptive auth changes.
6. Hand off RHOAI dashboard group selection to the RHOAI access skills.
