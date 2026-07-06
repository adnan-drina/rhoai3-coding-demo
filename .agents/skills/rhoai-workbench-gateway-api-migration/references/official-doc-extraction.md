# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Architecture Change

Earlier custom workbench setups commonly used individual OpenShift Routes and
unique hostnames or subdomains. The application usually served from `/`, and
the route path handling stripped the external prefix before the request reached
the container.

OpenShift AI now uses Kubernetes Gateway API request routing for workbenches.
The new routing model uses a single entry point with path-based routing, and
the full path is preserved when the request reaches the workbench container.

Practical impact:

- previous model: container applications could often serve from `/`
- Gateway API model: container applications must handle the complete
  workbench path prefix
- the runtime prefix is represented by the `NB_PREFIX` environment variable

If an application redirects to paths outside `NB_PREFIX`, the Gateway cannot
route those requests back to the workbench container.

## Path-Based Routing Rule

All browser requests must stay inside the workbench prefix:

```text
/${NB_PREFIX}/...
```

Avoid absolute URLs such as:

```text
/static/app.js
/api/data
```

Use relative URLs such as:

```text
static/app.js
api/data
```

Relative paths resolve under the prefixed context and remain routable through
the Gateway.

## Migration Prerequisites

- The user has OpenShift AI administrator privileges.
- OpenShift is at least version 4.19.
- The OpenShift AI Operator is at least version 3.0.
- The team can rebuild the custom workbench image.

## Native Application Migration

Required compatibility work:

1. Implement the health endpoint under the prefixed path:

   ```text
   GET /${NB_PREFIX}/api
   ```

   The endpoint must return HTTP 200.

2. Implement idle-culling status endpoints as JSON arrays:

   ```text
   GET /${NB_PREFIX}/api/kernels
   GET /${NB_PREFIX}/api/terminals
   ```

3. Use relative URLs for static assets, redirects, and API calls.
4. Configure the application's base path to the `NB_PREFIX` environment value
   when the framework supports base-path configuration.

Framework examples from the official guidance:

- FastAPI: configure `root_path`
- Flask: configure `APPLICATION_ROOT`
- JavaScript frameworks: configure the base URL or public path setting

## NGINX Translation Pattern

Use NGINX when the application cannot be configured for a base path or contains
hardcoded absolute URLs that cannot be changed.

NGINX responsibilities:

- preserve `NB_PREFIX` in redirects
- match the full prefixed application path
- strip the prefix before proxying to the internal application
- proxy to the backend service inside the container
- preserve WebSocket upgrade headers for interactive sessions
- set long read timeouts for interactive workbench use
- pass forwarding headers such as host, client address, and scheme
- expose the required health endpoint under `/${NB_PREFIX}/api`

## Verification

User-interface verification:

- Open the workbench from the Workbenches tab on the project details page.
- Confirm the page loads correctly.
- Confirm styling, JavaScript, redirects, and interactive functionality work.

In-pod health check:

```bash
oc exec <pod-name> -- curl -I http://localhost:8888/${NB_PREFIX}/api
```

Expected signal:

```text
HTTP/1.1 200 OK
```

Gateway diagnostics:

- review Gateway Controller logs for `No route matched`
- treat that message as evidence that the application is sending responses or
  redirects without the required prefix
- if the browser shows `no healthy upstream`, first verify that the generated
  `*-kube-rbac-proxy` Service has a ready EndpointSlice endpoint on port
  `8443`; this is a backend health problem, not proof of an application
  `NB_PREFIX` problem

## Out Of Scope For This Chapter

This chapter does not define:

- Gateway API installation or cluster GatewayClass design
- full Gateway Controller log command for every deployment topology
- how to build the custom workbench image
- ImageStream labels and annotations for dashboard discovery
- Notebook custom resource fields
- application-specific framework configuration for every framework
- full NGINX production hardening

Use `rhoai-workbenches-custom-images` and active schema checks for image and
workbench resource authoring.
