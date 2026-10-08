# MCP Gateway operator prerequisite

This isolated component installs the Red Hat Connectivity Link MCP Gateway 0.7.1 Technology Preview operator. It does not attach an extension to the MaaS Gateway or change model authentication, the Studio connection, or MCP server credentials.

Run the stage's `deploy-mcp-gateway-platform.sh` with the published branch. Reconcile the dedicated Application at its exact published revision, inspect the generated InstallPlan's bundle, images and permissions, and approve only the reviewed plan. Validate with `RHOAI_MCP_GATEWAY_EXPECTED_REVISION` set to that full commit SHA.

The namespace quota prohibits LoadBalancer services, NodePort services and OpenShift Routes. A bounded private ClusterIP probe must establish the selected product's request matching behavior before any shared Gateway integration. Operator readiness alone does not qualify that integration.
