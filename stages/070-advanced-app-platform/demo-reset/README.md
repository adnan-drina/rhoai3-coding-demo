# Demo reset and project removal

Operator actions that return the developer stages (110 to 140) to a clean starting point, with no trace of earlier
demo runs in GitLab, Developer Hub, Dev Spaces or OpenShift Pipelines. They act as the GitLab user `demo-operator`,
which the `070-gitlab` bootstrap creates as Owner of the workload and delivery groups, with a 180-day `api` token in
Secret `gitlab-system/gitlab-demo-operator` (readable with your cluster access; it never enters a developer
workspace). Both print a read-only plan and refuse until you pass `--yes`; what they delete cannot be recovered.

| Script | When to run |
|---|---|
| `reset-coolstore.sh [--yes]` | After a Stage 110 or 120 run on Coolstore. Recreates the `coolstore-inventory-service` workspaces (deleted with their storage; `070-devspaces` recreates the seats stopped and the script points them at GitLab again), deletes the merge requests and branches of demo runs (anything newer than the registered commit; imported branches such as `golden` stay), and, if `main` moved, puts it back on the registered initial commit: it deletes the PipelineRuns in `coolstore-dev`, clears the delivery repository's promotion record and recreates `main`, which fires one pipeline run that deploys the baseline. It also deletes the `coolstore-dev` runs stored in Tekton Results whose PipelineRun is gone. A rerun on a clean demo changes only the workspaces. |
| `delete-project.sh NAME [--yes]` | After a run that created a project from a Developer Hub template (kind `application` or `migration`, for example `coolstore-cart` in Stage 140). Deletes its workspaces, Applications, grants, scanner credential mirror and namespace, runs the retirement pipeline for a migration run and deletes its receipt and lifecycle PipelineRuns, then deletes the delivery repository `rhoai-delivery/NAME-deployment` and the GitLab project. It also deletes the SonarQube project of that name with its analysis history and analysis tokens, so a new project of the same name starts with a fresh new-code period, and the project's runs stored in Tekton Results. Developer Hub drops the component within a minute, and the name is free for the template again. On a name that is already removed, it deletes only leftovers of an earlier removal: a SonarQube project and stored runs. Refuses stage-owned imports such as Coolstore. |

`lifecycle.sh` holds the steps both share (registration and identity checks, delivery repository and workspace
lookup, workspace, GitLab project, SonarQube project and Tekton Results deletion); the two scripts source it.

`delete-project.sh` also acts as the SonarQube administrator (Secret `sonarqube/sonarqube-admin`, written by the `070-sonarqube` bootstrap) through the `sonarqube` Route.

Tekton Results keeps every finished PipelineRun and TaskRun after the cluster objects are deleted, and the OpenShift
console lists those stored runs. Both scripts delete them with your own `oc` token (a token login, `oc whoami -t`),
through a temporary `oc port-forward` to Service `openshift-pipelines/tekton-results-api-service`: the operator's
`tekton-results-api` Route is edge-terminated in front of a TLS backend and answers HTTP 400. They delete only stored
runs whose PipelineRun or TaskRun is no longer in the cluster.

Not covered: the Coolstore SonarQube history, and images in Quay or GitHub.
