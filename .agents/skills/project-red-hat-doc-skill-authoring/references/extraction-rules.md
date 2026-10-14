# Citation Rules (keep, link, or delete)

Product skills cite official Red Hat documentation; they do not extract it.
(The file name is kept for existing links.) Apply these rules to every claim
in a new skill and to every section of an old `official-doc-extraction.md`
during conversion.

## Classify each item

| Item | Action |
|---|---|
| Generic product behavior (what a component is, a procedure, a field table, a supported-configuration table) | Delete. Add a row to "Official documentation" linking the section with its anchor. |
| A fact the repo depends on, overrides, or got wrong before (API-group mismatch, Technology Preview posture, a deprecated release, a default the repo changes, a known issue the repo hit) | Keep as one line under "Repo decisions" or "Pitfalls", with its manifest path and a section link. Re-verify against the map's `docs_version`. |
| YAML or CLI example | Replace with the path of the repo's own manifest or script. If the repo has none, link the official procedure. |
| Supported-version tables, release dates, advisory IDs | Link the section; quote at most the single value a decision depends on. |
| Retrieval date, sections used, source URLs | Move to the map route (`reviewed`, `sections`, `note`). |

## Verification standard

- Verify each kept claim against the section of the map's `docs_version`.
- If docs.redhat.com answers 403/429/5xx, keep only claims the repo proves
  (manifest, README, validate script) and record the unverified gap in the
  route `note`.
- Mark unresolved product details explicitly:

  ```markdown
  Unresolved: <field or behavior>. Verify with `oc explain <kind>.<field>` before use in GitOps.
  ```

## Do not treat as product truth

- Upstream Kubernetes, Ceph, Kuadrant, KServe, Kubeflow or community docs not
  confirmed by Red Hat docs or the installed schema.
- Examples from older product versions, guessed defaults, blog snippets.
- Legacy repo text that is not tied back to Git or to the current docs.

## Licensing

Red Hat documentation text is CC BY-SA 3.0. Linking plus short quotations of
the names a decision needs avoids redistributing adapted text under
share-alike terms. Do not paste paragraphs, tables, or example blocks.
