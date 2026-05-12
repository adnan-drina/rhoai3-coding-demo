# Scribe MCP Stage Map

## Source

The user-provided repository, <https://github.com/sshaaf/scribe>, is a Java 21 and Quarkus 3 MCP server for generating Konveyor and Kantra rules.

The inspected repository contains:

- a Quarkus application using `quarkus-mcp-server-sse`;
- an MCP SSE endpoint at `http://localhost:8080/mcp/sse`;
- a single parametric MCP tool that routes rule-generation operations by operation name;
- rule operations for Java, Go, file content, XML, JSON, built-in file checks, ruleset creation, rule validation, and ruleset validation;
- command enablement controls through `application.properties`;
- Jib container-image configuration using a UBI 9 OpenJDK 21 runtime base image;
- tests for rule generation, validation, Go provider behavior, serialization, and external examples.

Local verification on May 9, 2026:

```bash
cd /tmp/scribe
./mvnw test
```

Result: 53 tests passed, 0 failures, 0 errors.

## Summary Assessment

Scribe is a strong fit for the planned modernization workflow. It turns MTA custom-rule authoring into an MCP tool that OpenCode or another agent can call while working on modernization analysis.

The strongest fit is:

- Stage 060: optional domain-specific MCP server pattern;
- Stage 130: OpenCode MCP configuration and per-agent tool control;
- Stage 155: supply-chain evidence for a custom MCP server image;
- Stage 160: standards-to-Konveyor-rule workflow for modernization at scale;
- Stage 170: future modernization harness tool inside an agent mesh.

It should not be treated as a replacement for MTA, Developer Lightspeed for MTA, or human rule review. Scribe can generate and validate rule YAML, but the workflow still needs grounded standards input, MTA validation, false-positive review, versioning, and approval.

## How Agents Should Load It

Scribe exposes an HTTP/SSE MCP endpoint. Agents that support remote MCP servers should connect to:

```text
http://localhost:8080/mcp/sse
```

For OpenCode, use a remote MCP entry:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scribe": {
      "type": "remote",
      "url": "http://localhost:8080/mcp/sse",
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

For agent-scoped use, keep Scribe registered but disable its tools globally, then enable them only for the modernization or migration agent:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scribe": {
      "type": "remote",
      "url": "http://localhost:8080/mcp/sse",
      "enabled": true,
      "timeout": 30000
    }
  },
  "tools": {
    "scribe_*": false
  },
  "agent": {
    "migration-specialist": {
      "tools": {
        "scribe_*": true
      }
    }
  }
}
```

For clients that use `mcpServers`, use the repository's documented shape:

```json
{
  "mcpServers": {
    "scribe": {
      "url": "http://localhost:8080/mcp/sse"
    }
  }
}
```

Scribe is not a stdio MCP server in the inspected repository. If an agent only supports stdio MCP servers, the demo should either run Scribe as a remote HTTP/SSE service behind an adapter supported by that agent, or defer that agent until remote MCP support is available.

## Recommended Runtime Patterns

### Local Dev Spaces Sidecar

Run Scribe inside the developer workspace with:

```bash
mvn quarkus:dev
```

or:

```bash
java -jar scribe.jar
```

Then configure OpenCode or another MCP-capable agent to use `http://localhost:8080/mcp/sse`.

This is the fastest path for a demo iteration, but it keeps the MCP server local to the workspace and does not prove platform governance.

### Platform MCP Service

Package Scribe as a container image and deploy it on OpenShift as a platform service. Agents connect through a Route, service DNS name, or MCP Gateway.

This is the stronger enterprise pattern because it lets the platform apply:

- image provenance and scanning;
- SBOM and signature checks;
- network policy;
- authentication and authorization;
- identity-based tool filtering through MCP Gateway;
- audit logs and tracing;
- runtime limits.

## Stage Mapping

