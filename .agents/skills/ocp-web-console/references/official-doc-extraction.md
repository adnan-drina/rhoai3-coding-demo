# Official Documentation Extraction

## Console Access

The OpenShift web console is a browser-accessible interface for visualizing,
browsing, and managing project contents. Supported browsers include Edge,
Chrome, Safari, and Mozilla Firefox; IE 11 and earlier are not supported.

For existing clusters, use this posture:

- discover the console URL with `oc whoami --show-console`
- validate access through the configured identity provider
- avoid storing installer-generated `kubeadmin` credentials in project files
- document console access as a user workflow, not as an automation dependency

## Console Workload And Dashboard

The console runs as a pod and serves the static assets for the web UI. Home >
Overview provides high-level cluster information through dashboard cards such
as details, inventory, status, utilization, and activity.

For the demo, use the dashboard for human validation and screenshots only after
the underlying cluster state is also verified with `oc` or official APIs.

## Perspectives And User Preferences

Starting with OpenShift Container Platform 4.19, console perspectives are
unified and the Developer perspective is not enabled by default. Administrators
can enable or disable the Developer perspective through Console Operator
customization.

User preferences are automatically saved and can include:

- theme
- default project
- topology graph or list view
- form or YAML resource editing preference
- language
- notification display
- default application resource type

Do not use user preferences as a substitute for project GitOps defaults.

## Console Configuration

The official docs distinguish console configuration resources:

- `console.config.openshift.io/cluster` is used for web console settings such
  as `spec.authentication.logoutRedirect` and exposes the console URL in
  status.
- `consoles.operator.openshift.io/cluster` is the Console Operator resource
  used for operator-managed behavior, customization, perspectives, and disabling
  the console with `spec.managementState`.

Review resource type and API group carefully before editing or authoring
manifests.

## Console Customization

Administrators can customize the web console for enterprise or government
requirements. Officially documented customization areas include:

- custom logo and product name
- custom links through `ConsoleLink`
- console and download routes
- login page customization
- external log links
- notification banners
- CLI downloads
- YAML examples for Kubernetes resources
- perspective visibility
- developer catalog and sub-catalog visibility

For demo work, keep customization minimal and explicitly tied to the story or
operator workflow. Do not brand the OpenShift web console as the RHOAI
dashboard.

## Dynamic Plugins

Dynamic plugins are loaded from remote sources at runtime. They can add custom
pages, perspectives, navigation items, tabs, and actions to the console UI.
`ConsolePlugin` registers a plugin with the console, and a cluster
administrator enables it in Console Operator configuration.

Review principles:

- use the official `ConsolePlugin` schema for registration, proxy, and CSP
  fields
- serve plugin assets with valid JavaScript MIME type
- prefix CSS classes with the plugin name to avoid collisions
- maintain a consistent PatternFly-based look, feel, and behavior
- use service proxy authorization intentionally, especially when forwarding the
  logged-in user's token
- document browser-side plugin disablement separately from cluster-wide plugin
  disablement

Do not introduce dynamic plugins for the demo unless they remove a clear
operational gap and can be maintained.

## Web Terminal

The Web Terminal Operator can be installed from the software catalog. Installing
it also installs the DevWorkspace Operator as a dependency. The terminal is
embedded in the console, uses the logged-in user's credentials, includes common
CLI tools, and creates a user-specific `DevWorkspace` when opened.

Review principles:

- manually created Web Terminal Operator subscriptions must be named
  `web-terminal` for the console masthead icon to appear
- the cluster administrator default terminal project is `openshift-terminal`
- timeout and image settings can be set per session or for all users
- network policies for terminal namespaces must allow required ingress from
  `openshift-console` and `openshift-operators`
- uninstalling the Web Terminal Operator does not automatically remove all CRDs
  or managed resources
- remove the DevWorkspace Operator only if no other installed component depends
  on it

For this demo, treat web terminal installation as optional and avoid relying on
it for core automation.

## Disabling The Web Console

The web console can be disabled by editing
`consoles.operator.openshift.io/cluster` and setting `spec.managementState` to
`Removed`. The valid documented values include `Managed`, `Unmanaged`, and
`Removed`.

For this demo, do not disable the console unless the user explicitly requests a
recovery or hardening exercise. The console is useful for live walkthroughs and
operator validation.

## Quick Starts

Quick starts are guided tutorials with tasks, steps, and check-your-work
modules. Users access them from the Help menu. Administrators can enable or
disable individual quick starts.

Use quick starts only for small guided tasks. Keep broader demo narratives in
project READMEs and presentations.
