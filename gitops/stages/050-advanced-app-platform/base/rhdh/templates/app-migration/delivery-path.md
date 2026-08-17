# App-migration delivery path (DEFAULT_EXTENSIONS / `redhat.java`)

The DevWorkspace env is **not** the Stage 080 golden `devfile.yaml` that
`bootstrap-scaffold-repos.sh` publishes. Attempt-9 live
`DEFAULT_EXTENSIONS` missed `redhat.java` because recreate applied a
sanitized prior DevWorkspace CR. Factory inlines **dest git** `devfile.yaml`
at **create** (Architect `E-20260817T123931Z`).

Do **not** re-edit `stages/080-…/quarkus-migration-scaffold/devfile.yaml`
for this env (`E-20260817T122644Z`). That file is already correct and is
**not** the render path.

| Artifact | Render path | Publish / apply command |
|---|---|---|
| Dest `devfile.yaml` `DEFAULT_EXTENSIONS` (includes `/tmp/redhat-java.vsix` before `mta-java`) | RHDH software template `skeleton/devfile.yaml` via `template.yaml` `fetch:template` `replace: true` | Stage 050 GitOps sync (`overlay-a8-publish`); catalog follows Argo `targetRevision` |
| Live DevWorkspace `spec.template` env | Dev Spaces factory inlines dest `devfile.yaml` **at workspace create** | Dashboard / factory URL on dest git (`che-incubator/che-code/latest`). **OBJECT** `oc apply` of a previous DevWorkspace CR |
| Hermes skills, mint, fence, Spec Kit overlay | Stage 080 golden `quarkus-migration-scaffold` | `bootstrap-scaffold-repos.sh` onto dest `main` (golden SHA), then dest re-scaffold |
| `migration.yaml` package stamp | Same RHDH skeleton as dest `devfile.yaml` | Same `fetch:template` `replace: true` (class: `091352Z`) |
| Che Code recommendations (`extensions.json`) | `gitops/…/devspaces/vscode-editor-configurations.yaml` ConfigMap | Stage 050 GitOps; does **not** set `DEFAULT_EXTENSIONS` |

Same class as prior bites: `27dd2b01` (gate strip), `595bcfa1` (frozen join),
`ddc039df` (unpublished), born-broken `migration.yaml`, attempt-9
`DEFAULT_EXTENSIONS` CR reuse.
