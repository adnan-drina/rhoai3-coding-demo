# IDE Workflow Patterns

These examples are review patterns. Verify the active workbench image,
available IDE, repository access, and package policy before using them in demo
steps.

## IDE Selection Pattern

```text
Project: <project-name>
Workbench: <workbench-name>
IDE: JupyterLab | code-server | RStudio Server (Technology Preview)
Primary workflow: <notebooks | multi-file app dev | extensions | terminal work>
Dependency approach: requirements.txt | custom workbench image
Collaboration path: Git repository
```

Review points:

- Use JupyterLab for notebook-native workflows and Elyra-based pipeline work.
- Use code-server for VS Code-like editing, extensions, and terminal-heavy
  tasks.
- Label RStudio Server as Technology Preview and avoid it in disconnected
  demos unless official release notes and environment validation allow it.

## Access Pattern

```text
OpenShift AI dashboard -> Projects -> <project> -> Workbenches
If status is Stopped: click Start
Wait for status Running
Click the open icon next to the workbench
```

Review points:

- Verify the IDE opens in a browser.
- If startup fails, capture Events before escalating.

## JupyterLab Git Pattern

```bash
git clone <https-repository-url>
cd <repository>
git status
```

JupyterLab UI review points:

- Save all files before commit.
- Stage changed files intentionally.
- Use a short commit summary.
- Push only after confirming the changed files are expected.
- Verify the pushed changes in the remote repository.

## code-server Git Pattern

```bash
git clone <https-repository-url>
cd <repository>
git status
```

code-server UI review points:

- Save all files.
- Open Source Control.
- Stage changed files.
- Enter a commit message.
- Use Commit & Sync when the remote is configured.
- Verify the pushed changes in the remote repository.

## Python Package Pattern

```text
requirements.txt
altair==4.1.0
```

JupyterLab notebook cell:

```python
!pip install -r requirements.txt
import altair
```

code-server terminal:

```bash
pip install -r requirements.txt
python -c "import altair"
```

Review points:

- Pin versions when stability matters.
- Use `requirements.txt` for repeatability.
- Move common dependencies into a custom workbench image when they are shared
  across many workbenches.

## Troubleshooting Handoff Pattern

| Symptom | User capture | Handoff |
|---------|--------------|---------|
| Jupyter `403: Forbidden` | user, project, workbench, time, screenshot/message | `rhoai-users-groups-access` |
| Workbench does not start | Events text, workbench name, selected image, requested resources | `rhoai-basic-workbenches` or `env-troubleshoot` |
| No space left on device | notebook cell or terminal error, workbench name, storage path | `rhoai-project-workflows`, `rhoai-storage-classes`, or `env-troubleshoot` |

Review points:

- Do not ask users to make cluster-admin changes from inside the IDE.
- Capture enough context for an administrator or Red Hat Support case.
