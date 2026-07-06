---
name: rhcl-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when checking RHCL 1.4 release notes, new features, bug fixes, known
  issues, and deprecated features. Do NOT use for RHCL concepts or architecture
  (use rhcl-about), MCP gateway concepts (use rhcl-mcp-gateway), installing
  (use rhcl-install), or configuring (use rhcl-configure).
---

# RHCL Release Notes

Use this skill to ground RHCL 1.4 release note content in the official
documentation — new features, enhancements, Technology Preview features, bug
fixes, known issues, and deprecations.

## Source Grounding

Read `references/source-capture.md` before referencing release content.
Official Red Hat documentation is the product authority.

## Critical Notices

### RHCL 1.4.0 Deprecation

**RHCL 1.4.0 is deprecated.** Clusters running 1.4.0 might experience:

- Authentication failures
- API key management errors
- Gateway instability
- Gateway pod memory pressure

These issues stem from integration changes not fully compatible on all
supported OCP and OpenShift Service Mesh combinations.

**Action required**: Install or upgrade to Red Hat Connectivity Link 1.4.1.

### RHCL 1.3 Lifecycle Update

Maintenance Support for RHCL 1.3 ends with the release of RHCL 1.5 (revised
from previous 1.6 announcement).

## New Features (1.4)

### X.509 Cryptographic Identity Verification (GA)

X.509 client certificate authentication for strong cryptographic identity
verification. Creates a two-layer process requiring both cryptographic proof
and context-aware validation.

### MCP Gateway: Prompt Federation (GA)

Federate MCP prompts through the Gateway object. Access and run prompt
templates from upstream MCP servers through a single central Gateway
connection. The Gateway presents a unified, prefixed list of all available
prompts across the network.

### MCP Gateway: Vault Integration (Docs)

Documentation for using HashiCorp Vault to retrieve and inject authentication
credentials into MCP server request flows.

### MCP Gateway: Audit Trail (Docs)

Documentation for creating an audit trail capturing caller identity, tool
names, and MCP session context through the MCP gateway.

## Notable Technical Changes (1.4)

| Change | Impact |
|--------|--------|
| Gateway integration migrated from Istio WasmPlugin to EnvoyFilter CRs | Internal; no user action. Orphan CRs may remain. |
| Kuadrant CR lookup cached in reconciliation state | Internal; reduces API server load and reconciliation times. |
| `toolPrefix` renamed to `prefix` on MCPServerRegistration | **Migration required**: delete and recreate CRs. |

### MCPServerRegistration Migration

The `toolPrefix` field is renamed `prefix`. This is a server-level namespace
(not tool-specific) that now applies to both tools and prompts.

Migration: Replace `toolPrefix` with `prefix` in manifests. Existing CRs must
be deleted and recreated (not patched in-place). Use `sed` or `yq` for bulk
updates before `oc apply`.

## Technology Preview Features (1.4)

- **GRPCRoute policy attachment**: Attach AuthPolicy and RateLimitPolicy to
  GRPCRoute CRs with native service and method matching.
- **Disconnected installation**: Procedures for installing in disconnected
  environments.
- **OCP web console plugin for API management**: API catalog, role-based
  access, and dynamic graph view of API products and attached resources.

## Known Issues (1.4)

- When Redis or RedisCached storage is set in a Limitador CR and the limitador
  pod restarts, the first request to the gateway is never rate-limited. All
  subsequent HTTP requests are rate-limited correctly. (CONNLINK-856)

## Bug Fixes (1.4.1)

- **AuthConfig CRD upgrade blocker** (CONNLINK-1131): OLM blocked upgrades
  when AuthConfig resources used CEL predicate conditions because `v1beta2`
  schema lacked CEL validation patches. Fix: `v1beta3` is now the standard
  served version; `v1beta2` is deprecated and removed.

## Demo Implications

The repo pins `rhcl-operator.v1.3.4` per `docs/PLATFORM_BASELINE.md` because
RHCL 1.4.0 is deprecated. The upgrade path to RHCL 1.4.1+ should be validated
against Stage 040 MaaS Gateway regression gates before approval.

When RHCL 1.4.1 is adopted:

- Update MCPServerRegistration CRs: `toolPrefix` → `prefix`
- Validate AuthPolicy and RateLimitPolicy behavior after EnvoyFilter migration
- Test MCP prompt federation if MCP gateway is enabled

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the release-specific question:
   - New features and GA announcements
   - Technology Preview features
   - Known issues and workarounds
   - Bug fixes (async z-stream releases)
   - Migration requirements
   - Lifecycle and support timeline
4. Cross-reference with `BACKLOG.md` for demo-specific compatibility holds.

## Related Skills

- Use `rhcl-about` for RHCL product concepts and architecture.
- Use `rhcl-mcp-gateway` for MCP gateway architecture details.
- Use `rhoai-maas-governance` for RHOAI MaaS integration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
