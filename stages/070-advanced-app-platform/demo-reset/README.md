# Demo reset and project removal

Operator actions that return the developer stages (110 to 140) to a clean starting point, with no trace of earlier
demo runs in GitLab, Developer Hub, Dev Spaces or OpenShift Pipelines. They act as the GitLab user `demo-operator`,
which the `070-gitlab` bootstrap creates as Owner of the workload and delivery groups, with a 180-day `api` token in
Secret `gitlab-system/gitlab-demo-operator` (readable with your cluster access; it never enters a developer
workspace). Both print a read-only plan and refuse until you pass `--yes`; what they delete cannot be recovered.

| Script | When to run |
|---|---|
| `reset-coolstore.sh [--yes]` | After a Stage 110 or 120 run on Coolstore. Recreates the `coolstore-inventory-service` workspaces (deleted with their storage; `070-devspaces` recreates the seats stopped and the script points them at GitLab again), deletes every merge request and every branch but `main`, and, if `main` moved, puts it back on the registered initial commit: it deletes the PipelineRuns in `coolstore-dev`, clears the delivery repository's promotion record and recreates `main`, which fires one pipeline run that deploys the baseline. A rerun on a clean demo changes only the workspaces. |
| `delete-project.sh NAME [--yes]` | After a run that created a project from a Developer Hub template (kind `application` or `migration`, for example `coolstore-cart` in Stage 140). Deletes its workspaces, Applications, grants, scanner credential mirror and namespace, runs the retirement pipeline for a migration run and deletes its receipt and lifecycle PipelineRuns, then deletes the delivery repository `rhoai-delivery/NAME-deployment` and the GitLab project. Developer Hub drops the component within a minute, and the name is free for the template again. Refuses stage-owned imports such as Coolstore. |

`lifecycle.sh` holds the steps both share (registration and identity checks, delivery repository and workspace
lookup, workspace and GitLab project deletion); the two scripts source it.

Not covered: SonarQube projects and their analysis history, and images in Quay or GitHub.
