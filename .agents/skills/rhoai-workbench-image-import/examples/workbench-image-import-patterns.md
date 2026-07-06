# Workbench Image Import Patterns

These examples are runbook and review patterns for the dashboard import
workflow. They are not active GitOps manifests.

## Dashboard Import Runbook

```text
1. Log in to OpenShift AI as an administrator.
2. Open Settings -> Environment setup -> Workbench images.
3. Check whether the image is already listed.
4. Click Import new image.
5. Enter the image location.
6. Enter a user-facing name.
7. Add a concise description.
8. Optionally select an accelerator identifier.
9. Optionally add software metadata.
10. Optionally add package metadata.
11. Click Import.
12. Verify the image appears in the table and during workbench creation.
```

## Image Location Choices

```text
quay.io/acme/rhoai-workbench:2026-06-10
quay.io/acme/rhoai-workbench@sha256:<digest>
docker.io/acme/rhoai-workbench:demo
```

Review points:

- Use the image reference documented by Red Hat or the image owner. Use a
  digest only when Red Hat guidance, validated artifact guidance, or an
  approved non-operator demo-app exception requires it.
- Avoid mutable tags for important demo paths unless rebuild cadence is
  documented.
- Confirm the cluster can pull the image before the demo.

## Metadata Template

```text
Name: ACME Fraud Analytics Workbench
Description: Python and data science workbench image for the fraud analytics demo.

Software:
- JupyterLab: <version>
- Elyra: <version>

Packages:
- pandas: <version>
- scikit-learn: <version>
- feast: <version>
```

Review points:

- Metadata should describe what data scientists need to choose the image.
- Do not list packages that are not actually installed in the image.
- Avoid internal URLs or credentials in visible metadata.

## Accelerator Association

```text
Accelerator identifier: nvidia.com/gpu
Recommended hardware profile: NVIDIA L40S queue-backed GPU profile
```

Review points:

- Use accelerator metadata only after GPU support is enabled.
- Match the identifier to the active cluster.
- Pair hardware profile details with `rhoai-hardware-profiles`; use
  `rhoai-nvidia-gpu-accelerators` only for GPU readiness.

## Smoke-Test Acceptance

```text
1. Create a project workbench using the imported image.
2. Confirm the workbench starts.
3. Confirm the image metadata is visible during workbench creation.
4. Open the workbench.
5. Run a small import check for the packages listed in metadata.
6. Stop or clean up the test workbench according to the operations runbook.
```

Review points:

- The official verification checks availability; demo readiness also requires
  a successful workbench start.
- Keep smoke-test cleanup separate from user-owned workbench cleanup.
