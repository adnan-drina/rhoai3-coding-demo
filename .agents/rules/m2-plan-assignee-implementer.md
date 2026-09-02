---
name: m2-plan-assignee-implementer
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**/AGENTS.md
  - gitops/stages/050-advanced-app-platform/base/devspaces/**
---

# M2 PLAN is implementer; dest AGENTS.md must not say orchestrator

Architect `123104Z`: M2 PLAN seat = implementer by design. dest
`orchestrator.yaml.template` disables `file` / `terminal` /
`code_execution` / `skills`. dest `AGENTS.md` L118 still says “M2 and
mint-verifier cards use `--assignee orchestrator`”. dest-4 M2
`t_c46275ae` ran implementer and **succeeded**; nothing noticed
(Operator `104946ZO`).

A convention that can be violated with no consequence is not a control.

## Non-negotiable

1. **Retire** dest `AGENTS.md` “M2 uses orchestrator”. Replace with:
   M2 PLAN → `--assignee implementer`; mint-verifier → `orchestrator`;
   M3 stories → `implementer`; **M4 VERDICT → `implementer`**. Paths
   table must match. dest `orchestrator.yaml.template` disables `file`,
   `terminal`, `code_execution`, and `skills` — that seat cannot run
   `check-release-readiness`. Operator `105656ZO` inferred orchestrator;
   OBJECT that argv.
2. Do **not** enforce orchestrator on M2 PLAN. That would contradict
   `123104Z` and break a green dest-4 card.
3. Do not add a dest-4 retroactive assignee KEEP. dest-5 golden text is
   the control. A later mint-time KEEP that M2 PLAN is implementer is
   optional after the text lands — not a dest-4 reopen.
4. `Lead:amend-agents-md-m2-plan-vs-mint-seat` remains load-bearing until
   dest `AGENTS.md` matches this rule.

Official cite: `.agents/skills/hermes-kanban/` worker lanes (`--assignee`
is the lane). Orchestrator fan-out is not the M2 PLAN implementer.
