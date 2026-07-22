# Knowledge Governance

Use this reference when converting repeated project knowledge into durable documentation.

## Read Before Writing

Before changing documentation, read the document that owns the knowledge you are about to edit and its nearest companion docs. Stage READMEs are not the catch-all for every operational detail.

Stage READMEs should contain:

- the stage-specific concept and business framing
- the value the concept brings to a regulated enterprise
- the RHOAI, OpenShift, or Red Hat AI technologies that enable the concept
- the architecture delta between this stage and previous stages
- short source-focused references

Other durable knowledge belongs elsewhere:

- deferred capabilities and future enhancements: `BACKLOG.md`
- operational procedures and deployment order: `docs/OPERATIONS.md`
- repeated failure symptoms, root causes, and recovery: `docs/TROUBLESHOOTING.md`

## Knowledge Sources

| Source | Purpose |
|--------|---------|
| `README.md` | overall architecture and demo flow |
| `stages/NNN-*/README.md` | concise stage-specific Why/What story |
| `docs/OPERATIONS.md` | prerequisites, deployment order, validation strategy |
| `docs/TROUBLESHOOTING.md` | symptom-based diagnostics and recovery |
| `BACKLOG.md` | known workarounds, limitations, planned work |

## Capture New Knowledge

When fixing a bug or discovering a pattern, update the relevant documentation:

- Put repeated symptoms, root causes, and recovery steps in
  `docs/TROUBLESHOOTING.md`.
- Put deployment order, validation strategy, day-2 operations, and script usage
  in `docs/OPERATIONS.md`.
- Put non-obvious design decisions in the stage README only when they are needed
  to understand the concept, technology choice, or architecture delta; otherwise place operational detail in `docs/OPERATIONS.md`.
- Put known limitations in the document where the reader needs them most, with
  product version notes and a link to the source.
- Put deferred capabilities and future enhancements in `BACKLOG.md`.
- Cross-reference related stages or docs instead of duplicating long procedures.

## Recommended Snippets

Troubleshooting:

```markdown
### <Symptom or error message>

**Root Cause:** <short explanation>

**Solution:** <safe verification or repair steps>
```

Design decision:

```markdown
> **Design Decision:** We use X instead of Y because...
```

Known limitation:

```markdown
> **Known Limitation (product baseline):** <description>
> **Workaround:** <solution>
> **Ref:** <official or verified source>
```

## Source Hierarchy

Repository documentation supplements official product documentation; it does not replace it. If official docs and implementation disagree, document the gap and verify against a live cluster or CRD schema.