| Demo stage | Mapping | How to use it |
|------------|---------|---------------|
| Stage 060: MCP Context Integrations | Strong fit as an optional domain-specific MCP server. | Add Scribe as a future MCP integration pattern after read-only OpenShift MCP. Treat write-capable or generated-output MCP tools as higher risk than read-only context tools. |
| Stage 080: AI-Assisted Application Modernization | Partial fit. Scribe complements MTA by generating custom rules. | Keep MTA and Developer Lightspeed as the modernization platform. Use Scribe only for custom-rule authoring and validation. |
| Stage 100: Governed Developer Entry Point | Partial fit. Developer Hub could document or launch the Scribe-backed modernization workflow. | Add later as catalog/TechDocs guidance, not as a first entry-point dependency. |
| Stage 130: Agentic Engineering With OpenCode | Strong fit. OpenCode can load Scribe as a remote MCP server and scope it to a migration agent. | Add an OpenCode MCP example and agent-scoped tool policy. Require review before accepting generated rules. |
| Stage 140: Golden Path Quarkus Service | Weak to partial fit. Scribe itself is a Quarkus MCP server. | Use as a reference for a Quarkus-based MCP service only if the demo later adds a "build an MCP server" slice. |
| Stage 150: Governed Pipeline And Deployment | Partial fit. Scribe is a deployable Quarkus service. | If adopted as a platform service, build and deploy it through the governed pipeline instead of running it manually. |
| Stage 155: Red Hat Trusted Software Supply Chain | Strong fit if Scribe is packaged. | Treat Scribe's MCP server image as an AI/developer-tool artifact requiring SBOM, provenance, signing, scanning, and promotion policy. |
| Stage 160: Modernization At Scale With MTA And Developer Lightspeed | Strongest fit. | Use Scribe to generate and validate Konveyor/Kantra rules from corporate standards retrieved through RAG or MCP. Run generated rules through MTA and false-positive review. |
| Stage 170: Agent Mesh Modernization Pattern | Partial fit. | Treat Scribe as a tool used by a modernization harness, not as the harness itself. |

## Suggested Stage 160 Workflow

1. Retrieve the relevant corporate standard passage through the planned standards RAG or MCP lookup.
2. Ask the migration agent to propose the rule intent, expected matches, known non-matches, category, effort, labels, and documentation link.
3. Call Scribe through MCP to generate the rule YAML.
4. Call Scribe validation for the generated rule.
5. Add the rule to a reviewed ruleset branch.
6. Run MTA against the selected application.
7. Capture findings, false positives, false negatives, and accepted remediation notes.
8. Promote the ruleset only after human review.

## Example Agent Instruction

```text
Use the Scribe MCP server only after you have cited the corporate standard passage that justifies the rule. Generate a Konveyor rule for the smallest detectable pattern, validate the rule with Scribe, and list expected matches, known non-matches, false-positive risks, category, effort, labels, and review evidence. Do not commit the rule until a human approves it.
```

## Trust Boundaries

Scribe generates rule definitions that influence modernization analysis. That makes it more than passive context. A poor rule can create false positives, miss required remediation, or encode a corporate standard incorrectly.

Required controls:

- ground rule intent in cited standards, MTA findings, or source evidence;
- scope Scribe tools to modernization agents only;
- validate generated rule YAML before use;
- test rules against expected-good and known-bad examples;
- review false-positive and false-negative risk;
- version rulesets in git;
- treat Scribe deployment artifacts as supply-chain-controlled platform assets;
- put authentication, authorization, network policy, and audit in front of any shared Scribe endpoint.

## Open Questions

- Should Scribe run locally inside Dev Spaces for the first demo, or as a shared OpenShift MCP service?
- Should Scribe be exposed directly to OpenCode, or only through MCP Gateway?
- Which agent should receive Scribe tools: `migration-specialist`, `rule-author`, or a separate `mta-rule-engineer`?
- Should the first implementation generate one Java rule only, or demonstrate Java plus file/XML/JSON rules?
- Should generated rules live in the application repo, a modernization-rules repo, or an MTA rules catalog repo?
- How should Scribe validation combine with MTA's own rule validation and analysis run?

## References

- [sshaaf/scribe](https://github.com/sshaaf/scribe)
- [OpenCode MCP servers](https://opencode.ai/docs/mcp-servers/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Konveyor](https://www.konveyor.io/)
- [Migration Toolkit for Applications](https://developers.redhat.com/products/mta)
