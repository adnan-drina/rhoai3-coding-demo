---
name: hermes-managed-scope
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when working with Hermes Managed Scope in stage 080: admin-tier config
  and secret pins under /etc/hermes, pin precedence over user seats and
  shell, fleet secret handling via vault sources (Bitwarden, 1Password,
  command helper), egress credential isolation, and production security
  posture. Do NOT use for user-tier config keys and precedence below the
  managed layer (use hermes-configuration) or the full CLI reference (use
  hermes-cli).
---

# Hermes Managed Scope

Use this skill for any stage 080 change touching admin-tier pins, fleet
secret delivery, or worker-fleet security posture.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction
(two independently-corroborated research dossiers plus reviewer
verification). Official Hermes Agent documentation (Nous Research) is the
product authority; every claim in a PR must cite its section.

## Key Concepts

### The mechanism

Managed Scope lets an administrator "push a baseline of configuration and
secrets that a standard (non-root) user cannot override" via a system-level
directory, default `/etc/hermes/{config.yaml,.env}` — root-owned, dir
`0755`, files `0644`. Both files are optional; absence means "no managed
scope". Relocate with `HERMES_MANAGED_DIR` (containers / non-`/etc`), but
bake that variable into the service unit or container image — a user who
can set it can repoint managed scope at a directory they control.

### Precedence

For exactly the keys it pins: **managed > user `~/.hermes` > built-in
defaults / shell**. Merging is leaf-level — pinning `model.default` does
not freeze the rest of `model.*`. Managed pins deliberately beat the shell
environment too — the one documented inversion of the usual
"env overrides config.yaml" rule. Everything unpinned stays fully
user-controlled. Two doc traps: the Configuration page's 4-tier precedence
list does NOT show the managed tier, and the Environment Variables
reference does NOT list `HERMES_MANAGED_DIR` — the Managed Scope page is
the authority for both.

### Enforcement ceiling (v1)

"Enforcement is filesystem permissions only" — a user with directory write
access, or Hermes running as root, makes managed scope advisory. It is "a
management-convenience boundary against a normal user, not an un-escapable
sandbox": the agent's own tools are not hard-blocked from managed values.
Explicitly out of scope for v1: hard agent boundary, macOS/Windows native
locations, `managed.d/` fragments, signed managed files, MDM delivery,
group-scoped secret permissions. Do not assume any of these exist. Distinct
from the NixOS `HERMES_MANAGED`/`.managed` whole-config lock — independent
mechanisms that can coexist.

### Where secrets actually go

- **Managed `.env` is world-readable (0644)** — official guidance: shared,
  non-sensitive values only (org API base URL, feature defaults), never
  high-sensitivity secrets.
- **Provider keys at fleet scale**: vault sources — Bitwarden or 1Password
  ("the good case ... multi-machine fleets ... centralized rotation and
  revocation"), or the command helper for unbundled vaults. The bundled set
  is deliberately closed; anything else is a plugin.
- **Bootstrap tokens** (`BWS_ACCESS_TOKEN`, `OP_SERVICE_ACCOUNT_TOKEN`)
  live in the seat's `~/.hermes/.env` (or `.op.env` / systemd
  `EnvironmentFile`) with `chmod 600` — official baseline; they must reach
  `os.environ` of every spawned context (cron, subprocess, containers),
  not just interactive shells.
- **Multi-source ladder**: own `.env`/shell wins unless a source sets
  `override_existing: true` (Bitwarden default); mapped beats bulk; first
  source wins; no source can ever overwrite another's bootstrap token.
- **Credential pools** store only metadata and a non-reversible fingerprint
  at the `auth.json` boundary — never the raw borrowed key.

### Sandboxed fleets: egress proxy

For Docker-sandboxed workers, the iron-proxy egress feature keeps real
provider keys out of the sandbox entirely — "the sandbox holds opaque proxy
tokens, never the real keys". Docker backend only in the current release
(not Modal/Daytona/SSH/Singularity); `proxy.enforce_on_docker: true`
(default) refuses to start a sandbox if the proxy is enabled but not
running. Defense-in-depth for sandbox compromise, not host compromise.

## Workflow

1. Classify the pin surface: managed `config.yaml` for non-secret policy;
   managed `.env` only for non-sensitive shared env; vault sources for
   provider keys.
2. Author `/etc/hermes` per the official walkthrough (root-owned,
   `0755`/`0644`); for containers, set `HERMES_MANAGED_DIR` in the image
   or unit, never user-space.
3. Wire Bitwarden/1Password for fleet provider keys; bootstrap token in
   the seat secret file at `0600`; verify it reaches non-interactive
   contexts.
4. Apply on next start; malformed managed files are logged loudly and
   ignored (fail-open) — always confirm with `hermes doctor`.
5. Verify a standard seat cannot override a pinned key (expect the
   documented refusal naming the managed path).
6. Gate fleet rollouts on the official 10-item Gateway Deployment
   Checklist (explicit allowlists, container backend, non-root, `0600`
   secrets, resource limits, updates).
7. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes doctor                          # resolved managed dir + pinned key counts
hermes config                          # header names managed source + pinned keys
hermes config set <pinned.key> x       # expect: "Cannot set '<key>': it is
                                       # managed by your administrator (...)"
hermes secrets bitwarden status        # vault source health (or onepassword)
hermes egress status                   # proxy enforcing token-swap (Docker fleets)
stat -c '%a %U' /etc/hermes /etc/hermes/*   # expect 755/644 root
ls -l ~/.hermes/.env                   # expect 600
```

Also confirm the worker process is not root — root makes every pin
advisory.

## Pitfalls

- Pinning secrets in the managed `.env` — it is world-readable by design;
  any local user can read it.
- Trusting the Configuration page's precedence list for managed fleets —
  it omits the managed tier; cite the Managed Scope page instead.
- Leaving `HERMES_MANAGED_DIR` user-settable — defeats the feature;
  `hermes doctor` makes a redirect visible.
- Assuming a malformed managed file blocks startup — it never does
  (fail-open); policy silently absent until `hermes doctor` is checked.
- Interactive-only vault auth (`op signin` in `.bashrc`) — cron jobs and
  spawned workers won't inherit it and fall back to stale `.env` values
  with only a warning.
- The Managed Scope × secret-source interaction for the SAME env key is
  undocumented — do not assert which wins; flag it in review instead.
- Whether `secrets.*` blocks can themselves be managed-pinned is
  undocumented (leaf-merge suggests yes, but no official example) — treat
  as inference, not fact.
- Project overlays (e.g. the stage 080 scaffold's rules) may be stricter
  than this official baseline — the scaffold's own AGENTS.md wins inside
  the scaffold.

## Related Skills

- `hermes-configuration` — user-tier keys and the precedence ladder the
  managed layer sits above.
- `hermes-cli` — full reference for `hermes doctor`/`config`/`secrets`.
- `rhoai-maas-governance` — the MaaS control point fleet pins integrate
  with.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
