# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product | Red Hat OpenShift Container Platform |
| Version | Repository baseline in `docs/PLATFORM_BASELINE.md` |
| Documentation category | Web console |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/web_console/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/web_console/index |
| Retrieved | 2026-06-10 |

## Sections Captured

- Web Console Overview
- Accessing the web console
- Using the OpenShift Container Platform dashboard to get cluster information
- Adding user preferences
- Configuring the web console in OpenShift Container Platform
- Customizing the web console in OpenShift Container Platform
- Dynamic plugins
- Web terminal
- Disabling the web console in OpenShift Container Platform
- Creating quick start tutorials in the web console
- Optional capabilities and products in the web console

## Related Official Sources

- OCP 4.20 documentation landing page:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/
- OCP 4.20 CLI tools:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/index
- OCP 4.20 Authentication and authorization:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index
- OCP 4.20 Routes and ingress guidance:
  https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking/index

## Source Boundaries

- This skill is about the OpenShift Container Platform web console, Console
  Operator resources, console customization, dynamic plugins, web terminal, and
  quick starts.
- It is not product authority for the Red Hat OpenShift AI dashboard; use
  `rhoai-dashboard-*` skills.
- It is not product authority for generic OAuth and identity provider behavior;
  use a future `ocp-authentication-identity-providers` skill.
- It is not product authority for general Routes, Ingress, or TLS behavior
  outside console component routes.
- If a console field, plugin extension, or quick start schema is not clear in
  the official docs, verify with `oc explain`, CRD inspection, or the active
  cluster before authoring GitOps resources.
