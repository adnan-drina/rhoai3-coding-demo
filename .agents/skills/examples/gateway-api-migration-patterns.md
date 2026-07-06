# Gateway API Migration Patterns

These examples are review and implementation patterns for custom workbench
images. They are not complete image definitions.

## Prefix-Aware Application Checklist

```text
NB_PREFIX is read from the environment.
The application base path is set to NB_PREFIX.
Static assets use relative URLs.
API calls use relative URLs.
Redirects stay under NB_PREFIX.
GET /${NB_PREFIX}/api returns HTTP 200.
GET /${NB_PREFIX}/api/kernels returns [] or kernel status JSON.
GET /${NB_PREFIX}/api/terminals returns [] or terminal status JSON.
```

## Python Framework Pattern

```python
import os

nb_prefix = os.environ.get("NB_PREFIX", "")

# FastAPI-style frameworks should pass nb_prefix as the root/base path.
# Flask-style frameworks should set APPLICATION_ROOT to nb_prefix.
```

Review points:

- The framework must generate links and redirects with the prefix.
- Static assets and API clients should avoid absolute root paths.
- Test from the OpenShift AI workbench URL, not only from localhost.

## Relative URL Pattern

Use:

```text
static/app.js
api/data
../api/data
```

Avoid:

```text
/static/app.js
/api/data
```

Review points:

- Absolute root paths bypass the workbench prefix.
- Browser developer tools are useful for finding failed static asset and API
  requests.

## NGINX Prefix-Preserving Redirect Pattern

```nginx
location ${NB_PREFIX} {
    return 302 $custom_scheme://$http_host${NB_PREFIX}/myapp/;
}
```

Review points:

- Redirects must include `NB_PREFIX`.
- Redirects to `/myapp/` without the prefix break Gateway routing.

## NGINX Proxy Pattern

```nginx
location ${NB_PREFIX}/myapp/ {
    rewrite ^${NB_PREFIX}/myapp/(.*)$ /$1 break;
    proxy_pass http://localhost:8080/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_read_timeout 20d;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $custom_scheme;
}
```

Review points:

- Match the prefixed path externally.
- Strip the prefix only before proxying to a backend that expects root paths.
- Preserve WebSocket headers for interactive sessions.

## Health Endpoint Pattern

```nginx
location = ${NB_PREFIX}/api {
    return 200;
    access_log off;
}
```

Review points:

- The health endpoint must be reachable at the prefixed path.
- If the endpoint redirects, the redirect must preserve `NB_PREFIX`.

## Verification Commands

Run only after following the repository OpenShift safety guard:

```bash
oc exec <pod-name> -- curl -I http://localhost:8888/${NB_PREFIX}/api
```

Expected result:

```text
HTTP/1.1 200 OK
```

Operational checks:

```text
Open the workbench from the project Workbenches tab.
Check browser developer tools for failed static assets or API requests.
Review Gateway Controller logs for No route matched.
```
