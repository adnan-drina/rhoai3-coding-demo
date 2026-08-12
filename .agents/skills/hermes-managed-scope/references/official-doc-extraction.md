# Official Doc Extraction — hermes-managed-scope

Merged from two blind parallel research dossiers (capture date 2026-08-12):
Run A (base document below — broader capture) and Run B (corroboration +
unique findings, appended). Reviewer validation: shared-core quotes
(precedence, world-readable .env, v1 enforcement, refusal message), Run A's
iron-proxy capture, and Run B's credential-pools and env-vars-reference
findings all re-verified verbatim against live pages on 2026-08-12.
Original dossiers: `source-analysis/hermes/hermes-managed-scope-capture-A.md`
and `-B.md`.

---

# Hermes Managed Scope — Source Capture (Run A)

## Executive Summary (5 lines)

1. **Captured**: the full official Managed Scope mechanism (`/etc/hermes`, precedence, security model), the full Secrets subsystem (Bitwarden, 1Password, Command-helper sources, multi-source precedence, plugin authoring), and the Security page (8-layer defense-in-depth model, production deployment checklist), plus the Egress credential-injection proxy (iron-proxy) and the NixOS declarative "Managed Mode" as a contrasting mechanism.
2. **Confidence**: High for Managed Scope and the three bundled secret sources (verbatim primary-source pages, internally consistent, cross-referenced from the Configuration page). Medium for exhaustive coverage of the Security page's 60+ command-pattern table (captured, but this dossier prioritizes fleet/governance-relevant subsections). Low/gap for macOS/Windows managed-directory equivalents and Homebrew "formula"-locked installs (explicitly out of scope per the docs themselves, or only glancingly referenced).
3. **Biggest gap**: the docs explicitly state v1 Managed Scope has **no** hard enforcement against a user with directory write access or root, **no** signed/integrity-checked managed files, and **no** macOS/Windows native managed locations or `managed.d/` fragment directories — all listed as "intentionally out of scope for v1." There is no worked end-to-end example of combining Managed Scope with the Secrets subsystem (e.g., pinning `secrets.bitwarden.enabled: true` at `/etc/hermes/config.yaml` for a fleet) in the official docs.
4. **Contradicts current placeholder?** No contradictions found. The placeholder's three pinned URLs are all live, current, and accurate anchors. One addition needed: the Secrets page has three linked sub-pages (Bitwarden, 1Password, Command helper) and one developer-guide page (Secret Source Plugins) that the placeholder's single `secrets/` URL does not itself surface as separate pins.
5. **Suggested next skill to research**: `hermes-configuration` should verify it captures the full Configuration Precedence ladder (CLI args → `config.yaml` → `.env` → built-in defaults) since Managed Scope sits *above* that ladder and this dossier only captures the intersection point; also flag `hermes-hooks`/`hermes-kanban` maintainers that the 1Password page's "Bootstrap token" section has a normative statement about cron/kanban dispatch context (`kanban.dispatch_in_gateway: false`) needing the token in `os.environ` of every spawned process — worth a cross-check in their own captures.

---

## 1. Capture Header

