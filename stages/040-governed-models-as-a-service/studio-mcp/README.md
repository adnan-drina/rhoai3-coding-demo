# Studio MCP catalog entries

Gen AI Studio lists MCP servers from the discovery keys of ConfigMap `gen-ai-aa-mcp-servers` in
`redhat-ods-applications`. Stage 040 owns the ConfigMap; the two entries for the Stage 060 OpenShift MCP servers
(`OpenShift-MCP`, read-only and in-cluster, and `OpenShift-MCP-ReadWrite`, through its Route) are written at deploy time,
because their addresses exist only once Stage 060 runs. Argo CD leaves exactly those two fields to this script
(`ignoreDifferences` on `040-genai-studio`).

| Script | When to run |
|---|---|
| `publish.sh [--key KEY] --replace` | After a reviewed change of an entry's address or description (a changed Stage 060 Route, MCPServer address or description text). Without `--replace` a changed entry is refused. |
| `publish.sh --validate` | Read-only check that both entries match what would be published. |

`deploy.sh` runs `publish.sh --defer-if-absent` on every deploy: it adds missing entries, repeats are no-ops, and it
defers while Stage 060 is not deployed (run Stage 040 `deploy.sh` again after Stage 060). Run alone, the script checks
against the revision `040-genai-studio` is deployed at, which must be on `origin/main`.
