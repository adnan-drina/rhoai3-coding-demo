---
name: project
skill-group: Project Structure
skill-prefix: project-
applies-to:
  - AGENTS.md
  - .agents/**
  - .cursor/**
  - README.md
  - stages/**
  - scripts/**
  - "**/PLAN.md"
  - "**/PLAN-*.md"
---

# Project Structure

Use the project-related skills as the source of truth for work that changes the
repository layout, coding discipline, change conventions, or shared agent
guidance:

- `.agents/skills/maintain-rules-and-skills/SKILL.md`
- `.agents/skills/prepare-pr-summary/SKILL.md`
- `.agents/skills/review-gitops-change/SKILL.md`
- `.agents/skills/update-demo-docs/SKILL.md`

## Project Purpose

This repository demonstrates a governed enterprise AI developer platform on
Red Hat OpenShift. The demo combines private/local models, governed external
model access, GitOps, Dev Spaces, Migration Toolkit for Applications, and
Developer Hub to support AI-assisted development and modernization.

## Product and Version Posture

The demo evolves across Red Hat product releases and early-access features. Do
not invent or normalize versions in documentation. Use the versions currently
implemented by the manifests and scripts.

Current target posture:
- Red Hat OpenShift Container Platform 4.20
- Red Hat OpenShift AI 3.3 plus selected 3.4 early-access MaaS capabilities where explicitly documented
- Red Hat OpenShift GitOps for Argo CD based reconciliation
- Red Hat OpenShift Dev Spaces for cloud development environments
- Migration Toolkit for Applications 8.1 for modernization analysis and Developer Lightspeed
- Red Hat Developer Hub 1.9 for the developer portal
- Red Hat build of Keycloak where used by MTA authentication flows

If changing a version, update the manifests, validation logic, README narrative,
operations notes, and references together.

## Absolute Priority: Official Documentation Alignment

- Treat official Red Hat documentation for the relevant product versions as the source of truth.
- Do **not** invent CR fields, API versions, annotations, or operator configurations.
- If unsure, say what you need to verify and propose the verification command.

## Demo Reliability Over Novelty

- Prefer stable, boring solutions that consistently work.
- Every change must be reproducible from GitOps (`gitops/`) and must include clear verification steps.

## Coding Discipline

Behavioral guardrails for all coding tasks. Bias toward caution over speed; for
trivial tasks, use judgment.

### Think Before Coding

- State assumptions explicitly before implementing. If uncertain, ask or propose a verification command.
- If multiple approaches exist, present them with tradeoffs; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and name what's confusing.

### Simplicity First

- No features beyond what was asked.
- No abstractions for single-use code.
- No speculative "flexibility" or "configurability" that wasn't requested.
- Do not create new documentation files unless explicitly requested or clearly required by a new cross-cutting workflow. Prefer updating existing docs first.
- If you write 200 lines and it could be 50, rewrite it.

### Surgical Changes

When editing existing code:
- Don't go on unrelated cleanup sprees, but fix obvious issues (bugs, stale comments) adjacent to your changes.
- Don't refactor things that aren't broken.
- Match existing code style unless it conflicts with project rules.

When your changes create orphans:
- Remove imports, variables, functions, and manifest entries that your changes made unused.
- When removing a resource from `kustomization.yaml`, also delete the unreferenced file.

The test: every changed line should trace directly to the user's request.

### Goal-Driven Execution

Transform tasks into verifiable goals before starting:

```
1. [Step] -> verify: [oc command or check]
2. [Step] -> verify: [oc command or check]
3. [Step] -> verify: [oc command or check]
```

Loop until verified. Weak criteria ("make it work") require clarification; ask for it.

### Human Review Boundary

AI-generated code must be reviewed by a human before merge. Do not add
`Signed-off-by` trailers. If asked to prepare commit messages or PR text,
include AI assistance disclosure but leave human sign-off to the contributor.

### Validation Honesty

If a change requires a live OpenShift cluster for validation and one is not
available, say so clearly:

> Not validated against a live OpenShift cluster. Static review only.

Do not claim that a GitOps, OpenShift, MaaS, model-serving, or gateway change
works unless it was actually validated or is directly covered by existing tested
patterns.

## Change Output Conventions

When responding with changes, always include:
1. **Files to change** (exact paths)
2. **What to add/modify** (small diffs or full file content if short)
3. **How to apply** (from GitOps folder, or `deploy.sh`, or exact commands)
4. **How to validate** (deterministic `oc` checks or `validate.sh`)

### Code and Documentation Alignment

Behavior and documentation MUST stay aligned.

When changing implemented behavior, update all affected surfaces in the same change:
- GitOps manifests under `gitops/`
- deployment scripts under `stages/*/deploy.sh`
- validation scripts under `stages/*/validate.sh`
- educational READMEs when the architecture, value story, demo flow, trust boundary, product version, or references change
- `docs/OPERATIONS.md` when deployment, validation, or day-2 operation changes
- `docs/TROUBLESHOOTING.md` when a known failure mode, diagnostic command, or recovery path changes

Documentation must not claim a capability is implemented unless it is backed by
manifests/scripts and, where practical, validation checks.

When changing workarounds, limitations, or validated status, update `BACKLOG.md`
in the same change.

### Branching Strategy: GitHub Flow + Trunk-Based Development

`main` is the trunk. ArgoCD syncs from `main`. All work targets `main`.

When to commit directly to main:
- Single-file fixes, typos, small updates
- Documentation-only changes (except agent system files)
- Changes you can describe in one commit message

When to use a feature branch:
- Multi-stage changes spanning multiple files or stages
- Parallel agent worktree work
- Changes that need review before merging
- Changes to `.agents/`, `.cursor/`, `AGENTS.md`, `CONTRIBUTING.md`, `.github/` templates, or `docs/AI_COLLABORATION.md`

### Git Commit Conventions

Use conventional commit messages: `type(scope): description`
- **Types:** `feat`, `fix`, `docs`, `refactor`, `chore`, `ci`
- **Scope:** Use the stage number for stage-specific changes, component name for cross-cutting changes
- Keep the subject line under 72 characters
- Never force-push to `main`

### AI Assistance Disclosure in PRs

Every PR must include AI assistance disclosure using the PR template. For
security-sensitive changes, always include explicit risk and rollback notes.

## Rules and Skills Governance

Treat changes to rules and skills like source code.

### Rule Versus Skill

Create or edit a **rule** when the guidance should apply automatically.
Create or edit a **skill** when the guidance is a repeatable workflow invoked for a specific task.

### Shared Versus Local

A shared rule or skill may be committed only when it applies to all
contributors, contains no secrets, is stable enough to maintain, and can be
reviewed.

### Quality Bar

Rules should be: short, specific, durable, enforceable, non-duplicative.

Skills should include: when to use, required inputs, files to inspect, steps to
follow, validation commands, expected output, things the agent must not do.

## Plan Documents (PLAN.md)

When creating or updating `PLAN.md` files:

1. **Conceptual Foundation** - connect features to enterprise value
2. **Layered Architecture Analysis** - infrastructure, platform, application, governance
3. **Design Decisions** - highlight non-default choices
4. **Implementation Checklist** - coding hand-off for agents
5. **References** - anchored to official Red Hat documentation
6. **Review Needed** - force clarification before implementation
