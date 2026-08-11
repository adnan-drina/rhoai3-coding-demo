# Tooling pins (R-HX.1)

**Status:** binding proving-min for Wave-0 demo reproducibility  
**Sources:** Architect BIND `E-20260811T070102Z` · live v11 workspace smoke 2026-08-11

| Tool | Pin (campaign-tested) | Install surface |
|------|----------------------|-----------------|
| **Hermes Agent** | `v0.20.0` (`2026.8.3`) | Platform Dev Spaces init (`maas-api-key-provisioning` / Managed Scope). Record digest when installer gains a pin API. |
| **Spec Kit (`specify-cli`)** | `0.16.1` | `uv tool install 'specify-cli==0.16.1'` in `specify-workspace-init` |

## Hermes Spec Kit skill names

Installed under `~/.hermes/skills` as **hyphenated** packages. Hard-invoke with
Hermes skill names (not dotted GitHub slash paths):

| Wrong (obsolete dotted) | Correct (Hermes skill) |
|-------------------------|------------------------|
| `/speckit.specify` | `/speckit-specify` |
| `/speckit.plan` | `/speckit-plan` |
| `/speckit.tasks` | `/speckit-tasks` |
| `/speckit.analyze` | `/speckit-analyze` |
| `/speckit.implement` | **FORBIDDEN** — Kanban only |

## Fresh-workspace smoke (before cold audience)

1. `hermes --version` matches pin above (or Architect-approved bump).
2. `specify --version` / `uv tool list` shows `specify-cli` **0.16.1**.
3. `ls ~/.hermes/skills | grep '^speckit-'` includes specify/plan/tasks/analyze.
4. `python3 .hermes/skills/phase-dispatch/scripts/sync-extension-overlays-into-skills.py . --check`.
