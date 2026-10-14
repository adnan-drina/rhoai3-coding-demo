# Validation Checklist

Run before finishing a new, updated, or converted product skill.

## Structure

- Folder `.agents/skills/<prefix>-<capability>/`, frontmatter `name` matches.
- Frontmatter: `metadata.product` (map key), `metadata.docs-version` (equals
  the map's `docs_version`), `metadata.skill-group`.
- `SKILL.md` under ~150 lines; sections When to use, Repo decisions,
  Procedure, Pitfalls, Official documentation, Related skills.
- No `references/official-doc-extraction.md`, no `references/source-capture.md`;
  any remaining reference file is repo-owned.

## Content

- Every repo decision names its path under `gitops/`, `scripts/`, `stages/`,
  or `docs/`, and the path exists.
- Every kept product claim is verified against the map's `docs_version` and
  linked to a section anchor, or marked unresolved.
- No paragraphs, tables, or example blocks copied from the documentation.
- No unversioned or other-version docs.redhat.com links.
- Live commands are read-only where possible and follow the OpenShift safety
  guard in `AGENTS.md`.
- No secrets, tokens, kubeconfigs, or private cluster URLs.

## Map

- The skill has a route; the route lists `sections` and `reviewed`.
- The product's `docs_version` agrees with its Git pin.

## Commands

```bash
python3 .agents/skills/agentskills-authoring/scripts/validate-skills.py --all
python3 scripts/shared/check-doc-links.py --family <family>
python3 scripts/shared/check-doc-links.test.py   # when the checker or map schema changed
./scripts/platform/validate-stage-flow.sh        # static; runs both checks
```

Record any skipped check, and any section that could not be read, in the
final response.
