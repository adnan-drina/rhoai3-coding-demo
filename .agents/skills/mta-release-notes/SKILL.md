---
name: mta-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when checking MTA 8.2 release notes, new features, bug fixes, known
  issues, and deprecated features. Do NOT use for installing (use mta-install),
  using tools (use mta-cli/mta-ui), or AI features (use mta-lightspeed).
---

# MTA Release Notes

Use this skill to ground Migration Toolkit for Applications release information
in the official Red Hat MTA 8.2 release notes.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Release Summary

Migration Toolkit for Applications (MTA) 8.2 accelerates large-scale
application modernization across hybrid cloud environments on Red Hat OpenShift.
The 8.1 release builds on MTA 8.0 with centralized configuration management,
LLM proxy service support, new Developer Preview features, and multiple bug
fixes.

Key releases covered:

- **MTA 8.2.0** — centralized configuration, LLM proxy, C# provider, VS Code
  extension pack
- **MTA 8.0.1** — pre-generated Maven index, Cloud Foundry fixes, FQN matching
- **MTA 8.0.0** — Developer Lightspeed, platform awareness, asset generation,
  new VS Code plugin, Solution Server (TP), Agentic AI (TP)

## Key Topics

- New features: centralized configuration management (profiles and custom
  rules), LLM proxy service via Keycloak JWT, C# provider (Developer Preview),
  VS Code extension pack (Developer Preview)
- Technology Preview / Developer Preview: C# source-only provider, VS Code
  extension pack with language-specific extensions, Solution Server, Agentic AI
- Known issues: Gradle dependency violations not triggered in UI
- Fixed issues: Source Control credential character limit, non-UTF-8 static
  report display, Cloud Foundry service binding discovery
- Removed features (8.0): XML rules removed, Eclipse IDE plugin removed

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - new features in MTA 8.2.0 or 8.0.x
   - Developer Preview or Technology Preview features
   - known issues and workarounds
   - fixed issues across 8.0.0, 8.0.1, and 8.2.0
   - removed or deprecated functionality
4. Use exact feature names and issue IDs from the extraction.
5. When advising on MTA 8.x features, distinguish between GA features,
   Technology Preview, and Developer Preview support scopes.

## Related Skills

- Use `mta-install` for installing MTA Operator, UI, and CLI.
- Use `mta-cli` for CLI usage and analysis workflows (planned).
- Use `mta-ui` for UI usage and assessment workflows (planned).
- Use `mta-lightspeed` for Developer Lightspeed AI features (planned).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
