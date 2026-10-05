# Agentic Quarkus Scaffold

Corporate Quarkus application scaffold for spec-driven agentic development.
Provisioned per developer by the `agentic-quarkus-scaffold` golden-path
template in the platform's Developer Hub.

The application does not exist yet — that is the point. You describe it in a
spec, and a coding agent (OpenCode) builds it following the corporate
standards that live in this repository:

- `AGENTS.md` — the agent's entry point: identity, workflow, commands.
- `.opencode/skills/` — REST conventions, test standards, and the mandatory
  MaaS-only LLM integration pattern.
- `specs/TEMPLATE.md` — spec format; `specs/claims-triage-service.md` is a
  worked example including an LLM-powered feature through the MaaS gateway.

## Getting started

1. Open this repository in Dev Spaces and start the workspace.
2. Copy `specs/TEMPLATE.md` to `specs/<your-feature>.md` and fill it in, or
   use the provided example spec.
3. Start OpenCode in the terminal and ask it to implement the spec.
4. Push to `main` — the platform pipeline builds, runs the SonarQube quality
   gate (fails on any new issue), and publishes the image.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | /q/health | Health (SmallRye Health) |

(The agent maintains this table as endpoints are added.)
