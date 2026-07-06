# Official Doc Extraction

## Platform Requirements

Official install guidance requires:

- A Red Hat OpenShift AI Self-Managed subscription.
- Cluster administrator access.
- A supported OpenShift version.
- A default storage class with dynamic provisioning.
- An OpenShift identity provider.
- Access to required Red Hat and image registry domains for connected
  installation.
- Absence of Open Data Hub on the target cluster.

For this demo, cluster-admin access and AWS-hosted OpenShift are expected, but
they still need validation before deployment.

## Supported OpenShift And Architecture

- RHOAI 3.4 is supported with OpenShift 4.19.9+, 4.20, and 4.21 in the
  supported configurations source.
- The demo baseline pins OCP 4.20, which is valid for RHOAI 3.4.
- Self-managed RHOAI is supported on OpenShift Container Platform across
  multiple architectures and providers, including AWS.
- Distributed Inference with llm-d requires OpenShift 4.20 or later.

## Resource And Storage Planning

- Official install requirements include a minimum of two worker nodes with at
  least 8 CPUs and 32 GiB RAM each for Operator installation.
- Single-node OpenShift clusters require larger node capacity.
- Additional resources depend on workloads.
- Several OpenShift AI components require or can use S3-compatible object
  storage.
- Object storage is required for single-model serving and AI Pipelines, and can
  also be used by workbenches, Kueue-based workloads, pipeline code, model
  registry, and model artifacts.

## Component Prerequisite Themes

- AI Pipelines need S3-compatible artifact storage when avoiding local storage.
- Kueue-based workloads require the Red Hat build of Kueue Operator and
  cert-manager.
- KServe requires cert-manager.
- Distributed Inference with llm-d requires cert-manager, Red Hat Connectivity
  Link, and Red Hat Leader Worker Set Operator.
- Llama Stack and RAG workloads need the Llama Stack Operator, Service Mesh,
  cert-manager, GPU-enabled nodes, NFD, NVIDIA GPU Operator, and S3-compatible
  model artifact access.
- Model registry needs an external MySQL database and S3-compatible object
  storage.

## Planning Boundary

Supported does not mean implemented. A README or GitOps step can claim a
capability only after the active project has:

- official source mapping,
- GitOps resources,
- validation commands or scripts,
- operational notes for deployment and recovery.
