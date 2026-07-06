# Official Doc Extraction

Use this extraction to keep OpenShift Dev Spaces user workflow content grounded
in official Red Hat sources. When implementation needs exact CR fields, verify
the active cluster schema with `oc explain` before authoring GitOps manifests.

## Starting Workspaces

### From a Git Repository URL

URL pattern:

```
https://<openshift_dev_spaces_fqdn>#<git_repository_url>
```

Git provider URL patterns:

| Provider | Default branch | Specified branch |
|----------|---------------|------------------|
| GitHub | `#https://<host>/<user>/<repo>` | `#https://<host>/<user>/<repo>/tree/<branch>` |
| GitLab | `#https://<host>/<user>/<repo>` | `#https://<host>/<user>/<repo>/-/tree/<branch>` |
| Bitbucket Server | `#https://<host>/scm/<project>/<repo>.git` | via `?at=refs%2Fheads%2F<branch>` |
| Azure DevOps | `#https://<user>@dev.azure.com/<org>/<project>/_git/<repo>` | via `?version=GB<branch>` |

Git+SSH is also supported: `#git@<host>:<user>/<repo>.git`

GitHub pull request branch: `#https://<host>/<user>/<repo>/pull/<pr_id>`

Prerequisites:
- Running Dev Spaces instance
- FQDN URL of the instance
- Optional: devfile in repository root (`devfile.yaml` or `.devfile.yaml`)
- For private repos: personal access token or OAuth configured

Without a devfile, workspaces start with the Universal Developer Image (UDI)
and Microsoft Visual Studio Code - Open Source.

### From a Raw Devfile URL

```
https://<openshift_dev_spaces_fqdn>#<devfile_url>
```

For private repositories, embed token:

```
https://<openshift_dev_spaces_fqdn>#https://<token>@<host>/<path_to_devfile>
```

The devfile must contain `projects` info to clone the Git repository.

## URL Parameters for Workspace Creation

Concatenate parameters with `&`:

```
https://<openshift_dev_spaces_fqdn>#<git_url>?<param_1>&<param_2>
```

### IDE Selection (`che-editor=`)

```
?che-editor=<editor_key>
```

Editor keys:
- `che-incubator/che-code/latest` — VS Code Open Source (default)
- `che-incubator/che-code/insiders` — VS Code development version
- `che-incubator/che-idea-server/latest` — IntelliJ IDEA Ultimate (stable)
- `che-incubator/che-idea-server/next` — IntelliJ IDEA Ultimate (dev)

Also accepts a URL to a file with devfile content: `?che-editor=<url_to_file>`

The `che-editor=` parameter overrides `/.che/che-editor.yaml`.

### IDE Image Override (`editor-image=`)

```
?editor-image=<registry/image:tag>
```

Overrides the IDE container image. Can be combined with `che-editor=`.

### Duplicate Workspace (`new`)

```
?new
```

Without `new`, revisiting a URL reopens the existing workspace.

### Other Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `existing=<name>` | Reopen a specific existing workspace | `?existing=my-ws` |
| `df=<filename>.yaml` | Custom devfile filename | `?df=custom.yaml` |
| `devfilePath=<path>` | Custom devfile path | `?devfilePath=config/devfile.yaml` |
| `storageType=<type>` | Storage: `ephemeral`, `per-user`, `per-workspace` | `?storageType=ephemeral` |
| `remotes={{n1,u1},{n2,u2}}` | Additional Git remotes | |
| `image=<url>` | Custom container image | `?image=quay.io/.../ubi9-latest` |
| `memoryLimit=<value>` | Container memory limit | `?memoryLimit=4Gi` |
| `cpuLimit=<value>` | Container CPU limit | `?cpuLimit=2` |

## Workspace Management via CLI

### List Workspaces

```bash
oc get devworkspaces
```

Example output:

```
NAMESPACE   NAME               DEVWORKSPACE ID             PHASE     INFO
user1-dev   spring-petclinic   workspace6d99e9ffb9784491   Running   https://url-to-workspace.com
user1-dev   golang-example     workspacedf64e4a492cd4701   Stopped   Stopped
```

### Create a DevWorkspace CR