| Field | Value |
|---|---|
| Product | Hermes Agent (Nous Research) |
| Version marker | No version marker on the Managed Scope, Secrets, or Security pages themselves. The CLI Commands Reference example output shows `version: 0.8.0 (2026.4.8) [af4abd2f]` as an illustrative `hermes dump` sample, not a docs-version marker. The iron-proxy page pins binary `v0.39.0` (iron-proxy, not Hermes itself) and mentions `bws v2.0.0` (Bitwarden CLI) as the currently-pinned bundled binary version. Nix docs page is explicitly labeled "Tier 2 platform — best-effort." |
| Capture date | 2026-08-12 |
| Capture run | A (independent parallel run; blind to any other run's dossier) |

### Full page inventory (step 1: territory mapping)

**Read in full (primary sources for this skill):**

| Page | URL | Relevance |
|---|---|---|
| Managed Scope | `/docs/user-guide/managed-scope` | Core topic — admin-tier pinning, `/etc/hermes`, precedence, security model |
| Secrets (index) | `/docs/user-guide/secrets/` | Core topic — external secret manager overview, multi-source precedence, profile aliasing |
| Security | `/docs/user-guide/security` | Core topic (one of the three pinned URLs) — 8-layer defense-in-depth, production deployment checklist |
| Bitwarden Secrets Manager | `/docs/user-guide/secrets/bitwarden` | Bundled secret source #1 — full config/CLI/security notes |
| 1Password | `/docs/user-guide/secrets/onepassword` | Bundled secret source #2 — full config/CLI/security notes |
| Command Helper Secret Source | `/docs/user-guide/secrets/command` | Bundled secret source #3 — generic CLI-vault escape hatch |
| Secret Source Plugins (developer guide) | `/docs/developer-guide/secret-source-plugin` | Third-party secret backend contract — orchestrator vs. plugin responsibilities |
| Egress credential-injection proxy (iron-proxy) | `/docs/user-guide/egress/iron-proxy` | Secrets-handling + security posture for sandboxed worker fleets — token-swap architecture, SSRF denylist, Bitwarden rotation integration |
| Nix & NixOS Setup | `/docs/getting-started/nix-setup` | Contrasting "package-manager-locked install" mechanism explicitly named in the Managed Scope page (`HERMES_MANAGED=true`, `.managed` marker, blocked CLI commands) |
| Configuration | `/docs/user-guide/configuration` | Boundary/context — hosts the Configuration Precedence ladder that Managed Scope sits above; one explicit cross-link to Managed Scope |
| CLI Commands Reference | `/docs/reference/cli-commands` | Reference — `hermes config`, `hermes doctor`, `hermes secrets bitwarden`, `hermes security audit` command tables |

**Identified but deprioritized (with reason):**

| Page | URL | Reason deprioritized |
|---|---|---|
| Egress proxy internals | `/docs/developer-guide/egress-internals` | Implementation-level (file syscalls, subprocess flags) for contributors; user-facing iron-proxy page already covers the operator-relevant facts |
| Build a Hermes Plugin | `/docs/developer-guide/plugins` | General plugin framework; only its "Secret Source Plugins" pointer is in-scope, already followed |
| 1Password skill (optional skill doc) | `/docs/user-guide/skills/optional/security/security-1password` | Describes the *optional Hermes skill* wrapping the `op` CLI for ad hoc agent use, not the `secrets.onepassword` startup-injection mechanism; adjacent but distinct feature |
| Skills System | `/docs/user-guide/features/skills` | Only touched for the `hermes skills install official/security/1password` command; skills system itself belongs to `hermes-skills` |
| Profiles: Running Multiple Agents | `/docs/user-guide/profiles` | `HERMES_HOME` / profile boundary is `hermes-configuration` territory; only referenced here because Managed Scope and Secrets both apply per-process regardless of profile |
| Codex App-Server Runtime | `/docs/user-guide/features/codex-app-server-runtime` | Uses the word "managed" for an unrelated mechanism (a marker-delimited managed block inside `~/.codex/config.toml` regenerated by `hermes codex-runtime migrate`) — namespace collision only, not the same feature as Managed Scope; flagged in Gaps for disambiguation |
| Website Blocklist section of Configuration page | `/docs/user-guide/configuration#website-blocklist` | Duplicate of content already fully quoted from the Security page; config-key table captured once under Reference Tables |
| Deploy Runbook (skills-hub tap deployment) | inside `/docs/user-guide/features/skills` (heading only) | False-positive match on "Deploy" — this is skill-tap/registry deployment, unrelated to fleet config governance |
| llms-full.txt | `/docs/llms-full.txt` | Used only as a cross-reference/navigation aid to confirm which pages exist and locate headings; not cited as a primary source for any normative statement (its snapshot predates the Managed Scope, Secrets, and Secret-Source-Plugin pages — they do not appear in it at all, confirming it lags behind the live site) |

**Dead links / redirects encountered:** None. All fetched URLs (via `WebFetch`) returned 200 with rendered content. No redirects were observed (the trailing-slash `secrets/` URL from the placeholder resolved directly).

---

## 2. Recommended Source Pins

Replace the current three-URL pin list in `references/source-capture.md` with:

**Core (must keep, confirmed accurate):**
- `https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope`
- `https://hermes-agent.nousresearch.com/docs/user-guide/secrets/`
- `https://hermes-agent.nousresearch.com/docs/user-guide/security`

**Recommended additions (found during territory mapping, directly load-bearing for this skill's stated scope — "secrets storage and handling"):**
- `https://hermes-agent.nousresearch.com/docs/user-guide/secrets/bitwarden` — the only bundled source with a documented `override_existing: true` central-rotation default and explicit "good case: multi-machine fleets" framing
- `https://hermes-agent.nousresearch.com/docs/user-guide/secrets/onepassword` — documents the three-way bootstrap-token precedence for non-interactive/fleet contexts (`.env` / `.op.env` / systemd `EnvironmentFile`)
- `https://hermes-agent.nousresearch.com/docs/user-guide/secrets/command` — generic vault escape hatch relevant when a fleet's secret manager has no bundled integration
- `https://hermes-agent.nousresearch.com/docs/developer-guide/secret-source-plugin` — needed if stage 080 ever needs a custom secret backend; documents the contract Hermes core enforces
- `https://hermes-agent.nousresearch.com/docs/user-guide/egress/iron-proxy` — directly answers "security posture relevant to running managed Hermes worker fleets" for the Docker sandbox case; not obviously discoverable from the three original pins (lives under a different `egress/` path, only reachable via search)

**Optional / context-only (cite inline, do not need to be primary pins):**
- `https://hermes-agent.nousresearch.com/docs/getting-started/nix-setup` — only for the "Managed Mode" contrast section; low value if stage 080 does not use NixOS
- `https://hermes-agent.nousresearch.com/docs/user-guide/configuration` — only for the one paragraph that cross-links to Managed Scope and situates it in the precedence ladder; primary ownership stays with `hermes-configuration`
- `https://hermes-agent.nousresearch.com/docs/reference/cli-commands` — only for the `hermes config`, `hermes doctor`, `hermes secrets bitwarden`, `hermes security audit` subcommand tables

**Pins that proved irrelevant:** none of the three original pins were irrelevant — all three were directly on-topic and among the most load-bearing pages found.

---

## 3. Page Maps

### 3.1 Managed Scope (`/docs/user-guide/managed-scope`)

1. (intro, no heading) — what managed scope is, who it's for, the one-line mechanism summary
2. (callout) "Different from a package-manager–locked install" — disambiguates from Nix/formula-style whole-config locking
3. **Where it lives** — `/etc/hermes/{config.yaml,.env}`, ownership/mode, "either file is optional" semantics
4. **Relocating the directory** (H3 under "Where it lives") — `HERMES_MANAGED_DIR`, the redirect-attack warning
5. **Precedence** — the 3-tier table (managed → user → default/shell), leaf-level merge semantics, the "wins over shell env too" callout
6. **Seeing what's managed** — `hermes config`, `hermes doctor`, the refusal error message shown to a user who tries to override
7. **Setting up a managed scope (administrators)** — full shell walkthrough (`sudo mkdir`, `tee`, `chmod`), "changes take effect on next start" + malformed-file behavior
8. **Security model and limitations (v1)** — bulleted limitations (filesystem-permissions-only enforcement, world-readable `.env`, no agent-tool hard-block) + a bulleted "intentionally out of scope for v1" list (six items)

### 3.2 Secrets (`/docs/user-guide/secrets/`)

1. (intro) — what the feature replaces (`~/.hermes/.env` plaintext keys), bootstrap-token framing, list of three supported sources
2. **Multiple sources at once** — three-rule precedence ladder (own-env-wins-by-default / mapped-beats-bulk / first-source-wins), provenance labeling (`(from Bitwarden)`)
3. **Profiles and shared vaults** — `secrets.preserve_existing`, profile aliasing (`secrets.profile_alias`)
4. **Adding your own backend** — one-paragraph pointer to the developer guide; states the bundled set is "deliberately closed"

### 3.3 Security (`/docs/user-guide/security`)

1. **Overview** — the 8-layer list (user auth, dangerous-command approval, file write safety, container isolation, MCP credential filtering, context file scanning, cross-session isolation, input sanitization)
2. **Dangerous Command Approval** — Approval Modes (`approvals.mode`: smart/manual/off + full key table), YOLO Mode, Hardline Blocklist (always-on floor), User-Defined Deny Rules (`approvals.deny`), Approval Timeout, What Triggers Approval (large pattern table), Approval Flow (CLI), Approval Flow (Gateway/Messaging), Permanent Allowlist, Mining Approval History (`hermes approvals suggest`)
3. **File Write Safety** — Protected paths (always blocked), `HERMES_WRITE_SAFE_ROOT` (optional sandbox), Cron and other Hermes state
4. **User Authorization (Gateway)** — Authorization Check Order (6-step), Platform Allowlists, DM Pairing System (security features table, CLI commands, Docker `-u hermes` caveat)
5. **Container Isolation** — Docker Security Flags (`_BASE_SECURITY_ARGS`), Resource Limits, Filesystem Persistence
6. **Terminal Backend Security Comparison** — table of 7 backends × isolation/dangerous-cmd-check/best-for
7. **Environment Variable Passthrough** — How It Works (skill-scoped automatic passthrough, config-based manual passthrough), Credential File Passthrough, What Each Sandbox Filters (table), Security Considerations
8. **MCP Credential Handling** — Safe Environment Variables (fixed allowlist), Credential Redaction (pattern list), Website Access Policy (`security.website_blocklist`), SSRF Protection (blocked-range list + `security.allow_private_urls` opt-out), Tirith Pre-Exec Security Scanning
9. **Best Practices for Production Deployment** — Gateway Deployment Checklist (10 items), Securing API Keys, Network Isolation (SSH terminal backend pattern)
10. **Supply-chain advisory checking** — `hermes doctor --ack`, lazy install of optional dependencies (`security.allow_lazy_installs`)

### 3.4 Bitwarden Secrets Manager (`/docs/user-guide/secrets/bitwarden`)

1. (intro) — bootstrap-secret-replaces-N-keys framing
2. **How it works** — 4-step lifecycle, auto-download of `bws` binary
3. **Why machine accounts (and why no 2FA prompt)** — threat framing for the bootstrap token
4. **Setup** — 1. Create a machine account and access token; 2. Run the wizard; 3. Confirm
5. **CLI** — table of 7 subcommands
6. **Rotating an expired or revoked token** — error text + fix command
7. **Configuration** — full YAML defaults block + key table
8. **Failure modes** — table (never blocks startup)
9. **Security notes** — bootstrap-token-cannot-be-overwritten guarantee, checksum verification, no auto-upgrade
10. **When NOT to use this** — explicit anti-patterns list + "the good case ... multi-machine fleets"

### 3.5 1Password (`/docs/user-guide/secrets/onepassword`)

1. (intro) — `op://` reference model
2. **How it works** — 4-step lifecycle; never-blocks-startup guarantee
3. **Authentication** — service accounts vs. desktop/interactive sessions
4. **Bootstrap token** — three delivery mechanisms in precedence order (`.env` / `.op.env` / systemd `EnvironmentFile`), non-interactive-context enumeration
5. **Setup** — 1. Install and sign in to `op`; 2. Enable the integration; 3. Map your credentials; 4. Preview and confirm
6. **CLI** — table of 8 subcommands + aliases note
7. **Configuration** — full YAML defaults block + key table
8. **Failure modes** — table
9. **Caching** — `op_cache.json` semantics
10. **Security notes** — token-overwrite refusal, minimal child env, `op://` validation
11. **When NOT to use this** — same anti-pattern framing as Bitwarden

### 3.6 Command Helper Secret Source (`/docs/user-guide/secrets/command`)

1. (intro) — generic CLI-vault framing
2. **How it works** — 3-step lifecycle + YAML example
3. **Config** — 4-key table
4. **Security model** — 5 bullets (trust level, output cap, stderr discard, whitespace handling, POSIX-only)
5. **Failure modes** — table
6. **When to use this vs a plugin**

### 3.7 Secret Source Plugins (`/docs/developer-guide/secret-source-plugin`)

1. (intro) — what secret sources resolve and when, bundled-set-is-closed policy
2. **What the framework owns vs. what you own** — two-column table
3. **Directory structure** — plugin layout
4. **The SecretSource ABC** — full Python class example; Contract rules (5 enforced rules); Choosing your `shape` (mapped vs. bulk); Optional hooks (5-row table)
5. **Subprocess safety: use `run_secret_cli()`**
6. **Registering** — `register(ctx)` example + rejection conditions
7. **Users configure it like any other source**
8. **Validate with the conformance kit**
9. **ErrorKind reference** — 8-row table

### 3.8 Egress credential-injection proxy (iron-proxy) (`/docs/user-guide/egress/iron-proxy`)

1. (intro) — threat model (prompt-injected sandbox agent exfiltrating real keys)
2. **What it is** / **What it is not**
3. **Quick start** — 4-command lifecycle
4. **Configuration** — full `proxy:` YAML block; Default allowed upstream hosts; Default SSRF deny CIDRs (table); Bind policy
5. **Covered auth schemes** / **Uncovered providers** (tables)
6. **Bitwarden integration** — Rotation semantics, Fail-loud at start, Switching credential source
7. **Slash commands** — full `hermes egress` subcommand tree; Token rotation
8. **State directory layout** — table of files/modes under `~/.hermes/proxy/`
9. **How it works** — request-flow diagram + CA distribution into the sandbox (docker-run arg table) + Node.js asymmetric CA caveat + docker_env collisions
10. **PID and nonce defense**
11. **Security model** — "What this protects against" / "What it does NOT protect against" (two bulleted lists)
12. **Failure modes**, **Troubleshooting**, **Limitations (v1)**

### 3.9 Nix & NixOS Setup (`/docs/getting-started/nix-setup`) — context only

Relevant sections only: **Secrets Management** (sops-nix / agenix / OAuth seeding — never put secrets in `settings`/`environment`), **Managed Mode** (the `HERMES_MANAGED=true` / `.managed` marker mechanism that blocks `hermes config set`, `hermes setup`, `hermes gateway install/uninstall`), **Options Reference → Secrets & Environment** table.

---

## 4. Normative Statements

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "Managed scope lets an administrator push a baseline of configuration and secrets that a standard (non-root) user cannot override." | Managed Scope, intro | Defines the feature's exact authority boundary — non-root users only |
| "When a managed scope is present, the values it specifies win over the user's `~/.hermes/config.yaml`, `~/.hermes/.env`, and even the shell environment — for exactly the keys it pins. Everything else stays fully user-controlled." | Managed Scope, intro | Core precedence rule; "exactly the keys it pins" rules out whole-file locking |
| "A package-manager–managed install (declarative-distro / formula) blocks all config mutation and tells you to use your package manager. Managed scope is a separate mechanism ... The two are independent and can coexist." | Managed Scope, callout | Prevents conflating Managed Scope with NixOS "Managed Mode" — both can be layered |
| "The directory and files are owned by `root` (directory mode `0755`, files `0644`): readable by everyone, writable only by an administrator. That filesystem permission is the enforcement mechanism — a standard user can read the managed files but cannot edit them." | Managed Scope, Where it lives | Exact enforcement mechanism and its precise limits (readable, not just by admin) |
| "Either file is optional. A missing managed directory or missing file simply means 'no managed scope,' and configuration resolves exactly as it does without the feature." | Managed Scope, Where it lives | Fail-safe default: absence of the feature is silent, not an error |
| "A user who can set `HERMES_MANAGED_DIR` can repoint managed scope at a directory they control, defeating it. In a real deployment this variable should be fixed by the administrator (e.g. baked into the service unit / container image), not left user-settable. `hermes doctor` reports the resolved managed directory so a redirect is visible." | Managed Scope, Relocating the directory | Direct security-relevant deployment guidance for stage 080 worker fleet hardening |
| "Merging is leaf-level: pinning `model.default` does not freeze the rest of `model.*` ... forces `model.default` for every user while leaving `model.fallback` (and every other key) under user control." | Managed Scope, Precedence | Precise granularity of pinning — per-leaf-key, not per-section |
| "For the keys it pins, managed scope deliberately wins over the shell environment too — otherwise it would not be 'managed.' This is the one place that inverts the usual 'an environment variable overrides config.yaml' rule, and it applies only to the specific keys the managed layer specifies." | Managed Scope, Precedence note | Explicit exception to the general precedence rule owned by `hermes-configuration` — critical boundary fact both skills must agree on |
| "Cannot set 'model.default': it is managed by your administrator (/etc/hermes/config.yaml) and cannot be changed." | Managed Scope, Seeing what's managed | Exact refusal message text a stage 080 review might grep logs/screenshots for |
| "The same applies to managed secrets — `hermes config set` / setup will not write a user value for an env key pinned by the managed `.env`." | Managed Scope, Seeing what's managed | Confirms secrets pins are enforced identically to config pins |
| "Changes take effect on the next Hermes start (a malformed managed file is logged loudly and ignored — it never blocks startup, but the admin should check `hermes doctor` to confirm the policy is being applied)." | Managed Scope, Setting up a managed scope | Fail-open behavior on malformed admin files — operationally important for fleet rollout safety |
| "Enforcement is filesystem permissions only. If a user has write access to the managed directory (or runs Hermes as `root`), managed scope is advisory." | Managed Scope, Security model and limitations (v1) | Sets the true trust boundary — root or directory-write access defeats the whole feature |
| "The managed `.env` is world-readable (`0644`), so any local user can read secrets pushed through it. Use it for shared, non-sensitive values (an org API base URL, feature defaults) rather than high-sensitivity secrets." | Managed Scope, Security model and limitations (v1) | Direct "don't put real secrets here" guidance — governs what stage 080 may pin in the managed `.env` |
| "The agent's own tools are not hard-blocked from a managed env value ... v1 is a management-convenience boundary against a normal user, not an un-escapable sandbox." | Managed Scope, Security model and limitations (v1) | Sets expectation ceiling: Managed Scope is not a sandbox against the agent itself |
| "The following are intentionally out of scope for v1 and may come later: A hard boundary that the agent itself cannot escape. Native managed locations on macOS and Windows (v1 is Linux/POSIX-first). Drop-in fragment directories (`managed.d/`) for layered policy. Signed / integrity-checked managed files. Remote / device-management (MDM) delivery. Tighter (group-scoped) permissions for managed secrets." | Managed Scope, Security model and limitations (v1) | Explicit non-goals list — critical for a skill about "security posture," since it tells the reviewer what NOT to assume is protected |
| "You can enable more than one secret source at the same time ... Sources compose per env var with a deterministic precedence ladder: 1. Your `.env`/shell wins by default ... 2. Mapped sources beat bulk sources ... 3. First source wins." | Secrets, Multiple sources at once | The exact multi-source precedence algorithm |
| "`override_existing` never lets one source overwrite a var another source already claimed, and no source can ever overwrite another source's bootstrap token (e.g. `BWS_ACCESS_TOKEN`)." | Secrets, Multiple sources at once | Bootstrap-token protection is a cross-source invariant, not per-source |
| "The bundled set is deliberately closed (same policy as memory providers): Bitwarden and 1Password ship in-tree. Everything else — Infisical, Proton Pass, HashiCorp Vault, AWS Secrets Manager, OS keystores — belongs in plugin repos." | Secrets, Adding your own backend | Governs whether stage 080 can request a new bundled backend (no) vs. must write a plugin (yes) |
| "Before executing any command, Hermes checks it against a curated list of dangerous patterns. If a match is found, the user must explicitly approve it." | Security, Dangerous Command Approval | Baseline behavior relevant to fleet worker autonomy expectations |
| "Setting `approvals.mode: off` disables all safety prompts. Use only in trusted environments (CI/CD, containers, etc.)." | Security, Approval Modes warning | Direct fleet-relevant operational warning |
| "Some commands are so catastrophic ... that Hermes refuses to run them regardless of: `--yolo`/`/yolo` toggled on, `approvals.mode: off`, Cron jobs running in headless `approve` mode, User explicitly clicking 'allow always' ... there's no override flag." | Security, Hardline Blocklist | The one unconditional safety floor in the whole approval system — relevant to any "can a managed fleet worker ever be fully unattended safely" question |
| "Container bypass: When running in `docker`, `singularity`, `modal`, `daytona`, or `vercel_sandbox` backends, dangerous command checks are skipped because the container itself is the security boundary." | Security, What Triggers Approval (info box) | Explains why fleet deployments should prefer container backends |
| "If no allowlists are configured and `GATEWAY_ALLOW_ALL_USERS` is not set, all users are denied." | Security, User Authorization | Fail-closed default for gateway fleets |
| "Write guards apply to `write_file` and `patch` only. The `terminal` tool runs as the same OS user and can still `cat` or overwrite denied paths via shell commands. The denylist reduces accidental damage ... it does not sandbox a hostile or compromised agent." | Security, File Write Safety | Same "convenience boundary, not a sandbox" caveat pattern as Managed Scope — worth stating consistently |
| "1. Set explicit allowlists — never use `GATEWAY_ALLOW_ALL_USERS=true` in production. 2. Use container backend ... 3. Restrict resource limits ... 4. Store secrets securely ... 8. Run as non-root — never run the gateway as root ..." | Security, Best Practices for Production Deployment → Gateway Deployment Checklist | Direct 10-item checklist for any stage 080 "how should we run this fleet" validation step |
| "Hermes will refuse to let Bitwarden overwrite the bootstrap token itself, even with `override_existing: true`. If you store `BWS_ACCESS_TOKEN` as a secret inside the project, it's silently skipped during apply." | Bitwarden, Security notes | Concrete instance of the cross-source bootstrap-token invariant |
| "The good case for this is multi-machine fleets, shared dev boxes, gateway VPSes, or any setup where you want centralized rotation and revocation across multiple Hermes installations." | Bitwarden, When NOT to use this (closing line) | Direct docs framing of fleet applicability — same sentence appears near-verbatim on the 1Password page |
| "It must be present in `os.environ` of every process that resolves secrets — including cron jobs (`kanban.dispatch_in_gateway: false`), subprocess invocations, CLI runs, macOS launchd agents, and Docker containers — not just the interactive gateway." | 1Password, Bootstrap token | Names the exact fleet/worker contexts the bootstrap token must reach — cites a `hermes-kanban`-owned config key as a boundary example |
| "If the token is reachable only through an interactive shell (`op signin`, `OP_SESSION_*` exports in `.bashrc`, etc.), it will not be inherited by cron jobs or freshly spawned subprocesses, and those contexts will log a warning and fall back to whatever credentials `.env` already held." | 1Password, Bootstrap token | Direct operational failure mode for fleet/worker deployments relying on interactive auth |
| "The sandbox holds opaque proxy tokens, never the real keys ... Compromise the sandbox and the attacker walks away with tokens that only work behind the configured trusted proxy boundary." | iron-proxy, intro | Core security guarantee for sandboxed fleet workers |
| "This release wires the egress proxy into the Docker backend only. Modal, Daytona, SSH, and Singularity do not receive proxy env vars or CA mounts yet." | iron-proxy, intro | Scope limitation directly relevant to choosing a fleet terminal backend |
| "When true (default), the Docker backend refuses to start a sandbox if the proxy is enabled but not running." (`enforce_on_docker`) | iron-proxy, Configuration | Fail-closed default worth citing for fleet hardening |
| "A compromised host process. If the agent process itself is compromised, real keys in the host's `~/.hermes/.env` are exposed regardless. This is a defense-in-depth feature for sandbox compromise, not host compromise." | iron-proxy, Security model | Same "defense-in-depth, not a sandbox against everything" pattern repeated a third time across this dossier's sources |
| "When hermes runs via the NixOS module, the following CLI commands are blocked with a descriptive error ... This prevents drift between what Nix declares and what's on disk. Detection uses two signals: 1. `HERMES_MANAGED=true` ... 2. `.managed` marker file ..." | Nix & NixOS Setup, Managed Mode | The contrasting "whole-config-locked" mechanism explicitly named (but not detailed) by the Managed Scope page's callout |
| "Values in Nix expressions end up in `/nix/store`, which is world-readable. Always use `environmentFiles` with a secrets manager." | Nix & NixOS Setup, Secrets Management | Directly parallels the Managed Scope world-readable-`.env` warning — same underlying lesson in a different mechanism |
| "An administrator can pin specific config and secret values that a standard user cannot override, via a system-level managed directory. See Managed Scope." | Configuration, Org deployments callout | Confirms Managed Scope's canonical cross-link point from the general Configuration page |

---

## 5. Reference Tables

### 5.1 Managed Scope

| Key / path / var | Type | Default | Description |
|---|---|---|---|
| `/etc/hermes/config.yaml` | file path | n/a (optional) | Managed config layer; wins over `~/.hermes/config.yaml` for pinned keys |
| `/etc/hermes/.env` | file path | n/a (optional) | Managed env layer; wins over `~/.hermes/.env` + shell for pinned keys |
| `/etc/hermes` directory mode | filesystem mode | `0755` | root-owned, world-readable, admin-writable |
| managed file mode | filesystem mode | `0644` | root-owned, world-readable, admin-writable |
| `HERMES_MANAGED_DIR` | env var | `/etc/hermes` | Relocates the managed directory; deployment/bootstrap knob, never persisted to `.env` |

CLI: `hermes config` (shows managed source + pinned keys header), `hermes doctor` (reports resolved managed dir + pinned key counts).

### 5.2 Secrets — cross-cutting orchestrator keys

| Key | Type | Default | Description |
|---|---|---|---|
| `secrets.sources` | list | undocumented (optional) | Explicit ordering of sources for first-claim-wins tie-breaking |
| `secrets.preserve_existing` | list of env var names | `[]` (implied; not shown with explicit default) | Env vars whose existing `.env`/shell value always wins even against `override_existing: true` |
| `secrets.profile_alias` | bool | `true` (on by default; page states "on by default") | Controls credential-shaped-suffix profile aliasing (`*_API_KEY`, `*_TOKEN`, `*_SECRET`, `*_KEY`, `*_PASSWORD`) |

### 5.3 Bitwarden (`secrets.bitwarden.*`)

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch |
| `access_token_env` | string | `BWS_ACCESS_TOKEN` | Env var name holding the bootstrap token |
| `project_id` | string | `""` | UUID of the Bitwarden project to sync |
| `server_url` | string | `""` | Region/self-hosted endpoint; empty = US Cloud default |
| `cache_ttl_seconds` | int | `300` | Fetch-result reuse window; `0` disables reuse |
| `encrypted_cache.enabled` | bool | `false` | AES-GCM encrypted cache at `~/.hermes/cache/bws_cache.enc.json` |
| `encrypted_cache.max_stale_seconds` | int | `0` | Stale-cache allowance after network/timeout failure only (never after auth failure) |
| `override_existing` | bool | `true` | Bitwarden values overwrite existing env |
| `auto_install` | bool | `true` | Auto-download `bws` binary |

CLI: `hermes secrets bitwarden {setup, status, token, sync, sync --apply, install, disable}` (aliased `hermes secrets bw`).

### 5.4 1Password (`secrets.onepassword.*`)

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch |
| `env` | map (env-var name → `op://` ref) | `{}` | Explicit credential mapping |
| `account` | string | `""` | Account shorthand/sign-in address |
| `service_account_token_env` | string | `OP_SERVICE_ACCOUNT_TOKEN` | Env var holding the service-account token |
| `binary_path` | string | `""` | Pin the `op` binary path (bypasses PATH lookup) |
| `cache_ttl_seconds` | int | `300` | Resolved-value reuse window; `0` disables both cache layers entirely |
| `override_existing` | bool | `true` | Resolved values overwrite existing env |

CLI: `hermes secrets onepassword {setup, status, token, set ENV_VAR "op://...", remove ENV_VAR, sync, sync --apply, disable}` (aliases: `op`, `1password`).

### 5.5 Command helper (`secrets.command.*`)

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master switch |
| `command` | string | `""` | Helper run via `/bin/sh -c`; must print `KEY=VALUE` lines |
| `helper_timeout_seconds` | int | `3` | Hard timeout for one helper run |
| `override_existing` | bool | `false` | Off by default (unlike Bitwarden/1Password) |

### 5.6 Security page — approvals

| Key | Default | Description |
|---|---|---|
| `approvals.mode` | `smart` | `smart` \| `manual` \| `off` |
| `approvals.timeout` | `300` | Seconds to wait for approval reply |
| `approvals.cron_mode` | `deny` | `deny` \| `approve` — cron headless behavior on dangerous-command hit |
| `approvals.mcp_reload_confirm` | `true` | Confirm before `/reload-mcp` rebuilds tool cache |
| `approvals.destructive_slash_confirm` | `true` | Confirm before `/clear`, `/new`, `/reset`, `/undo` |
| `approvals.denial_breaker_threshold` | `3` | Consecutive denials before hard-stop escalation; `0` disables |
| `approvals.deny` | `[]` (implied) | User-editable glob denylist, checked before `--yolo`/`mode: off` |
| `command_allowlist` | `[]` (implied) | Permanent "always approve" patterns, editable via `hermes config edit` |
| `HERMES_YOLO_MODE` | env var, unset | `1` activates YOLO mode |
| `HERMES_EXEC_ASK` | env var | auto-set `1` when gateway runs | Signals gateway approval-ask context |
| `HERMES_WRITE_SAFE_ROOT` | env var, unset | Restricts `write_file`/`patch` targets to listed prefixes; `:` (Unix) / `;` (Windows) separated |

### 5.7 Security page — general security keys

| Key | Default | Description |
|---|---|---|
| `security.redact_secrets` | `true` | Redact API-key-shaped patterns in tool output/logs |
| `security.tirith_enabled` | `true` | Enable Tirith pre-exec scanning |
| `security.tirith_path` | `"tirith"` | Binary path (PATH lookup default) |
| `security.tirith_timeout` | `5` | Seconds |
| `security.tirith_fail_open` | `true` | Proceed if tirith unavailable; `false` blocks in high-security environments |
| `security.website_blocklist.enabled` | `false` | Master switch for URL blocking |
| `security.website_blocklist.domains` | `[]` | Exact / wildcard-subdomain / TLD-wildcard patterns |
| `security.website_blocklist.shared_files` | `[]` | External files with one domain rule per line |
| `security.allow_private_urls` | `false` | Global opt-out of RFC1918/loopback/link-local/CGNAT/cloud-metadata SSRF blocking |
| `security.allow_lazy_installs` | `true` | Allow venv-scoped `pip install` for lazy-loaded optional deps |
| `config.security.acked_advisories` | persisted list | Advisory IDs acknowledged via `hermes doctor --ack <id>` |
| `terminal.env_passthrough` | `[]` | Config-based manual env-var passthrough into sandboxes |
| `terminal.credential_files` | `[]` | Manual list of files to mount read-only into sandboxes |
| `terminal.docker_forward_env` | `[]` | Explicit allowlist of env vars forwarded into Docker containers |

### 5.8 Egress proxy (`proxy.*`)

| Key | Type | Default | Description |
|---|---|---|---|
| `proxy.enabled` | bool | `false` | Master switch; complete no-op when false |
| `proxy.tunnel_port` | int | `9090` | Sandbox `HTTPS_PROXY` target port (plain-HTTP forward listener is `+1`) |
| `proxy.auto_install` | bool | `true` | Auto-download pinned `iron-proxy` binary |
| `proxy.credential_source` | enum | `env` | `env` \| `bitwarden` |
| `proxy.enforce_on_docker` | bool | `true` | Refuse to start a Docker sandbox if proxy enabled-but-not-running |
| `proxy.allow_env_fallback` | bool | `false` | Opt back into legacy silent host-env fallback when `credential_source: bitwarden` |
| `proxy.upstream_deny_cidrs` | list or `null` | `null` (safe default list) | SSRF deny CIDRs; `[]` opts out entirely |
| `proxy.extra_allowed_hosts` | list | `[]` | Extra allowed upstream hosts beyond bundled defaults; wildcards supported |

### 5.9 CLI commands (from CLI Commands Reference + individual pages)

| Command | Description |
|---|---|
| `hermes config {show,edit,get,set,unset,path,env-path,check,migrate}` | Config management; `get`/`set` reject managed-pinned keys with a named-source error |
| `hermes doctor [--fix]` | Diagnose config/dependency issues; surfaces resolved managed dir + advisory acks |
| `hermes secrets bitwarden {setup,status,token,sync,sync --apply,install,disable}` | Bitwarden lifecycle (alias `hermes secrets bw`) |
| `hermes secrets onepassword {setup,status,token,set,remove,sync,sync --apply,disable}` | 1Password lifecycle (aliases `op`, `1password`) |
| `hermes security audit [--json] [--fail-on] [--skip-venv] [--skip-plugins] [--skip-mcp]` | On-demand OSV.dev supply-chain vulnerability scan |
| `hermes egress {install,setup,start,stop,restart,reload,status,disable,config}` | iron-proxy lifecycle; `setup --from-bitwarden`/`--no-bitwarden`/`--rotate-tokens` |
| `hermes pairing {list,approve,revoke,clear-pending}` | DM pairing management |
| `hermes approvals suggest [--apply N,M] [--json] [--days N] [--min-count N] [--limit N] [--db PATH]` | Mine approval history into allowlist proposals |

---

## 6. Official Examples (verbatim)

### 6.1 Managed Scope directory layout

```text
/etc/hermes/
├── config.yaml     # managed config layer (wins over ~/.hermes/config.yaml)
└── .env            # managed env layer (wins over ~/.hermes/.env + shell)
```

### 6.2 Managed Scope precedence table

| Tier | config.yaml | .env |
| --- | --- | --- |
| 1 | `/etc/hermes/config.yaml` (managed) | `/etc/hermes/.env` (managed) |
| 2 | `~/.hermes/config.yaml` (user) | `~/.hermes/.env` (user) |
| 3 | built-in defaults | pre-existing shell environment |

### 6.3 Managed Scope leaf-level pin example

```yaml
model:
  default: org/standard-model
```

### 6.4 Relocating the managed directory

```bash
export HERMES_MANAGED_DIR=/opt/org/hermes-policy
```

### 6.5 Refusal message (attempted override)

```text
$ hermes config set model.default my/model
Cannot set 'model.default': it is managed by your administrator
(/etc/hermes/config.yaml) and cannot be changed.
```

### 6.6 Administrator setup walkthrough (full)

```bash
sudo mkdir -p /etc/hermes
# Pin some config values for every user on this machine
sudo tee /etc/hermes/config.yaml >/dev/null <<'YAML'
model:
  provider: nous
security:
  redact_secrets: true
YAML
# Optionally pin a shared, non-sensitive env value
sudo tee /etc/hermes/.env >/dev/null <<'ENV'
OPENAI_API_BASE=https://inference.example.com/v1
ENV
sudo chmod 0755 /etc/hermes
sudo chmod 0644 /etc/hermes/config.yaml /etc/hermes/.env
```

### 6.7 Secrets — explicit source ordering

```yaml
secrets:
  sources: [bitwarden]     # optional explicit ordering
  bitwarden:
    enabled: true
    project_id: "..."
```

### 6.8 Secrets — preserve_existing for shared vaults

```yaml
secrets:
  preserve_existing: [FEISHU_APP_SECRET, TELEGRAM_BOT_TOKEN]
```

### 6.9 Bitwarden — non-interactive setup

```bash
hermes secrets bitwarden setup \
  --access-token "$BWS_ACCESS_TOKEN" \
  --server-url https://vault.bitwarden.eu \
  --project-id <project-uuid>
```

### 6.10 Bitwarden — full config defaults

```yaml
secrets:
  bitwarden:
    enabled: false
    access_token_env: BWS_ACCESS_TOKEN
    project_id: ""
    server_url: ""
    cache_ttl_seconds: 300
    encrypted_cache:
      enabled: false
      max_stale_seconds: 0
    override_existing: true
    auto_install: true
```

### 6.11 1Password — full config defaults

```yaml
secrets:
  onepassword:
    enabled: false
    env:
      OPENAI_API_KEY: "op://Private/OpenAI/api key"
      ANTHROPIC_API_KEY: "op://Private/Anthropic/credential"
    account: ""
    service_account_token_env: OP_SERVICE_ACCOUNT_TOKEN
    binary_path: ""
    cache_ttl_seconds: 300
    override_existing: true
```

### 6.12 1Password — systemd EnvironmentFile bootstrap-token delivery

```ini
[Service]
EnvironmentFile=-/home/youruser/.hermes/.op.env
```

### 6.13 Command helper source

```yaml
secrets:
  command:
    enabled: true
    command: "cat /run/user/1000/hermes-secrets.env"
    # or any vault CLI that dumps KEY=VALUE lines:
    # command: "pass show hermes/env"
    # command: "secret-tool lookup service hermes-env"
```

### 6.14 Secret Source Plugin skeleton (abridged; see page for full listing)

```python
class MyVaultSource(SecretSource):
    name = "myvault"          # config section key: secrets.myvault
    label = "My Vault"        # used in startup lines + provenance labels
    shape = "mapped"          # "mapped" (explicit VAR→ref map) or "bulk" (project dump)
    scheme = "mv"             # optional: unique URI scheme you own (mv://...)

    def fetch(self, cfg: dict, home_path: Path) -> FetchResult:
        """Resolve secrets. MUST NOT raise. MUST NOT prompt."""
        ...

    def protected_env_vars(self, cfg: dict):
        # Your bootstrap token — no source (including yours) may ever overwrite it.
        return frozenset({"MYVAULT_TOKEN"})
```

```python
# __init__.py
def register(ctx):
    ctx.register_secret_source(MyVaultSource())
```

### 6.15 Approval config (Security page)

```yaml
approvals:
  mode: smart                     # smart | manual | off
  timeout: 300                    # seconds to wait for user response (default: 300)
  cron_mode: deny                 # deny | approve — what cron jobs do when they hit a dangerous command
  mcp_reload_confirm: true        # /reload-mcp asks before invalidating the MCP tool cache
  destructive_slash_confirm: true # /clear, /new, /reset, /undo prompt before discarding state
```

### 6.16 User-defined deny rules

```yaml
approvals:
  deny:
    - "git push --force*"
    - "*curl*|*sh*"
    - "dd if=* of=/dev/*"
```

### 6.17 Website blocklist (Security page)

```yaml
# In ~/.hermes/config.yaml
security:
  website_blocklist:
    enabled: true
    domains:
      - "*.internal.company.com"
      - "admin.example.com"
    shared_files:
      - "/etc/hermes/blocked-sites.txt"
```

### 6.18 Egress proxy full config block

```yaml
proxy:
  enabled: false
  tunnel_port: 9090
  auto_install: true
  credential_source: env
  enforce_on_docker: true
  allow_env_fallback: false
  upstream_deny_cidrs: null
  extra_allowed_hosts: []
```

### 6.19 Egress proxy quick start

```bash
# 1. Install the iron-proxy binary (pinned version, SHA-256 verified)
hermes egress install
# 2. Run the wizard: generates CA, mints proxy tokens for every provider key
#    in your env, writes proxy.yaml.
hermes egress setup
# 3. Start the proxy daemon
hermes egress start
# 4. Check status
hermes egress status
```

### 6.20 NixOS Managed Mode minimal config (context only)

```nix
{ config, ... }: {
  services.hermes-agent = {
    enable = true;
    settings.model.default = "anthropic/claude-sonnet-4";
    environmentFiles = [ config.sops.secrets."hermes-env".path ];
    addToSystemPackages = true;
  };
}
```

---

## 7. Recommendations Found

Everything the docs explicitly phrase as a recommendation or best practice:

- "Use it for shared, non-sensitive values (an org API base URL, feature defaults) rather than high-sensitivity secrets." — Managed Scope, on the world-readable managed `.env`.
- "In a real deployment this variable should be fixed by the administrator (e.g. baked into the service unit / container image), not left user-settable." — Managed Scope, on `HERMES_MANAGED_DIR`.
- "the admin should check `hermes doctor` to confirm the policy is being applied." — Managed Scope, after a malformed managed-file event.
- "Use `hermes config edit` to review or remove patterns from your permanent allowlist." — Security, Permanent Allowlist tip.
- Gateway Deployment Checklist (10-item recommended list) — Security, Best Practices for Production Deployment: explicit allowlists; container backend; resource limits; secure secret storage with proper file permissions; DM pairing over hardcoded IDs; periodic `command_allowlist` review; set `terminal.cwd`; run as non-root; monitor `~/.hermes/logs/`; run `hermes update` regularly.
- "For maximum security, run the gateway on a separate machine or VM." — Security, Network Isolation.
- "Never commit .env files to version control" / "Keep separate keys for different services" — Security, Securing API Keys.
- "Set `security.tirith_fail_open: false` in high-security environments to block commands when tirith is unavailable." — Security, Tirith section (implied recommendation for stricter postures).
- "Public-facing gateways should leave [`security.allow_private_urls`] off." — Security, SSRF Protection.
- "The command source is the escape hatch for vaults without a bundled integration. If you find yourself wrapping a complex CLI dance in a long script, consider a proper secret-source plugin instead — plugins get caching, provenance labels, and typed config." — Command Helper Secret Source, closing recommendation.
- "The good case for this is multi-machine fleets, shared dev boxes, gateway VPSes, or any setup where you want centralized rotation and revocation across multiple Hermes installations." — Bitwarden and 1Password pages (near-identical closing recommendation on both).
- "For production gateway deployments, use `docker`, `modal`, `daytona`, or `vercel_sandbox` backend to isolate agent commands from your host system. This eliminates the need for dangerous command approval entirely." — Security, tip under Container Bypass.
- "Do not mount real provider credentials into an enforced egress sandbox." — iron-proxy, Security model (What it does NOT protect against).
- "Protect the CA key (it's `0600`, host-only) and the proxy endpoint accordingly." — iron-proxy, Security model.
- "Always use `environmentFiles` with a secrets manager [never Nix `settings`/`environment` for secrets]." — Nix & NixOS Setup, Secrets Management (context-only page, cited for the parallel lesson).

---

## 8. Boundary Notes

- User-tier config keys, the general Configuration Precedence ladder (CLI args → `config.yaml` → `.env` → defaults), and `${VAR}`/`${env:VAR}` substitution syntax belong to `hermes-configuration`; this dossier only captures the point where Managed Scope inserts itself above that ladder.
- `HERMES_HOME` / profile isolation (`hermes-configuration`'s or a profiles-focused skill's territory) — Managed Scope and the Secrets subsystem apply per-process regardless of active profile; not re-derived here.
- Cron job dispatch semantics (`kanban.dispatch_in_gateway`, cron `approvals.cron_mode: deny|approve`) belong to `hermes-kanban`; only cited here because the 1Password bootstrap-token section names it as a context where the token must be present.
- Event hooks belong to `hermes-hooks`; not touched by any page read in this run.
- The skills system, skill security scanning ("Skills Guard"), and the `official/security/1password` *optional skill* (a different feature from the `secrets.onepassword` startup-injection mechanism captured here) belong to `hermes-skills`.
- Session/checkpoint storage, `/rollback`, and the shadow git store belong to `hermes-sessions`; only the "cross-session isolation" security-layer bullet was noted in passing.
- The `hermes` CLI command surface generally belongs to `hermes-cli`; this dossier cites specific subcommands (`hermes config`, `hermes doctor`, `hermes secrets ...`, `hermes egress ...`, `hermes security audit`) only insofar as they are the operational interface to Managed Scope/Secrets/Security, not as a full CLI reference capture.
- The Codex App-Server Runtime page's "managed block" (a marker-delimited section of `~/.codex/config.toml` regenerated by `hermes codex-runtime migrate`) is an unrelated, differently-scoped use of the word "managed" — not Hermes Managed Scope, and not owned by this skill or clearly by any other; flagged for disambiguation only.

---

## 9. Gaps & Open Questions

- **No worked example combining Managed Scope with the Secrets subsystem.** The docs never show, e.g., pinning `secrets.bitwarden.enabled: true` and `secrets.bitwarden.project_id` at `/etc/hermes/config.yaml` for a fleet, nor confirm whether a managed `secrets.*` config key is honored with the same "managed wins" semantics as other keys. INFERENCE (not stated in docs): given "leaf-level" merge and no stated exception, `secrets.bitwarden.project_id` pinned in `/etc/hermes/config.yaml` should behave like any other pinned key, but this is not verified in any official example.
- **No native macOS/Windows managed-directory equivalent.** Explicitly listed as out of scope for v1 ("Native managed locations on macOS and Windows (v1 is Linux/POSIX-first)"). Any stage 080 fleet on non-Linux hosts has no first-class Managed Scope story from official docs.
- **No `managed.d/` fragment directories, no signed/integrity-checked managed files, no MDM delivery, no group-scoped secret permissions** — all explicitly listed as future work, not present in v1. A security review should not assume any of these exist.
- **The "formula" reference is under-documented.** The Managed Scope callout mentions "declarative-distro / formula" installs as a parallel package-manager-lock concept, and web search surfaced only a passing "Platform Support" page reference to a community/unsupported Homebrew formula (`brew install hermes-agent`), with no docs page describing a Homebrew-specific config-lock mechanism analogous to NixOS's `HERMES_MANAGED=true`. This claim (that Homebrew has an equivalent lock) could not be confirmed from any allowed source — recorded as a gap, not asserted.
- **No documented interaction between Managed Scope and the egress proxy (iron-proxy).** Neither page cross-references the other; it is unclear from the docs whether `proxy.*` keys can be fleet-pinned via Managed Scope the same way `model.*` or `security.*` keys can. Not stated either way.
- **No documented audit-log or compliance-reporting surface specific to Managed Scope itself** (e.g., no "list of all pin-override attempts" log format is documented) — `hermes doctor` reports pinned-key counts and the resolved directory, but no attempt-logging format is described.
- **iron-proxy logging split (`audit.log` vs `iron-proxy.log`) is a forward-looking placeholder in the current pinned binary version (v0.39.0)** — the docs are explicit that `audit.log` is empty today and monitoring should point at `iron-proxy.log` instead; a stage 080 review should not wire tooling to `audit.log` yet per the docs' own instruction.
- **No documented behavior for what happens if both a managed `config.yaml` AND `configFile`/NixOS "Managed Mode" are present simultaneously** beyond the one-line "the two are independent and can coexist" — no worked example of the combined precedence.

---

## 10. Suggested SKILL.md Inputs (for the reviewer — not an edit)

**Key concepts** (each citing the row/quote it derives from):
- Managed Scope = per-key pin via `/etc/hermes/{config.yaml,.env}`, enforced by filesystem permissions only, distinct from whole-config-lock installs (Normative Statements rows 1–3; §6.1–6.3).
- Precedence: managed > user > built-in/shell, leaf-level merge, with the one documented inversion (managed pins beat shell env) (Normative Statements rows 5, 8; §6.2).
- Security ceiling: v1 is a "management-convenience boundary," not a sandbox against the agent, root, or a user with directory write access (Normative Statements rows 12–14, plus the iron-proxy and File-Write-Safety "defense-in-depth, not a sandbox" restatements — Normative Statements rows 25 and 29).
- Secrets subsystem = pull-at-startup model with a documented multi-source precedence ladder and a cross-source bootstrap-token-protection invariant (Normative Statements rows 15–17, 27; Reference Table 5.2–5.5).
- Fleet framing is explicit in the docs for Bitwarden/1Password ("multi-machine fleets ... centralized rotation and revocation") and for the egress proxy (sandboxed worker isolation) — Normative Statements rows 18, 26; Recommendations §7.

**Workflow steps** (deriving from Method/Workflow-relevant normative content):
1. Before pinning anything, run `hermes doctor` to see current managed-dir resolution and pinned-key counts (Reference Table 5.1 CLI row; Normative Statements row 11).
2. Write `/etc/hermes/config.yaml` / `/etc/hermes/.env` with `0755`/`0644` root ownership per the official walkthrough (§6.6); never put high-sensitivity secrets in the managed `.env` (Normative Statements row 13).
3. If pinning `HERMES_MANAGED_DIR`, bake it into the service unit/container image, not a user-editable path (Normative Statements row 6).
4. For provider credentials at fleet scale, prefer a bundled secret source (Bitwarden or 1Password) over the managed `.env` for anything sensitive, citing the explicit "good case: multi-machine fleets" framing (Reference Tables 5.3–5.4; Recommendations §7).
5. For sandboxed/Docker worker fleets, evaluate the egress proxy (iron-proxy) to keep real provider keys out of the sandbox entirely (Normative Statements row 24; §6.18–6.19); note the Docker-only v1 scope limitation (Normative Statements row 25 sibling: intro quote "wires the egress proxy into the Docker backend only").
6. Apply the Gateway Deployment Checklist as a fleet-readiness gate (Recommendations §7, 10-item list).
7. Validate that a standard seat cannot override a pinned key by attempting `hermes config set <pinned-key> <value>` and expecting the documented refusal text (§6.5; Normative Statements row 9).

**Validation commands** (all sourced from the reference tables above):
- `hermes doctor` — confirms managed dir + pinned-key count + advisory status (Reference Table 5.1, 5.7).
- `hermes config` — shows the managed-source header and pinned keys (Reference Table 5.1).
- `hermes config set <key> <value>` against a pinned key — expect the exact refusal text in §6.5 (Normative Statements row 9).
- `hermes secrets bitwarden status` / `hermes secrets onepassword status` — confirm secret-source health for a fleet worker (Reference Tables 5.3–5.4).
- `hermes security audit --fail-on high` — supply-chain check appropriate for a CI/fleet-rollout gate (Reference Table 5.9).
- `hermes egress status` — confirm the egress proxy is enforcing token-swap isolation for sandboxed workers (Reference Table 5.9; §6.19).

---

## Run B corroboration and unique findings (reviewer merge, 2026-08-12)

Run B (different model, blind, same prompt) corroborated the entire shared
core verbatim: Managed Scope mechanism/precedence/v1 limits, the secrets
multi-source ladder and bootstrap-token invariant, all three secret-source
config tables (identical keys and defaults), the Security checklist, and
the NixOS Managed Mode distinction. Unique findings merged from Run B:

### Doc inconsistencies (all reviewer-verified)

- The Environment Variables reference
  (`/docs/reference/environment-variables`) does NOT list
  `HERMES_MANAGED_DIR` — it is documented only on the Managed Scope page.
  (`HERMES_HOME` IS listed there: "Override Hermes config directory
  (default: `~/.hermes`). Also scopes the gateway PID file and systemd
  service name, so multiple installations can run concurrently".)
- The Configuration page's 4-tier precedence list (CLI args > config.yaml >
  .env > defaults) does not show the managed tier; only the Managed Scope
  page documents where it inserts.
- Managed Scope and Secrets pages are absent from the curated
  `/docs/llms.txt` index (`/llms.txt` at the site root 404s) — discovery
  fragility for agents that only load the curated index.

### Credential Pools (`/docs/user-guide/features/credential-pools`)

QUOTE: "Borrowed runtime secrets (for example env vars,
Bitwarden/Vault/keyring/systemd references, and custom config values) are
reference-only at the `auth.json` boundary. Hermes can use the resolved
value in memory for the current run, but it persists only metadata such as
the source ref, label, status, request counters, and a non-reversible
fingerprint."

### Additional keys/facts from Run B

- `secrets.<plugin>.timeout_seconds` — per-source wall-clock timeout,
  orchestrator default 120s (Secret Source Plugins page).
- Managed Scope intro names concrete fleet pin examples: "the model
  provider, a shared API base URL, or `security.redact_secrets: true`".
- `HERMES_MANAGED_DIR` "is never persisted to any `.env` by Hermes"
  (bootstrap-only knob).
- Bitwarden bootstrap token guidance: "treat it like a high-value bearer
  token — store it in `.env` (not `config.yaml`)".
- 1Password bootstrap token delivery: "In `~/.hermes/.env` (recommended)",
  `~/.hermes/.op.env` (0600, gitignored), or systemd `EnvironmentFile`.

### Placeholder contradiction caught by Run B (resolved in SKILL.md v1.0.0)

The placeholder said secrets go "never in writable seat homes". Official
docs contradict this: bootstrap tokens belong in the seat's
`~/.hermes/.env` at `chmod 600`, and the warning against secrets in a
writable location applies to the world-readable MANAGED `.env`
(`/etc/hermes/.env`), not the seat file. SKILL.md v1.0.0 states the
official baseline and notes that project overlays (e.g. the stage 080
scaffold's stricter rules) apply inside their own scope.

### Left open (both runs agree)

- Managed Scope × secret-source interaction for the same env key:
  undocumented.
- Managed-pinning `secrets.*` blocks: leaf-merge suggests yes; no official
  example (INFERENCE, not fact).
