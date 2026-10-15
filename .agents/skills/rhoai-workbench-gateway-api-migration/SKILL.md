---
name: rhoai-workbench-gateway-api-migration
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a custom OpenShift AI workbench image must work behind the
  Kubernetes Gateway API path-based routing of OpenShift AI 3.x: honoring
  NB_PREFIX, the /api health and kernels/terminals culling endpoints, relative
  URLs, framework base paths, an NGINX path-translation layer, or "no route
  matched" in the Gateway Controller logs. Not deployed in this demo (no custom
  workbench images). Do NOT use for building or registering images (use
  rhoai-workbenches-custom-images), the dashboard import (use
  rhoai-workbench-image-import), or MaaS Gateway and HTTPRoute work (use
  rhoai-maas-governance or ocp-ingress-gateway-routes).
---

# RHOAI Workbench Gateway API Migration

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections.

**Not deployed in this demo.** The repo has no custom workbench image, so no
image needs migrating. This skill is the acceptance gate for any custom image that
`rhoai-workbenches-custom-images` or `rhoai-workbench-image-import` adds.

## When to use

- A custom workbench starts but its page, assets or API calls fail in the browser.
- Reviewing a custom image before it is registered.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Workbench routing is product-owned; the repo adds no Route, HTTPRoute or proxy for workbenches | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md` (generated objects are not in Git) | [Path-based routing][paths] |
| The OpenShift AI gateway class `data-science-gateway-class` comes with the platform; Stage 040 reuses it only for the MaaS Gateway | `gitops/stages/040-governed-models-as-a-service/gateway-governance/README.md` | [Kubernetes Gateway API migration][intro] |
| A custom image is accepted only when it serves under `NB_PREFIX`, answers the health endpoint and the culling endpoints; prefer the framework's base-path setting over NGINX | (review rule; no image in Git) | [Migrate][migrate], [Migrate with NGINX][nginx] |

## Procedure

1. Read [Path-based routing][paths]; the names a review checks are `NB_PREFIX`,
   `/{NB_PREFIX}/api`, `/{NB_PREFIX}/api/kernels` and `/{NB_PREFIX}/api/terminals`.
2. Configure the application's base path from `NB_PREFIX` ([Migrate][migrate]);
   use the NGINX layer only when the framework cannot
   ([Migrate with NGINX][nginx]).
3. Test in a throwaway workbench in `demo-sandbox`, after the OpenShift safety
   guard in `AGENTS.md`:

   ```bash
   oc get notebooks.kubeflow.org -n demo-sandbox
   oc exec -n demo-sandbox <workbench-pod> -- sh -c 'curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8888${NB_PREFIX}/api"'
   ```

   Port 8888 is an assumption about the image; use the port the image serves.

## Pitfalls

- Absolute asset URLs and redirects that drop the prefix are the usual
  failure; the page loads blank or 404s ([Migrate][migrate]).
- "No route matched" is a Gateway Controller log entry, not an application
  error; the docs do not name the controller namespace, so find it with
  `oc get pods -A | grep -i gateway` before reading logs.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview and prerequisites | [Kubernetes Gateway API migration][intro] |
| Routing model | [Path-based routing][paths] |
| Migration | [Migrate][migrate], [Migrate with NGINX][nginx] |

## Related skills

`rhoai-workbenches-custom-images`, `rhoai-workbench-image-import`,
`rhoai-data-science-ide-workflows`, `ocp-ingress-gateway-routes`.

[intro]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#introducing-kubernetes-gateway-api_resource-mgmt
[paths]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#understanding-path-based-routing_resource-mgmt
[migrate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#migrating-to-kubernetes-gateway-api_resource-mgmt
[nginx]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#migrating-to-kubernetes-gateway-api-with-nginx_resource-mgmt
