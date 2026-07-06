# Namespace Topology Example

Use this example as a review pattern, not as a required implementation.

## Product Namespaces

```text
redhat-ods-operator       # RHOAI Operator
redhat-ods-applications  # dashboard and required product components
rhods-notebooks          # default basic workbench project
```

## Demo Application Namespaces

```text
rhoai-demo-system        # optional demo control-plane resources
maas                     # model-serving and MaaS demo resources
acme-corp                # scenario application workloads
rag-demo                 # RAG application services, if split from maas
```

Rules:

- Keep demo applications outside OpenShift AI product namespaces.
- Treat custom applications, MCP servers, databases, and scenario services as
  demo glue unless official docs identify them as product-managed components.
- If custom OpenShift AI projects are used, document the custom-project
  installation decision and keep the namespace roles clear.
