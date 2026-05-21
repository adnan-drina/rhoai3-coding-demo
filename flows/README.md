# Demo Flows

This directory contains machine-readable flow metadata.

[`default.yaml`](default.yaml) is the ordered source of truth for the implemented nine-stage demo path. It records each stage ID, name, product focus, deploy script, validate script, GitOps application, GitOps source path, and dependencies.

Stage content lives in [`../stages/`](../stages/). GitOps manifests live in [`../gitops/stages/`](../gitops/stages/).
