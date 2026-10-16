# Studio MCP catalog qualification

`validate.sh` checks that the Gen AI Studio catalog entries match the live MCP servers (see
[`../studio-mcp/`](../studio-mcp/README.md)). This folder holds the persona-level qualification of the token-required
entry `OpenShift-MCP-ReadWrite`, which `validate.sh` does not do because it needs both persona sessions.

| Script | When to run |
|---|---|
| `qualify-mcp.sh --admin-kubeconfig FILE --developer-kubeconfig FILE --receipt FILE` | After a change to the read-write MCP server, its Route or the catalog entry, or before a demo that uses it. Needs current `ai-admin` and `ai-developer` sessions ([`personas/login.sh`](../../010-openshift-ai-platform-foundation/personas/README.md)). Checks the published entry first (`studio-mcp/publish.sh --validate`), then that both personas discover the entry and list its tools in Gen AI Studio, that a missing session bearer is refused, and, calling the Route directly, that the developer reads its own project, is denied the hosting project and that an invalid bearer is rejected. No model calls and no cluster writes; writes a new private receipt and refuses an existing one. Optional: `--bootstrap-kubeconfig`, `--state`, `--expected-stage040-revision`, `--expected-stage060-revision` (passed to `publish.sh`). |

Browser rendering and model-generated tool invocation remain user acceptance steps.
