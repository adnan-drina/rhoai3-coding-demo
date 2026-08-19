# Shared Rules

This directory contains short, tool-neutral project rules.

Use these files for durable domain constraints that should apply across agent tools. Keep detailed workflows in `.agents/skills/` and make each rule point to the relevant skill instead of duplicating procedure text.

| Rule | Purpose |
|------|---------|
| `project.md` | Project structure, coding discipline, change conventions, governance |
| `env.md` | Live demo environment, secrets, certs, cluster safety |
| `kanban-log-watch.md` | After every dest Hermes Kanban spawn, read the official worker log in the same turn |
| `gitops.md` | GitOps authoring, manifests, labels, schema validation |
| `docs.md` | Documentation standards, README structure, operations docs |
| `rhoai.md` | RHOAI platform component guidance backed by official Red Hat documentation |
| `ocp.md` | OpenShift Container Platform infrastructure, control plane, networking, auth, monitoring, GitOps, cluster, and storage integration guidance |
| `odf.md` | OpenShift Data Foundation storage, object storage, NooBaa, OBC, and storage-class guidance |
| `stage-080-track-b.md` | Stage 080 Track B: quality over throughput; mandatory quality-advance loop before ship/next story |