```yaml
kind: DevWorkspace
apiVersion: workspace.devfile.io/v1alpha2
metadata:
  name: my-devworkspace
  namespace: user1-dev
spec:
  routingClass: che
  started: true
  contributions:
    - name: ide
      uri: http://devspaces-dashboard.openshift-devspaces.svc.cluster.local:8080/dashboard/api/editors/devfile?che-editor=che-incubator/che-code/latest
  template:
    projects:
      - name: my-project-name
        git:
          remotes:
            origin: https://github.com/eclipse-che/che-docs
    components:
      - name: tooling-container
        container:
          image: quay.io/devfile/universal-developer-image:ubi9-latest
          env:
            - name: CHE_DASHBOARD_URL
              value: https://<openshift_dev_spaces_fqdn>/dashboard/
```

Key fields: `routingClass: che`, `started`, `contributions` (IDE devfile URI),
`template.projects`, `template.components`.

### Stop a Workspace

```bash
oc patch devworkspace <workspace_name> \
  -p '{"spec":{"started":false}}' \
  --type=merge -n <user_namespace> && \
oc wait --for=jsonpath='{.status.phase}'=Stopped \
  dw/<workspace_name> -n <user_namespace>
```

### Start a Stopped Workspace

```bash
oc patch devworkspace <workspace_name> \
  -p '{"spec":{"started":true}}' \
  --type=merge -n <user_namespace> && \
oc wait --for=jsonpath='{.status.phase}'=Running \
  dw/<workspace_name> -n <user_namespace>
```

### Remove a Workspace

```bash
oc delete devworkspace <workspace_name> -n <user_namespace>
```

Deleting the DevWorkspace also deletes associated DevWorkspaceTemplate and
per-workspace PVCs created by Dev Spaces.

## Devfile Structure

Devfile schema version 2.1.0 or 2.2.2. Key sections:

```yaml
schemaVersion: 2.2.2
metadata:
  name: my-workspace
components:
  - name: tools
    container:
      image: quay.io/devfile/universal-developer-image:ubi9-latest
      memoryLimit: 6G
      memoryRequest: 512Mi
      cpuLimit: 4000m
      cpuRequest: 1000m
      mountSources: true
      env:
        - name: MY_VAR
          value: my-value
      endpoints:
        - name: http
          targetPort: 8080
          exposure: public
      volumeMounts:
        - name: m2
          path: /home/user/.m2
  - name: m2
    volume:
      size: 10G
commands:
  - id: build
    exec:
      component: tools
      commandLine: mvn package
      workingDir: ${PROJECT_SOURCE}
```

Without a devfile, Dev Spaces uses the Universal Developer Image which includes
common development tools, Podman, Buildah, and `oc`.

Images used in `components` should be based on Universal Base Images (UBI) for
production. Images missing `openssl` and `libbrotli` will fail to start VS Code.

## IDE Configuration

### Repository-Level (`/.che/che-editor.yaml`)

Using `id` (plugin registry lookup):

```yaml
id: che-incubator/che-code/latest
```

Using `reference` (URL to a remote che-editor.yaml):

```yaml
reference: https://<host>/<path>/che-editor.yaml
```

Using `inline` (full devfile definition):

```yaml
inline:
  schemaVersion: 2.1.0
  metadata:
    name: JetBrains IntelliJ IDEA Community IDE
  components:
    - name: intellij
      container:
        image: 'quay.io/che-incubator/che-idea:next'
        memoryLimit: 2048M
        endpoints:
          - name: intellij
            attributes:
              type: main
              cookiesAuthEnabled: true
              urlRewriteSupported: true
            targetPort: 8887
            exposure: public
            protocol: https
```

Using `override` to customize resources:

```yaml
id: che-incubator/che-idea/latest
override:
  containers:
    - name: che-idea
      memoryLimit: 1280Mi
      cpuLimit: 1510m
```

## VS Code Extension Installation

Add `/.vscode/extensions.json` to the Git repository:

```json
{
  "recommendations": [
    "<publisher_A>.<extension_B>",
    "<publisher_C>.<extension_D>"
  ]
}
```

Extensions are installed from the Open VSX registry at workspace startup.
In restricted environments, configure a private Open VSX registry or install
from `.vsix` files via Command Palette (`Extensions: Install from VSIX…`).

### GitHub Copilot Chat Setup

1. Install `Dev Spaces Copilot Chat Integration` extension version 0.36.2.
2. Complete Device Authentication: Command Palette → `GitHub: Device Authentication`.
3. Complete the device flow in the browser.
4. Refresh the browser page when prompted.

