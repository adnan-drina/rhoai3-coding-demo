# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Concept Model

Basic workbenches are managed through the Start basic workbench application.
The related user-facing documentation states that basic workbenches are useful
when users do not need their own projects or when opening a Jupyter notebook
developed outside OpenShift AI. The preferred way to access workbenches in
OpenShift AI is through a project when the workflow needs project organization,
connections, models, data, or pipelines.

OpenShift AI administrators can use the basic workbench administration
interface to start, access, and stop workbenches owned by other users. These
administrator actions are intended for support, troubleshooting, resource
control, and user-resource cleanup.

## Administration Interface

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Official dashboard path:

```text
OpenShift AI dashboard -> Applications -> Enabled -> Start basic workbench -> Open application -> Administration
```

Verification:

- The administration interface for basic workbenches is visible.

## Starting Another User's Basic Workbench

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The Start basic workbench application has been launched.

Workflow:

1. Open the Start basic workbench application.
2. Open the Administration tab.
3. In the Users section, locate the target user.
4. Click Start workbench for that user.
5. Complete the Start a basic workbench page.
6. Optionally select Start workbench in current tab.
7. Click Start workbench.

Verification:

- The JupyterLab interface opens in the selected browser tab behavior.

## Accessing Another User's Running Basic Workbench

Use this workflow only to correct configuration errors or help troubleshoot a
user environment.

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The Start basic workbench application has been launched.
- The target workbench is running.

Workflow:

1. Open the Administration tab.
2. In the Users section, locate the target user.
3. Click View server for that user.
4. On the Workbench control panel page, click Access workbench.

Verification:

- The JupyterLab interface opens in the user's workbench.

## Stopping Basic Workbenches Owned By Other Users

OpenShift AI administrators can stop basic workbenches owned by other users to
reduce cluster resource consumption or as part of removing a user and their
resources from the cluster.

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The Start basic workbench application has been launched.
- The target workbench is running.

Stop one specific workbench:

1. Open the Administration tab.
2. Locate the user.
3. Either use the row action menu and select Stop server, or click View server
   and then Stop workbench.
4. In the Stop server dialog, click Stop server.

Stop all workbenches:

1. Open the Administration tab.
2. Click Stop all workbenches.
3. Confirm by clicking OK.

Verification:

- The stop action changes to Start workbench after the workbench has stopped.

## Idle Workbench Timeout

Idle workbench timeout stops workbenches that have no logged-in users for a
defined period. The default behavior is that idle workbenches are not stopped
after a specific time limit.

If cluster settings disconnect all users after a specified time limit, that
cluster-wide setting takes precedence over the idle workbench time limit.

Prerequisite:

- The operator is logged in to OpenShift AI with administrator privileges.

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings
```

Workflow:

1. Under Idle workbench timeout, select Stop idle workbenches after defined
   period.
2. Enter a time limit in hours and minutes.
3. Save changes.

Verification:

- In the OpenShift console, inspect the `notebook-controller-culler-config`
  ConfigMap in the `redhat-ods-applications` project.
- Confirm the culling settings:
  - `ENABLE_CULLING`: whether culling is enabled or disabled; default is
    `false`
  - `IDLENESS_CHECK_PERIOD`: polling frequency for notebook activity checks in
    minutes
  - `CULL_IDLE_TIME`: maximum time in minutes before scaling an inactive
    notebook to zero
- Idle workbenches stop at the configured time limit.

## Workbench Pod Tolerations

Workbench pod tolerations can allow workbench pods to be scheduled on tainted
nodes. This is useful when certain machine pools should run only workbench pods
or when workbenches need nodes with specific capacity.

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- The operator understands OpenShift taints and tolerations.

Official dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings
```

Workflow:

1. Under Workbench pod tolerations, select Add a toleration to workbench pods
   to allow them to be scheduled to tainted nodes.
2. Enter a toleration key.
3. Save changes.

Toleration key rule:

- The key can be any string up to 253 characters.
- The key must begin with a letter or number.
- The key can contain letters, numbers, hyphens, dots, and underscores.

Example key:

```text
workbenches-only
```

The toleration key is applied to new workbench pods when they are created.
Existing workbench pods receive the toleration when the workbench pods are
restarted.

Next platform step:

- Add a matching taint key with any value to the machine pools dedicated to
  workbenches.

Verification:

1. In the OpenShift console, select the project.
2. Open Workloads -> StatefulSet.
3. Check whether the workbench has zero or one running pods.
4. Open the workbench pod details.
5. Confirm the assigned node and tolerations are correct.

## Troubleshooting: Jupyter 404

Problem:

- A user receives a 404 page when logging in to Jupyter.

Likely cause:

- If OpenShift AI user groups are configured, the user might not be added to
  the default OpenShift AI user group.

Diagnosis:

1. In the OpenShift web console, open User Management -> Groups.
2. Open the group allowed to access Jupyter, for example `rhods-users`.
3. On the Details tab, confirm the user is listed in the Users section.

Resolution:

- If the user is not in an allowed group, add the user to an OpenShift AI user
  group with `rhoai-users-groups-access`.
- If the user is already in an allowed group, contact Red Hat Support.

## Troubleshooting: Workbench Does Not Start

Problem:

- A user's workbench does not start.

Likely causes:

- The cluster does not have enough resources.
- The workbench pod failed.

Diagnosis:

1. Log in to the OpenShift web console.
2. Check the workbench pod in `rhods-notebooks` or the custom workbench
   namespace.
3. Search for a pod like `jupyter-nb-<username>-*`.
4. If the pod exists, an intermittent pod failure might have occurred.
5. If the pod does not exist, check available CPU and memory against the
   selected workbench image requirements.
6. Check the workbench pod state.

Resolution:

- If the pod failure appears intermittent, delete the user's workbench pod and
  ask the user to start the workbench again.
- If there are insufficient resources, add cluster resources or choose a
  smaller image size.
- If the workbench pod is in a failed state, collect logs from the
  `jupyter-nb-*` pod for Red Hat Support, then delete the pod.
- If the documented resolutions do not apply, contact Red Hat Support.

## Troubleshooting: Database Or Disk Full

Problem:

- The user receives a database or disk full error, or a no-space-left-on-device
  error when running notebook cells.

Likely cause:

- The user might have exhausted the workbench storage.

Diagnosis:

1. Log in to Jupyter and start the user's workbench when possible.
2. If the workbench does not start, inspect the workbench pod in
   `rhods-notebooks` or the custom workbench namespace.
3. Open logs for a pod like `jupyter-nb-<idp>-<username>-*`.
4. Look for errors indicating that the database or disk is full.

Resolution:

- Increase the user's available storage by expanding the persistent volume
  according to OpenShift storage documentation.
- Work with the user to remove unneeded files from `/opt/app-root/src`.
- Deleting files in the JupyterLab file explorer moves them to
  `/opt/app-root/src/.local/share/Trash/files`; permanently delete those files
  to actually free space.

## Out Of Scope For This Chapter

This chapter does not define:

- project workbench creation
- custom workbench image creation or import
- Gateway API migration for custom workbench images
- GitOps fields for idle culling or toleration settings
- OpenShift machine pool taint creation
- persistent volume expansion procedures
- general notebook authoring, Git workflows, or Python package management
