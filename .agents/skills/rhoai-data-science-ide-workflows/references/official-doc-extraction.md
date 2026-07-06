# Official Doc Extraction

Extract only behavior supported by the official Working in your data science
IDE guide and active-baseline linked Red Hat docs.

## IDE Choices

- When creating a workbench, users select a workbench image that includes an
  integrated development environment for developing machine learning models.
- The guide identifies these data science IDEs for OpenShift AI:
  - JupyterLab
  - code-server
  - RStudio Server as a Technology Preview feature
- RStudio workbench images are currently unavailable for disconnected
  environments.
- Treat RStudio Server support statements as release-note and support-posture
  dependent.

## Accessing A Workbench IDE

- A project and workbench must exist before accessing the IDE.
- Users access the IDE from:
  `OpenShift AI dashboard -> Projects -> <project> -> Workbenches`.
- If the workbench is stopped, start it from the Status column.
- The workbench status changes from Stopped to Starting, then Running.
- The open icon next to the workbench opens the IDE in a new browser window.

## JupyterLab Workflows

- JupyterLab is a web-based interactive development environment for Jupyter
  notebooks, code, and data.
- It supports configurable data science and machine learning workflows and many
  languages, including Python and R.
- Users can create a notebook from the JupyterLab File menu and select a
  kernel when prompted.
- Users can upload an existing notebook file from local storage through the
  JupyterLab file browser.
- Users can clone a Git repository through the JupyterLab Git UI or through a
  terminal with `git clone <git-clone-URL>`.
- Users can pull remote changes from the JupyterLab Git pane after the remote
  repository is configured and visible in the file browser.
- Users can push notebook/project changes through the JupyterLab Git pane:
  save all files, review changed or untracked files, stage changes, commit,
  and push to the remote repository.
- If files appear under Untracked, the official workflow notes that users can
  enable Git simple staging.

## JupyterLab Python Packages

- Users can inspect installed Python packages from a notebook cell with:

  ```python
  !pip list
  ```

- Users can install packages that are not part of the default workbench by
  creating `requirements.txt`, adding one package per line, and running:

  ```python
  !pip install -r requirements.txt
  ```

- Red Hat recommends using `requirements.txt` so the package list can be
  reused across workbenches.
- Red Hat recommends specifying exact package versions to improve environment
  stability over time.
- The `pip install` command installs packages on the workbench; users still
  need to import packages in code before using them.

## User-Facing Jupyter And Workbench Troubleshooting

- A `403: Forbidden` error when logging in to Jupyter can indicate the user is
  not in the default OpenShift AI user group or administrator group when groups
  are configured.
- A workbench that does not start can indicate insufficient cluster resources
  or a failed workbench pod.
- For startup failures, users should check OpenShift Events for relevant error
  messages and contact a cluster administrator with those details.
- Database full, disk full, or no-space-left errors can indicate exhausted
  workbench storage.
- Problems not covered by the guide or release notes should be escalated to
  Red Hat Support.

## code-server Workflows

- code-server is a web-based interactive development environment supporting
  multiple languages, including Python, for working with Jupyter notebooks.
- The code-server workbench image supports customization through extensions
  for languages, themes, debuggers, and connections to services.
- Elyra-based pipelines are not available with the code-server workbench image.
- code-server workbench creation follows the project workbench workflow:
  select an image, configure connections, configure cluster storage, and add
  container storage when needed.
- Users can upload an existing notebook file from local storage into
  code-server.
- Users can clone a Git repository through the code-server UI or from a
  terminal with `git clone <git-clone-URL>`.
- Users can pull remote changes through code-server Source Control after the
  remote repository is configured and visible.
- Users can push changes by saving all files, reviewing Changes, staging all
  changes, entering a commit message, and using Commit & Sync.

## code-server Python Packages And Extensions

- Users can inspect installed Python packages from a code-server terminal with:

  ```bash
  pip list
  ```

- Users can install packages by creating `requirements.txt`, adding one package
  per line, and running:

  ```bash
  pip install -r requirements.txt
  ```

- Red Hat recommends exact package versions for environment stability.
- Users still need to import installed packages in code before using them.
- Users can install code-server extensions from the Extensions panel.
- The official guide points to Open VSX Registry for third-party extension
  details.

## Do Not Infer

- Do not assume code-server supports Elyra-based pipelines.
- Do not treat ad hoc `pip install` commands as a durable replacement for
  custom workbench images when the same dependency set is required broadly.
- Do not document unverified IDE extensions as part of the supported demo.
- Do not put Git credentials, access tokens, storage credentials, or API keys
  into notebooks, `requirements.txt`, README files, or Git examples.
- Do not use this guide to infer custom workbench image fields, Notebook CR
  schema, storage class behavior, or project connection fields.
