# Extraction Rules

Use these rules to convert an official RHOAI chapter into skill knowledge.

## Extract

Capture these facts when present:

- component purpose in one or two sentences
- supported, technology-preview, developer-preview, deprecated, or unsupported
  posture
- prerequisites and cluster assumptions
- required operators, namespaces, subscriptions, and dependencies
- CRDs, API groups, kinds, top-level spec fields, labels, and annotations
- Red Hat registry images, validated model sources, and artifact provenance
- install, configure, use, upgrade, and remove workflows
- validation commands and expected healthy signals
- common failure modes explicitly described by docs
- boundaries between product feature and custom demo integration

## Do Not Extract As Product Truth

Do not promote these into skill instructions without verification:

- upstream Kubernetes, Kubeflow, KServe, Llama Stack, or community docs fields
  not confirmed by Red Hat docs or installed schema
- examples from old RHOAI versions
- guessed default values
- UI behavior observed in screenshots but not documented
- blog snippets that conflict with official product docs
- existing legacy demo code that has not been tied back to official docs

## Skill Mapping

Map extracted content into the generated skill:

| Extracted content | Generated skill location |
|-------------------|--------------------------|
| component purpose, when to use | `SKILL.md` intro and description |
| positive and negative triggers | `SKILL.md` frontmatter description |
| source metadata | `references/source-capture.md` |
| detailed product behavior | `references/official-doc-extraction.md` |
| verification and review checklist | `references/validation-checklist.md` |
| small demo snippets | `examples/` |

## Ambiguity Handling

If official docs do not confirm a detail, write:

```markdown
Unresolved: <field or behavior>
Verification: `oc explain <kind>.<field>` or `oc get crd <name> -o yaml`
Do not use in GitOps until verified.
```

Do not silently omit unresolved product-critical items; generated skills must
make uncertainty visible.
