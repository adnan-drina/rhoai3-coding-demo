# MCP Gateway operator prerequisite

This isolated component installs the Red Hat Connectivity Link MCP Gateway 0.7.1 Technology Preview operator. It does not attach an extension to the MaaS Gateway or change model authentication, the Studio connection, or MCP server credentials.

Run the stage's `deploy-mcp-gateway-platform.sh` with the published branch. Reconcile the dedicated Application at its exact published revision, inspect the generated InstallPlan's bundle, images and permissions, and approve only the reviewed plan. Validate with `RHOAI_MCP_GATEWAY_EXPECTED_REVISION` set to that full commit SHA.

The operator uses the existing `openshift-operators` global OperatorGroup so OLM can reuse the installed Connectivity Link dependencies. This component does not own or change that OperatorGroup or its existing Subscriptions. An MCP-only plan is the intended scope; an expanded plan requires separate review of its exact versions and changes. The completed installation used the explicitly approved combined MCP 0.7.1, GitOps 1.21.5 and Service Mesh 3.4.3 plan. Operator watch scope does not grant human users access to tools or data.

The separate probe namespace quota prohibits LoadBalancer services, NodePort services and OpenShift Routes. The bounded native 0.7.1 probe rejected all three exposure types and showed the same non-MCP health request changing from HTTP 200 to 404 after Extension insertion. The generated filter selects the Gateway workload and listener port without a hostname or path restriction. Do not attach this version to the shared model Gateway's 443 listeners. Temporary probe resources and loopback forwards were removed; the operator prerequisite remains available for a separately reviewed topology.
