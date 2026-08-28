# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | procedural (rolling `origin/main`; check `hermes version` vs GitHub releases). Point-in-time anchor at capture: v0.20.0 "The Herald Release", tag v2026.8.3 (2026-08-03) |
| Chapter or page title | llms.txt (positioning + index); User Stories; Quickstart; Installation; Platform Support; Learning Path; Updating; Nix Setup; Termux; Features Overview; the ten mechanism-comparison feature pages; Desktop/TUI/CLI surface pages |
| Source URL | https://hermes-agent.nousresearch.com/docs/llms.txt (first-party positioning paragraph) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/overview (canonical feature inventory) |
| Source URL | https://hermes-agent.nousresearch.com/docs/getting-started/platform-support (tier matrix) |
| Source URL | https://hermes-agent.nousresearch.com/docs/getting-started/quickstart |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-stories (curated COMMUNITY quotes — never cite as Nous positioning) |
| Source URL | mechanism-comparison pages: features/{memory, kanban, delegation, goals, hooks, skills, plugins, personality, cron, context-files} — full ~25-URL pin list in the dossier §2 |
| Documentation category | Getting Started / Features / Using Hermes |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-about-capture.md`); reviewer re-verified the llms.txt positioning paragraph, the three tier-definition sentences, the Docker-update note, and the Goals-vs-Kanban quotes verbatim against live sources on 2026-08-12; feature inventory cross-mapped against the seven implemented sibling skills |

## Captured Sections

- Positioning: llms.txt paragraph (only first-party prose); user-stories
  taxonomy (community voice, flagged as such).
- Feature inventory: the full Features Overview five-category list (~35
  rows) with per-row official quotes, URLs, and sibling-skill ownership.
- Platform matrix: Tier 1/2/Unsupported with exact tier language; four
  front ends; Windows native vs WSL2 parity; Nix three-level model;
  Termux tested bundle.
- Mechanism selection: TEN documented comparisons quoted verbatim —
  session_search vs memory; kanban vs delegate_task; delegate_task vs
  execute_code; /goal vs kanban; the four hook systems; SOUL.md vs
  AGENTS.md; SOUL.md vs /personality; bundles vs individual skills;
  NixOS native vs container; the pluggable-interfaces routing table.
- Getting-started shape, setup modes (incl. Blank Slate minimal-trust
  baseline), versioning-as-procedure, 64K minimum context constraint.

## Ownership decisions (reviewer)

- Curator: owned by `hermes-skills` (its capture covers the curator in
  full) — the dossier's provisional assignment is CONFIRMED.
- `hermes egress`/secrets semantics: `hermes-managed-scope`.
- Checkpoints: `hermes-sessions`.

## Consolidated taxonomy gaps (features with no owning hermes-* skill)

Persistent Memory (+ Memory Providers/Honcho); MCP;
Plugins; Context Files;
Provider Routing/Fallback/Credential Pools; API
Server; ACP; Voice/Vision/Browser/Image-gen/TTS; Batch Processing; Cron.
These are documented product features flagged as "not yet covered by a
sibling skill" — candidates for family growth, to be added only on
explicit decision, not unprompted. (Closed 2026-08-12 on maintainer
request: Tools & Toolsets → `hermes-tools`; Delegation →
`hermes-delegation`; Persistent Goals → `hermes-goals`;
Personality/SOUL.md → `hermes-personality`.)

## Supplementary non-official sources (segregated in openshift-deployment.md)

| Source | Nature | Captured |
|---|---|---|
| https://developers.redhat.com/articles/2026/06/02/deploy-hermes-agent-openshift-ai-vllm-model-serving | Red Hat Developers ARTICLE (blog-tier, not docs.redhat.com product docs) | 2026-08-12 |
| https://github.com/aicatalyst-team/hermes-openshift | Community repo (manifests read directly; 2026-06-02 vintage — predates the v0.20.0 anchor) | 2026-08-12 |

Reviewer cross-checked both against the official extractions: reusable
parts and six verified conflicts are documented in
`references/openshift-deployment.md`. Verified during this check:
`OPENAI_BASE_URL`, `GATEWAY_ALLOW_ALL_USERS`, `HERMES_HOME` are official
env vars; `LLM_MODEL` and `GATEWAY_PORT` are absent from the official
Environment Variables reference (repo-specific).

## Known Open Items

- Messaging-platform count is imprecise across sources (llms.txt "21+"
  vs a larger gateway table) — reconcile with a full fetch of
  /docs/user-guide/messaging/ before citing a number.
- MCP page only lightly read (orientation slice); depth unowned.
- No first-party audience/persona statement exists beyond llms.txt.
