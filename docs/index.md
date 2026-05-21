# RHOAI Coding Demo Developer Docs

This TechDocs site is the Developer Hub entry point for the governed developer
workspace used in the "From Vibe Coding to Agentic Engineering" demo.

Start with the [Developer Workspace Guide](DEVELOPER_WORKSPACE_GUIDE.md). It
shows how an enterprise developer moves from Developer Hub to Red Hat OpenShift
Dev Spaces, verifies MaaS-backed Continue, and captures safe Stage 100 evidence
without committing secrets or private route details.

## What This Site Covers

- How to choose the correct Developer Hub component for onboarding,
  engineering, or modernization.
- How to open the controlled single-repository Dev Spaces workspace.
- How to confirm only the selected source repository is present.
- How to verify Continue against the private MaaS model path.
- Where deferred stages `110-170` are tracked before they are recreated.
- What evidence to record before later agentic engineering work.

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