Required URLs for restricted environments:
- `https://github.com`
- `https://api.github.com`
- `https://api.githubcopilot.com`

Device Authentication credentials persist across workspaces as a cluster Secret.

## Credential Management

### Mount Secrets

```yaml
kind: Secret
apiVersion: v1
metadata:
  name: my-credentials
  labels:
    controller.devfile.io/mount-to-devworkspace: 'true'
    controller.devfile.io/watch-secret: 'true'
  annotations:
    controller.devfile.io/mount-as: file
    controller.devfile.io/mount-path: /etc/my-credentials
type: Opaque
data:
  api-key: <base64_encoded_api_key>
```

Mount types:
- `file` — each key becomes a file in the mount path directory
- `subpath` — similar to file, uses subPath volumes
- `env` — each key-value pair becomes an environment variable

Default mount path for Secrets: `/etc/secret/<Secret_name>`

### Mount Secrets as Environment Variables

```yaml
kind: Secret
apiVersion: v1
metadata:
  name: my-env-secret
  labels:
    controller.devfile.io/mount-to-devworkspace: 'true'
    controller.devfile.io/watch-secret: 'true'
  annotations:
    controller.devfile.io/mount-as: env
type: Opaque
stringData:
  DATABASE_URL: postgresql://localhost:5432/mydb
  API_SECRET: my-secret-key
```

### Image Pull Secrets

```bash
oc create secret docker-registry <Secret_name> \
    --docker-server=<registry_server> \
    --docker-username=<username> \
    --docker-password=<password> \
    --docker-email=<email_address>

oc label secret <Secret_name> \
    controller.devfile.io/devworkspace_pullsecret=true \
    controller.devfile.io/watch-secret=true
```

### Mount ConfigMaps

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: my-config
  labels:
    controller.devfile.io/mount-to-devworkspace: 'true'
    controller.devfile.io/watch-configmap: 'true'
  annotations:
    controller.devfile.io/mount-as: subpath
    controller.devfile.io/mount-path: /home/user
data:
  .gitconfig: |
    [user]
      name = Your Name
      email = your.email@example.com
```

Default mount path for ConfigMaps: `/etc/config/<ConfigMap_name>`

Applying or modifying a Secret or ConfigMap with
`controller.devfile.io/mount-to-devworkspace: 'true'` restarts all running
workspaces in the project.

## Git Provider Access Tokens

```yaml
kind: Secret
apiVersion: v1
metadata:
  name: personal-access-token-github
  labels:
    app.kubernetes.io/component: scm-personal-access-token
    app.kubernetes.io/part-of: che.eclipse.org
  annotations:
    che.eclipse.org/che-userid: <devspaces_user_id>
    che.eclipse.org/scm-personal-access-token-name: github
    che.eclipse.org/scm-url: https://github.com
type: Opaque
stringData:
  token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Supported providers: `github`, `gitlab`, `bitbucket-server`, `azure-devops`.

User ID: `https://<openshift_dev_spaces_fqdn>/api/user/id`
User namespace: `https://<openshift_dev_spaces_fqdn>/api/kubernetes/namespace`

## Persistent Storage

### In a Devfile

```yaml
schemaVersion: 2.1.0
metadata:
  name: mydevfile
components:
  - name: golang
    container:
      image: golang
      memoryLimit: 512Mi
      mountSources: true
      command: ['sleep', 'infinity']
      volumeMounts:
        - name: cache
          path: /.cache
  - name: cache
    volume:
      size: 2Gi
```

### Via PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: <pvc_name>
  labels:
    controller.devfile.io/mount-to-devworkspace: 'true'
  annotations:
    controller.devfile.io/mount-path: </example/directory>
    controller.devfile.io/read-only: 'true'
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 3Gi
```

Storage type URL parameter: `?storageType=ephemeral|per-user|per-workspace`

With `ephemeral` or `per-workspace` storage, multiple workspaces can run
concurrently (not possible with default `per-user`).

## Container Tooling (fuse-overlayfs and Kubedock)

### fuse-overlayfs ConfigMap

```yaml
kind: ConfigMap
apiVersion: v1
metadata:
  name: fuse-overlay
  labels:
    controller.devfile.io/mount-to-devworkspace: 'true'
    controller.devfile.io/watch-configmap: 'true'
  annotations:
    controller.devfile.io/mount-as: subpath
    controller.devfile.io/mount-path: /home/user/.config/containers
