# Validation Checklist

Use this checklist before accepting custom workbench image Gateway API
migration docs, runbooks, or implementation changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The work is about custom workbench application compatibility with Gateway API
  path-based routing.
- Gateway API installation, cluster ingress design, ImageStream registration,
  Notebook CR authoring, and dashboard import stay in their own skills.

## Prerequisite Review

- OpenShift version is at least 4.19.
- OpenShift AI Operator version is at least 3.0.
- Team can rebuild the custom workbench image.
- The target workbench image is documented as custom image content owned by the
  project or customer.
- Live checks follow the OpenShift safety guard in `AGENTS.md`.

## Application Path Review

- Application honors `NB_PREFIX`.
- Application does not redirect outside the prefixed path.
- Static assets use relative URLs or generated URLs that include the prefix.
- API calls use relative URLs or generated URLs that include the prefix.
- Framework base path is configured when supported.
- NGINX is used only when native base-path configuration is not possible.

## Endpoint Review

- `GET /${NB_PREFIX}/api` returns HTTP 200.
- `GET /${NB_PREFIX}/api/kernels` returns a JSON array when idle culling is
  expected.
- `GET /${NB_PREFIX}/api/terminals` returns a JSON array when idle culling is
  expected.
- Health and culling endpoints are implemented in the final image, not only in
  local development.

## NGINX Review

When NGINX is used:

- redirects preserve `NB_PREFIX`
- prefixed routes match before proxying
- prefix stripping is intentional and only happens inside the proxy
- WebSocket upgrade headers are preserved
- long read timeouts are set for interactive sessions
- forwarded host, client IP, and scheme headers are passed to the backend
- health endpoint remains available at `/${NB_PREFIX}/api`

## Verification Review

Run only after following the OpenShift safety guard:

```bash
oc exec <pod-name> -- curl -I http://localhost:8888/${NB_PREFIX}/api
```

Expected result:

```text
HTTP/1.1 200 OK
```

Also verify:

- workbench opens from the project Workbenches tab
- generated `*-kube-rbac-proxy` Service has a ready EndpointSlice endpoint on
  port `8443`
- Notebook, generated StatefulSet, and running pod include the
  `kube-rbac-proxy` sidecar for migrated Gateway-backed workbenches
- page loads with styling and static assets
- navigation and redirects remain under the workbench prefix
- interactive functions work
- Gateway Controller logs do not show `No route matched` for the workbench

## Fail Conditions

- Application assumes it is served from `/`.
- Application emits absolute paths that bypass `NB_PREFIX`.
- Health check only works at `/api`, not at the prefixed path.
- Idle culling endpoints are missing when culling is expected.
- HTTPRoute targets a proxy Service with no ready `8443` endpoint.
- Gateway logs show `No route matched` for workbench interactions.
- NGINX strips or redirects away from the required prefix.
