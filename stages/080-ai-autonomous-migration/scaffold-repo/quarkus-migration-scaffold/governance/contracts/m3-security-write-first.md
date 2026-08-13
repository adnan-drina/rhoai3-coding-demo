# M3 security write-first ( R-M3.29)

**Status:** binding proving-min
**Basis:** S-005 hard-block `t_df9cf31a` (0/3 across dual wall)

## Rules

| ID | Rule |
|----|------|
| **R-M3.29** | Security cards: hard `skill_view` → `references/security-config.md` **and** `references/security-anti-essay.md` (Hermes skill tree) before first `security/**` edit; write-first / anti-essay |
| **R-M3.32** | Create/init must sync `extensions/<skill>/references/*` into `.hermes/skills/<skill>/references/` and `--check` before next S-005-class create (`sync-extension-overlays-into-skills.py`) — extensions-only is not enough for `skill_view` |
| **R-M3.39** | `security_authz` / claim language require **functional** Quarkus auth: `quarkus-security` + `quarkus-elytron-security-jdbc` in pom, `application.properties` basic+JDBC userstore + profile toggle, and `check-empty-security.py` rc=0 — javadoc-only `*AuthenticationConfig` / compile-only 3/3 is **FAIL** (AR-2.2) |
| **R-M3.28** | Wall-exit-eval / ballot narrative must credit AD-009 freeze + >300s stream latencies before calling a wall-fit PASS body a sizing defect |
| **R-M3.30** | After soft-K spent hard-block with 0 progress: typed `environmental_provider` + **fix-forward new create** (fresh task id) — never silent reclaim |
| **R-M3.31** | Exit-eval: `overall_ok=false` when wallish and checkpoint incomplete (even if compile green) |

See also: `wall-exit-eval.md`, `ad011-skill-extension.md`, `runnable-db-security.md`, `m3-wallfit-jdbc.md` (sizing twin is **not** this failure mode).
