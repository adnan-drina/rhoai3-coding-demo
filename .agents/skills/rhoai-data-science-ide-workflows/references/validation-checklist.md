# Validation Checklist

Use this checklist before accepting documentation, notebooks, examples, or
runbooks that describe OpenShift AI data science IDE workflows.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The Working in your data science IDE guide is recorded when IDE workflows are
  introduced.
- Project and workbench lifecycle is delegated to `rhoai-project-workflows`.
- Custom workbench image content is delegated to
  `rhoai-workbenches-custom-images`.
- S3-compatible object storage notebook workflows are delegated to
  `rhoai-s3-object-storage-data`.
- AI Pipelines and Elyra/KFP authoring are delegated to
  `rhoai-kfp-pipeline-authoring`.

## IDE Access Review

- A project and workbench exist before IDE access is described.
- Workbench state is checked before opening the IDE.
- Stopped workbenches are started through the documented Workbenches tab
  workflow.
- Verification confirms that a new browser window opens for the IDE.

## JupyterLab Review

- Notebook creation uses JupyterLab File -> New -> Notebook or the official
  equivalent from the launcher.
- Kernel selection is explicit when the workflow depends on a kernel.
- Local notebook upload is treated as an import convenience, not durable
  collaboration.
- Git clone, pull, commit, and push workflows use repository URLs and
  credentials without exposing secrets.
- Changed and untracked files are reviewed before commit.
- Git push verification checks the remote repository.

## code-server Review

- code-server is chosen for a VS Code-like, terminal-centric, or extension-rich
  workflow.
- code-server examples do not claim Elyra-based pipeline support.
- Notebook upload, Git clone, pull, commit, and sync workflows match the
  code-server UI or terminal behavior.
- Extension examples are verified in the active code-server image and listed
  as third-party where appropriate.
- Installed extension verification checks the code-server Extensions panel.

## Python Package Review

- `pip list` is used to inspect installed packages in the correct interface:
  notebook cell for JupyterLab or terminal for code-server.
- New packages are listed in `requirements.txt` when repeatability matters.
- Package versions are pinned with `==` when stability matters.
- `pip install -r requirements.txt` is followed by an import check in code.
- Frequently reused package sets are considered for a custom workbench image
  instead of repeated ad hoc installation.

## Troubleshooting Review

- A Jupyter `403: Forbidden` error is routed to OpenShift AI user/admin group
  membership review with `rhoai-users-groups-access`.
- Workbench startup failures capture OpenShift Events messages before admin
  escalation.
- Disk-full and no-space-left symptoms are routed to storage review and
  administrator troubleshooting.
- Uncovered or release-note-specific problems are escalated to Red Hat Support
  with captured symptom details.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get notebooks.kubeflow.org -n <project-name>
oc get pods -n <project-name>
oc get events -n <project-name> --sort-by=.lastTimestamp
oc get pvc -n <project-name>
```

Workbench-local checks:

```bash
git status
git remote -v
pip list
pip install -r requirements.txt
```

JupyterLab notebook-cell checks:

```python
!pip list
!pip install -r requirements.txt
import <package_name>
```

## Fail Conditions

Stop and correct the work if any of these are true:

- Git credentials, access tokens, storage credentials, or API keys appear in
  committed content.
- code-server is used for an Elyra-based pipeline workflow.
- RStudio Server is presented as generally available or disconnected-ready.
- Package installation is unpinned in a repeatable demo workflow without a
  reason.
- User-facing troubleshooting skips the symptom capture needed for admin or Red
  Hat Support escalation.
