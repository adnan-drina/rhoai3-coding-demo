# Delivery path (copy — GitOps SoT)

Canonical table: `gitops/stages/050-advanced-app-platform/base/rhdh/templates/app-migration/delivery-path.md`.

`DEFAULT_EXTENSIONS` / `redhat.java` render from the **RHDH app-migration
skeleton** → dest git `devfile.yaml` → Dev Spaces **factory inlines dest**
`devfile.yaml` at **create**. They do **not** render from this golden
`devfile.yaml` after `bootstrap-scaffold-repos.sh`. Do not re-edit the
scaffold `devfile.yaml` for that env. Do not recreate a DevWorkspace by
applying a previous CR.