data:
  storage.conf: |
    [storage]
    driver = "overlay"

    [storage.options.overlay]
    mount_program = "/usr/bin/fuse-overlayfs"
```

For OpenShift 4.15+, only `io.kubernetes.cri-o.Devices: /dev/fuse` annotation
is needed. For older versions, also add `io.openshift.podman-fuse: ""`.

### Kubedock Devfile Example

```yaml
schemaVersion: 2.2.0
metadata:
  name: kubedock-sample-devfile
components:
  - name: tools
    container:
      image: quay.io/devfile/universal-developer-image:latest
      memoryLimit: 8Gi
      cpuLimit: "2"
      env:
        - name: KUBEDOCK_ENABLED
          value: 'true'
        - name: DOCKER_HOST
          value: 'tcp://127.0.0.1:2475'
        - name: TESTCONTAINERS_RYUK_DISABLED
          value: 'true'
        - name: TESTCONTAINERS_CHECKS_DISABLE
          value: 'true'
      endpoints:
        - exposure: none
          name: kubedock
          protocol: tcp
          targetPort: 2475
```

Kubedock supported commands: `podman run`, `podman ps`, `podman exec`,
`podman cp`, `podman logs`, `podman inspect`, `podman kill`, `podman rm`,
`podman wait`, `podman stop`, `podman start`. Other commands (e.g.,
`podman build`) use local Podman.

## Workspace Idling Prevention

```yaml
enabled: true
watchedCommands:
  - helm
  - odo
  - sleep
checkPeriodSeconds: 60
```

Place as `~/.noidle`, `$CLI_WATCHER_CONFIG`, or in the project directory.
Supports live updates. PID 1 and `tail` are always excluded.

## Team Workflow

### Factory Badge

Add to repository README:

```
[![Contribute](https://www.eclipse.org/che/contribute.svg)](https://<openshift_dev_spaces_fqdn>/#https://<your_repository_url>)
```

### Try in Web IDE GitHub Action

```yaml
name: Try in Web IDE example
on:
  pull_request_target:
    types: [opened]
jobs:
  add-link:
    runs-on: ubuntu-20.04
    steps:
      - name: Web IDE Pull Request Check
        id: try-in-web-ide
        uses: redhat-actions/try-in-web-ide@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          add_comment: true
          add_status: true
```

## Troubleshooting

### View Workspace Logs

```bash
oc logs --follow --namespace='<workspace_namespace>' \
  --selector='controller.devfile.io/devworkspace_name=<workspace_name>'
```

### Common Issues

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| `OOMKilled` | Container memory limit exceeded | Increase `memoryLimit` in devfile |
| `CrashLoopBackOff` | Container image fails to start | Verify image runs outside Dev Spaces |
| `Failed to process devfile` | Devfile syntax error | Validate YAML, check `schemaVersion` |
| Workspace ignores devfile changes | Cached devfile | Delete workspace, create new from URL |
| `openssl`/`libbrotli` not found | Missing libraries in image | `RUN yum install compat-openssl11 libbrotli` |
| WebSocket FAILED | Browser/proxy blocking WSS | Allow WSS on port 443 |
| Endpoint returns 502/503 | App not on declared port | Verify `targetPort` matches app port |

### Performance Tuning

Devfile resource configuration:

```yaml
components:
  - name: tools
    container:
      image: quay.io/devfile/universal-developer-image:ubi8-latest
      cpuLimit: 4000m
      cpuRequest: 1000m
      memoryLimit: 6G
      memoryRequest: 512Mi
```

Admin-side improvements: Image Puller (pre-cache images), offline installation,
reduce public endpoints, choose optimal storage type.

## OpenShift Integration

- Automatic OpenShift token injection: `oc` and `kubectl` authenticate
  automatically in workspace containers (OpenShift infrastructure only)
- ConsoleLink CR created by the Dev Spaces Operator for Red Hat Applications menu
- Developer Perspective Topology view: Edit Source Code button opens Dev Spaces
- User namespace: `https://<fqdn>/api/kubernetes/namespace`
- User ID: `https://<fqdn>/api/user/id`
