# Shared Rules

This directory contains short, tool-neutral project rules.

Use these files for durable domain constraints that should apply across agent tools. Keep detailed workflows in `.agents/skills/` and make each rule point to the relevant skill instead of duplicating procedure text.

| Rule | Purpose |
|------|---------|
| `project.md` | Project structure, coding discipline, change conventions, governance |
| `env.md` | Live demo environment, secrets, certs, cluster safety |
| `kanban-log-watch.md` | After every dest Hermes Kanban spawn, read the official worker log in the same turn |
| `ensure-cli-capability.md` | Stage 080 golden `ensure_cli`: probe kantra usability (`kantra-assert-exec`), not mere presence. No MTA/KAI precedent; probe exceeds existence/`X_OK`. |
| `managed-scope-enforcement.md` | PVC `HERMES_MANAGED_DIR` is advisory; `/etc/hermes` image bake is the native enforcement; dest-5 cuts first |
| `k2-env-assignment-not-access.md` | K2 terminal fence must not treat `export NAME=value` spans as filesystem access; do not widen allow-root |
| `k2-opaque-not-pathless.md` | AMEND `214743ZA`: deny opaque construction, not every pathless command; `strip_env` does not close GAP 2 |
| `skill-path-declaration.md` | Golden skills declare path classes; dest-init fail-closes vs `K2_ALLOW_ROOT`; derived output stays inside a grant |
| `external-dirs-home-contract.md` | Relocated `external_dirs` home slot is dest-user `/home/user/.hermes/skills`, not worker `Path.home()` |
| `profile-home-contract.md` | Profile `HERMES_HOME` vs OS `HOME`; do not publish post-hoc `kanban_create` board gates |
| `native-kanban-alignment.md` | Keep G1–G4; adopt `request-review`/`attach`; named K4 mint-writer; OBJECT swarm for serial T0 |
| `m2-plan-assignee-implementer.md` | M2 PLAN `--assignee implementer`; retire dest AGENTS.md orchestrator-for-M2 |
| `m2-m3-native-dispatch.md` | Minted M3 children claim via native dispatcher; M4 still needs a named GO |
| `gitops.md` | GitOps authoring, manifests, labels, schema validation |
| `docs.md` | Documentation standards, README structure, operations docs |
| `rhoai.md` | RHOAI platform component guidance backed by official Red Hat documentation |
| `ocp.md` | OpenShift Container Platform infrastructure, control plane, networking, auth, monitoring, GitOps, cluster, and storage integration guidance |
| `odf.md` | OpenShift Data Foundation storage, object storage, NooBaa, OBC, and storage-class guidance |
| `stage-080-track-b.md` | Stage 080 Track B: quality over throughput; mandatory quality-advance loop before ship/next story |
