# Demo reset and project retirement

Operator actions on registered GitLab projects. They act as the GitLab user `demo-operator`, which the
`070-gitlab` bootstrap creates as Owner of the workload group, with a 180-day `api` token in Secret
`gitlab-system/gitlab-demo-operator` (readable with your cluster access; it never enters a developer workspace). Both print a read-only plan and refuse until you
pass `--yes`. Repository history is always kept (no force push); workspace PVCs and delivery history stay.

| Script | When to run |
|---|---|
| `reset-coolstore.sh [--yes]` | After a Stage 110/120 demo run, to give the next audience the original Coolstore code. Restores the registered baseline of `coolstore-inventory-service` with one normal commit on `main` and stops the `coolstore-inventory-service` workspaces that clone it. The commit fires one expected pipeline run in `coolstore-dev`. A rerun on a restored `main` commits nothing. |
| `delete-project.sh NAME [--yes]` | To retire a project created from a Developer Hub template (kind `application` or `migration`). Writes an immutable retirement record, stops its workspaces, archives the GitLab project, runs the retirement pipeline for a migration run, then deletes its Applications, cross-namespace grants and namespace. Refuses Stage-owned imports such as Coolstore. |

`lifecycle.sh` holds the steps both share (registration and identity checks, workspace matching, the restoring
commit); the two scripts source it.
