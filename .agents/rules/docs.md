---
name: docs
skill-group: Documentation
skill-prefix: docs-
applies-to:
  - README.md
  - "**/README.md"
  - "**/README.mdx"
  - docs/OPERATIONS.md
  - docs/TROUBLESHOOTING.md
  - docs/**/*.md
---

# Documentation Standards

Use the documentation-related skills for work that changes README files, operations docs, or troubleshooting guides:

- `.agents/skills/project-documentation-authoring/SKILL.md` — authoring and structuring READMEs
- `.agents/skills/update-demo-docs/SKILL.md` — consistency checks after changes
- `.agents/skills/demo-operations-docs/SKILL.md` — operational documentation

## Golden Rule: Read Before You Write

Before implementing a change, consult the relevant stage README, GitOps manifests, scripts, and operations docs. The documentation describes the intended demo story; the manifests and scripts describe the implemented behavior.

## Documentation Sources

| Source | Purpose | When to consult |
|--------|---------|-----------------|
| `README.md` | Workshop landing article, architecture story, product map | Overall platform narrative |
| `stages/NNN-*/README.md` | Stage educational article and demo explanation | Before modifying a stage |
| `docs/OPERATIONS.md` | Deployment, validation, GitOps operation, day-2 notes | When changing deploy/validate behavior |
| `docs/TROUBLESHOOTING.md` | Symptom-based diagnostics and recovery | When fixing a failure mode |
| `stages/*/deploy.sh` | Executable deployment entrypoint | Before changing installation |
| `stages/*/validate.sh` | Executable readiness check | Before claiming stage health |
| `gitops/**` | Declarative source of truth | Before documenting platform behavior |

## Content Placement

| Content type | Put it here |
|--------------|-------------|
| Why the stage matters, what it teaches, Red Hat product value | Stage README |
| Workshop / project architecture and trust boundaries | Root README or stage README |
| Stage-local implementation architecture | That stage's directory. Stage 080: `stages/080-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md`. Do not lift it into `docs/` or repo root; it is not the workshop SAD. |
| Stage 080 demo walkthrough | `stages/080-ai-autonomous-migration/README.md` |
| Deployment order, script behavior, validation commands | `docs/OPERATIONS.md` |
| Failure symptoms, root causes, diagnostic commands, recovery | `docs/TROUBLESHOOTING.md` |
| Cluster-specific commands for repeated use | Script, then reference from ops docs |
| Future ideas or non-implemented enhancements | README section marked as future/deferred |

Do not turn stage READMEs into runbooks.

## Stage README Standard

Each stage README is an educational artifact first. Readers should understand the "why, what, how, and so what" even without running the demo.

### Primary Audience

Enterprise architects, solution architects, platform engineers, and developer experience teams evaluating Red Hat OpenShift AI for regulated or security-sensitive software development use cases.

### Required Structure

```markdown
# Stage NNN: Capability Name

## Why This Matters

## Architecture

## What This Stage Adds

## What To Notice And Why It Matters

## How Red Hat And Open Source Make It Work

## Trust Boundaries

## Red Hat Products Used

## Open Source Projects To Know

## Deploy And Validate

## References

## Next Stage
```

### Narrative Principles

- Lead with this demo's storyline, not with external articles
- Explain why the capability matters for private and governed AI coding
- Make trust boundaries, credentials, and data movement explicit
- Use official Red Hat product terminology

### Red Hat Product Requirements

Every stage README must clearly identify relevant Red Hat products and explain their role. Use official product names and link to product pages.

### Trust Boundary Language

Approved:
- "Private local models keep prompts and code inside the OpenShift platform boundary."
- "Governed external models are centrally controlled, but prompts are still processed by the external provider."

Avoid:
- "All AI traffic is private" when external models are present
- Claims of EU AI Act compliance (say the architecture supports controls and readiness)

## Root README Standard

The root README is a workshop landing article. It must explain the enterprise platform pattern before operational details.

Required sections: Why This Workshop Exists, Architecture, What We Are Building, What The Demo Shows, Why This Is Worth Knowing, How Red Hat And Open Source Make It Work, Trust Boundaries, Red Hat Products Demonstrated, Open Source Projects, Running The Workshop, Repository Map, References.

## Operations Documentation

| File | Responsibility |
|------|----------------|
| `docs/OPERATIONS.md` | Deployment order, validation strategy, GitOps operations |
| `docs/TROUBLESHOOTING.md` | Failure symptoms, causes, diagnostics, recovery |

### Troubleshooting Entry Template

```markdown
## <Symptom>

**Where it appears:** <stage/component>

**Likely cause:** <short explanation>

**Check:**
<diagnostic command>

**Recover:**
<safe recovery command>

**Related docs:** <link>
```

## Version-Sensitive Notes

Tag version-sensitive information explicitly. When official documentation conflicts with the implementation, document the conflict and include a verification command.

## Official Docs Remain The Source Of Truth

- Local documentation supplements, but does not replace, official Red Hat documentation.
- Prefer official Red Hat documentation links for product behavior.
- Prefer upstream project documentation only for open source internals not covered by Red Hat docs.

## Architecture Diagrams

- Use ASCII diagrams directly in README files for architecture representation
- Keep diagrams simple, showing the three platform layers and key components
- Stage READMEs may include stage-specific Mermaid or ASCII diagrams inline
