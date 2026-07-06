# Official Doc Extraction

Use this extraction to keep OpenShift Lightspeed release information grounded in
the official Red Hat OpenShift Lightspeed 1.0 release notes. All version
numbers, feature names, CVEs, issue IDs, and behavioral changes are taken
directly from the official documentation.

## FIPS Compliance

Red Hat OpenShift Lightspeed is designed for Federal Information Processing
Standards (FIPS). When running on OpenShift Container Platform in FIPS mode, it
uses the Red Hat Enterprise Linux cryptographic libraries submitted (or planned
to be submitted) to NIST for FIPS validation on only the `x86_64`, `ppc64le`,
and `s390X` architectures.

## Release Notes for 1.1.1

Red Hat OpenShift Lightspeed 1.1.1 addresses security vulnerabilities, fixes
software bugs, and improves stability. This release helps ensure continued
support and stability for clusters running OpenShift Container Platform 4.16 and
later.

### Fixed Security Issues

Security issues fixed in 1.1.1 (viewable at Red Hat Security Updates):

- CVE-2026-48710
- CVE-2026-44432

## Release Notes for 1.1

Red Hat OpenShift Lightspeed 1.1 provides maintenance updates, security fixes,
and feature enhancements. This release helps ensure continued support and
stability for clusters running OpenShift Container Platform 4.16 and later.

### Enhancements

Red Hat OpenShift Lightspeed 1.1 introduces security enhancements for secret
handling, updated component management, and support for modern AI software
development kits.

- **Rich text clipboard copy** — previously, copying a response from OpenShift
  Lightspeed only included raw markdown text. Now copying preserves formatting
  when pasted into applications that support rich text, such as Google Docs.

- **Kubernetes MCP server enabled by default** — the `introspectionEnabled`
  field in the `OLSConfig` custom resource (CR) is `true` by default. You do
  not have to specify this field to use the Kubernetes Model Context Protocol
  (MCP) server. To disable the Kubernetes MCP server, set this field to
  `false`.

- **Kubernetes MCP server read/write with human-in-the-loop** — the Kubernetes
  MCP server supports both read and write operations. Because human-in-the-loop
  (HITL) support is enabled by default, you must approve any non-read operation
  (such as update or delete) in the user interface before OpenShift Lightspeed
  executes the action. This behavior is controlled by the
  `toolsApprovalConfig.approvalType` field in the `OLSConfig` CR, which
  defaults to `tool_annotations`.

- **Expandable code blocks** — you can expand code blocks to view more content
  and collapse them to return to their original size.

- **Strong TLS cipher enforcement** — OpenShift Lightspeed supports only the
  strong ciphers and Transport Layer Security (TLS) profiles recommended by
  Red Hat Product Security. This prevents the use of weak signature algorithms
  to ensure that your cluster remains protected and compliant with security
  standards.

- **Prometheus alert attachment** — you can attach Prometheus alerting rules and
  `Alertmanager` silences to a prompt directly from their details pages.

- **Google Vertex AI provider support** — OpenShift Lightspeed supports Google
  Vertex AI as an LLM provider. You can configure Google-native models (such as
  Gemini) by using the `google_vertex` provider type. You can also configure
  Anthropic models (such as Claude hosted on Vertex AI) by using the
  `google_vertex_anthropic` provider type. Both provider types authenticate by
  using a Google Cloud Platform (GCP) service account JSON key stored within a
  Kubernetes Secret.

## Release Notes for 1.0

Red Hat OpenShift Lightspeed version 1.0 provides an AI-driven virtual assistant
that helps users troubleshoot and manage OpenShift clusters. This release
introduces support for OpenShift Container Platform 4.15 and later.

### Enhancements

Red Hat OpenShift Lightspeed 1.0 introduces general availability support for
OpenShift Container Platform 4.15 and later. This release includes new AI-driven
cluster interaction capabilities, security updates, and several Technology
Preview features.

The following enhancements are included:

- **Cluster interaction** — AI-driven cluster interaction capabilities for
  troubleshooting and management.
- **PostgreSQL persistence** — persistent storage backend using PostgreSQL.
- **Token quota** — token quota management for controlling usage.

### Technology Preview Features

> **Important:** Technology Preview features are not supported with Red Hat
> production service level agreements (SLAs) and might not be functionally
> complete. Red Hat does not recommend using them in production. These features
> provide early access to upcoming product features, enabling customers to test
> functionality and provide feedback during the development process.

The 1.0 release notes list the following as Technology Preview features:

- Cluster interaction
- PostgreSQL persistence
- Token quota

### Known Issues

Red Hat OpenShift Lightspeed 1.0 includes known issues related to web console
interface visibility, quota configuration updates, and database connectivity.
Use the provided workarounds to resolve these issues and maintain service
availability in your OpenShift cluster.

- **Lightspeed icon disappears on namespace/project creation** — for OpenShift
  Container Platform 4.17 and later, the OpenShift Lightspeed icon disappears
  when you click Create Namespace or Create Project from:
  - Administration > Namespaces
  - Home > Projects > Create Project
  - The Project drop-down menu at the top of most pages
  - **Workaround:** Refresh the web browser and the OpenShift Lightspeed icon
    appears. (OLS-1815)

- **Quota parameter changes not applied until period expiry** — changing the
  value of the `quota` parameter in the
  `spec.ols.quotaHandlersConfig.limitersConfig` specification of the
  `OLSConfig` custom resource file does not take effect until the currently
  defined quota period expires.
  - **Workaround:** Delete the OpenShift Lightspeed Operator. Ensure that any
    operand pods that the OpenShift Lightspeed Operator manages, and the
    Persistent Volume Claim `lightspeed-postgres-pvc` associated with the
    `postgres` pod are also deleted. Then, install the OpenShift Lightspeed
    Operator again. (OLS-1826)

- **Service pod fails to connect to postgres after restart** — after restarting
  the `postgres` pod, the OpenShift Lightspeed service pod fails to connect to
  the `postgres` pod.
  - **Workaround:** Restart the OpenShift Lightspeed service pod so that the
    service pod connects to the `postgres` pod. (OLS-1835)

## Supported OCP Versions

- **1.0** — OpenShift Container Platform 4.15 and later
- **1.1** — OpenShift Container Platform 4.16 and later
- **1.1.1** — OpenShift Container Platform 4.16 and later
