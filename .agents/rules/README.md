# Shared Rules

This directory contains short, tool-neutral project rules.

Use these files for durable domain constraints that should apply across agent
tools. Keep detailed workflows in `.agents/skills/` and make each rule point to
the relevant skill instead of duplicating procedure text.

| Rule | Purpose |
|------|---------|
| `project.md` | Project structure, coding discipline, change conventions, governance |
| `env.md` | Live demo environment, secrets, certs, cluster safety |
| `gitops.md` | GitOps authoring, manifests, labels, schema validation |
| `docs.md` | Documentation standards, README structure, operations docs |
