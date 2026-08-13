# Tooling pins (R-HX.1)

**Status:** binding proving-min for Wave-0 demo reproducibility
**Basis:** in-tree harness obligations (sibling contracts + skills).

| Tool | Pin (campaign-tested) | Install surface |
|------|----------------------|-----------------|
| **Hermes Agent** | `v0.20.0` (`2026.8.3`) | Platform Dev Spaces init (`maas-api-key-provisioning` / Managed Scope). Record digest when installer gains a pin API. |
| **Spec Kit (`specify-cli`)** | `0.16.1` | `uv tool install 'specify-cli==0.16.1'` in `init-spec-workspace` |
| **Red Hat Quarkus platform** | `com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1-redhat-00002` | Destination `pom.xml` `quarkus.platform.*` properties; Maven plugin same GAV stream. Skills cite this row — do not restate the version in skill bodies. |

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

1. `hermes --version` matches pin above (or steward-approved bump).
2. `specify --version` / `uv tool list` shows `specify-cli` **0.16.1**.
3. `ls ~/.hermes/skills | grep '^speckit-'` includes specify/plan/tasks/analyze.
4. `python3 .hermes/enforcement/dispatch-phase/scripts/sync-extension-overlays-into-skills.py . --check`.
