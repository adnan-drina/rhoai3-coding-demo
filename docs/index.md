# RHOAI Coding Demo Developer Docs

This TechDocs site is the Developer Hub entry point for the governed developer
workspace used in the "From Vibe Coding to Agentic Engineering" demo.

Start with the [Developer Workspace Guide](DEVELOPER_WORKSPACE_GUIDE.md). It
shows how an enterprise developer moves from Developer Hub to Red Hat OpenShift
Dev Spaces, verifies MaaS-backed Kilo Code, and records Stage 060 evidence
outside Git without exposing secrets or private route details.

The terminology follows Red Hat's enterprise guide to AI-assisted application
development and the Red Hat "vibes, specs, skills, and agents" framing. The
developer workflow starts with human-led exploration in Kilo Code, then moves
through specifications, reusable skills, and finally OpenCode agents that use
those assets to perform bounded engineering work.

## What This Site Covers

- How to choose the correct Developer Hub component for onboarding,
  engineering, or modernization.
- How to open the controlled single-repository Dev Spaces workspace.
- How to confirm only the selected source repository is present.
- How to verify Kilo Code against the private MaaS model path.
- How Stage 060 uses bounded Kilo Code prompts, gap lists, and human review for
  coding.
- What evidence to record before OpenCode performs agentic engineering work.

## What This Site Does Not Do

- It does not expose model API keys, cluster credentials, or private route
  hostnames.
- It does not load the platform repository into the developer workspace.
- It does not combine the onboarding, inventory service, and modernization
  repositories into one workspace.
- It does not replace the app-local README, task packets, or `AGENTS.md` rules
  in `coolstore-inventory-service`.

The developer workspace should remain focused on application work. Platform
operators maintain this guide in `rhoai3-coding-demo` and publish it through
Developer Hub TechDocs.
