# Shared Rules

This directory contains short, tool-neutral project rules.

Use these files for durable domain constraints that should apply across agent tools. Keep detailed workflows in `.agents/skills/` and make each rule point to the relevant skill instead of duplicating procedure text.

| Rule | Purpose |
|------|---------|
| `project.md` | Project structure, coding discipline, change conventions, governance |
| `env.md` | Live demo environment, secrets, certs, cluster safety |
| `kanban-log-watch.md` | After every dest Hermes Kanban spawn, read the official worker log in the same turn |
| `ensure-cli-capability.md` | Stage 080 golden `ensure_cli`: probe kantra usability (`kantra-assert-exec`), not mere presence. No MTA/KAI precedent; probe exceeds existence/`X_OK`. |
| `tirith-declared-absent.md` | Dest must not declare Hermes tirith enabled when the overlay does not ship the binary; disable until a named GO |
| `k2-env-assignment-not-access.md` | K2 terminal fence must not treat `export NAME=value` spans as filesystem access; do not widen allow-root |
| `k2-opaque-not-pathless.md` | AMEND `214743ZA`: deny opaque construction, not every pathless command; `strip_env` does not close GAP 2 |
| `skill-path-declaration.md` | Golden skills declare path classes; dest-init fail-closes vs `K2_ALLOW_ROOT`; derived output stays inside a grant |
| `gitops.md` | GitOps authoring, manifests, labels, schema validation |
| `docs.md` | Documentation standards, README structure, operations docs |
| `rhoai.md` | RHOAI platform component guidance backed by official Red Hat documentation |
| `ocp.md` | OpenShift Container Platform infrastructure, control plane, networking, auth, monitoring, GitOps, cluster, and storage integration guidance |
| `odf.md` | OpenShift Data Foundation storage, object storage, NooBaa, OBC, and storage-class guidance |
| `stage-080-track-b.md` | Stage 080 Track B: quality over throughput; mandatory quality-advance loop before ship/next story |
