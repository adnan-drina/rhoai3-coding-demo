# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages; Managed Scope limitations labeled "v1"; iron-proxy binary pinned v0.39.0 |
| Chapter or page title | Managed Scope; Secrets (+ Bitwarden, 1Password, Command helper); Security; Secret Source Plugins; Egress proxy (iron-proxy); Credential Pools |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/managed-scope |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/secrets/ |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/secrets/bitwarden |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/secrets/onepassword |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/secrets/command |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/security |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/secret-source-plugin |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/egress/iron-proxy |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/credential-pools (auth.json fingerprint rule only) |
| Documentation category | Using Hermes / Features / Developer Guide |
| Capture date | 2026-08-12 |
| Capture method | Two blind parallel research dossiers by different models (`source-analysis/hermes/hermes-managed-scope-capture-A.md` and `-B.md`); shared core corroborated verbatim; reviewer spot-verified shared core plus each run's unique findings against live pages on 2026-08-12 |

## Captured Sections

- Managed Scope: mechanism, `/etc/hermes` layout and modes, precedence
  (managed > user > defaults/shell, leaf-level merge, shell inversion),
  `HERMES_MANAGED_DIR`, refusal UX, admin setup walkthrough, v1 security
  model and explicit non-goals.
- Secrets: multi-source precedence ladder, bootstrap-token cross-source
  invariant, `preserve_existing`, `profile_alias`; full config/CLI tables
  for Bitwarden, 1Password, and the command helper; plugin contract.
- Security: 8-layer model, approvals keys, Gateway Deployment Checklist,
  `security.redact_secrets`, secret-file hygiene (`chmod 600`).
- Egress proxy (iron-proxy): token-swap guarantee, Docker-only scope,
  `proxy.*` keys, `enforce_on_docker` fail-closed default.
- Credential Pools: borrowed secrets are fingerprint-only in `auth.json`.

## Doc inconsistencies found (cite Managed Scope page as authority)

- The Configuration page's 4-tier precedence list omits the managed tier.
- The Environment Variables reference omits `HERMES_MANAGED_DIR`.
- Managed Scope and Secrets pages are absent from `/docs/llms.txt`.

## Source Boundaries

This skill captures: admin-tier pinning, pin precedence and enforcement,
fleet secret delivery (vault sources, bootstrap tokens), and worker-fleet
security posture. User-tier precedence below the managed layer belongs to
`hermes-configuration`; full CLI reference to `hermes-cli`; the NixOS
`HERMES_MANAGED` whole-config lock is a distinct mechanism (noted for
disambiguation only).

## Known Open Items

- Managed Scope × secret sources: which wins when the managed `.env` and a
  vault source supply the SAME env key is undocumented.
- Whether `secrets.*` config blocks can be managed-pinned is undocumented
  (leaf-merge suggests yes; no official example).
- No macOS/Windows managed locations, no signed/MDM delivery, no
  `managed.d/` fragments in v1 (explicit official non-goals).
- No Managed Scope-specific audit/attempt-log format documented.
- iron-proxy `audit.log` is a placeholder in v0.39.0 — monitor
  `iron-proxy.log` per the docs.
