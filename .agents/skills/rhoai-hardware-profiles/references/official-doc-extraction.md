# Official Documentation Extraction

Use this extraction when creating or reviewing hardware profile guidance for the
active RHOAI baseline.

## Product Behavior

- Accelerators are used in OpenShift AI to optimize data science workflows
  such as NLP, inference, model training, data cleansing, and data processing.
- Before an accelerator is usable in OpenShift AI, the relevant accelerator
  software must be installed. The guide lists NFD and the corresponding GPU
  Operator as part of accelerator enablement.
- After installing the accelerator, administrators create a hardware profile.
- Existing accelerator profiles can be automatically created after an upgrade
  when profiles were already configured.
- Hardware profiles are managed from the OpenShift AI dashboard under
  Settings -> Hardware profiles.
- OpenShift AI validates dashboard visibility by showing the profile on the
  Hardware profiles page, in the Create workbench profile list, and on the
  `HardwareProfile` CRD instances page.

## Hardware Profile Creation

The official dashboard workflow captures these profile dimensions:

- profile identifying information: display name, identifier, and description
- resource requests and limits
- local queue selection when Kueue scheduling is used
- workload priority for jobs that use the profile
- node selectors
- tolerations

Node selector key and value entries must begin with a letter or number and can
contain letters, numbers, hyphens, dots, and underscores.

Toleration configuration includes:

- operator: `Equal` or `Exists`
- effect: none, `NoSchedule`, `PreferNoSchedule`, or `NoExecute`
- key
- value
- toleration seconds: forever or a custom seconds value

## Update And Delete Behavior

- Existing hardware profiles can be enabled or disabled from the Enabled column
  on the Hardware profiles page.
- Administrators can edit identifying information, such as display name,
  identifier, or description.
- Deleting a hardware profile removes it from the dashboard after the name is
  entered to confirm deletion.

## Recommended Accelerator Tags

Workbench images:

- Administrators can set an accelerator identifier as recommended for a
  workbench image.
- If the image has only one accelerator identifier, the identifier name is
  displayed by default.
- If a workbench image does not contain an accelerator identifier, configure one
  before creating an associated hardware profile.

Serving runtimes:

- Administrators can add a recommended accelerator tag to a custom serving
  runtime.
- The OpenVINO Model Server runtime included with OpenShift AI cannot be
  directly edited; clone it first if a custom variant is needed.
- The official example uses this annotation shape for NVIDIA GPU compatibility:

  ```yaml
  metadata:
    annotations:
      opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
  ```

## GitOps Extraction Rules

- Treat the dashboard workflow as the supported UI source.
- Treat the `HardwareProfile` CRD as the Kubernetes API surface, but verify the
  active schema before authoring manifests.
- Prefer exporting a dashboard-created profile as the source for GitOps
  promotion when creating the first profile in a new RHOAI baseline.
- Do not copy upstream or old-version HardwareProfile examples without
  verifying `apiVersion`, `kind`, and `spec` fields.
- Keep recommended accelerator annotations close to the workbench image or
  serving runtime they describe.

## Demo Handoff

For the current NVIDIA L40S demo profiles:

- verify a GPU node reports `nvidia.com/gpu` in both Capacity and Allocatable
- verify active node labels before adding node selectors
- verify active taints before adding tolerations
- keep `rhoai-nvidia-gpu-accelerators` as the owner for GPU Operator and node
  readiness
- keep `rhoai-kueue-workload-management` as the owner for local queue policy
