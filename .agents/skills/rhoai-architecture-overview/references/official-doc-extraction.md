# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Deployment Context

Red Hat OpenShift AI Self-Managed is available as an Operator in self-managed
environments such as Red Hat OpenShift Container Platform, and in Red Hat
managed cloud environments such as OpenShift Dedicated, ROSA classic, ROSA HCP,
and Microsoft Azure Red Hat OpenShift.

Do not use this statement as a support matrix by itself. For platform and
hardware requirements, use `docs/PLATFORM_BASELINE.md` and the official planning
or supported-configuration documentation.

## Service Layer

The chapter identifies these service-layer components and services:

| Component | Official role |
|-----------|---------------|
| OpenShift AI dashboard | Customer-facing dashboard for available and installed applications, learning resources, administrative functions, and data science projects |
| Model serving | Deployment of trained machine-learning models behind API endpoints for production applications |
| AI pipelines | Portable ML workflows using containerized pipeline steps |
| Jupyter self-managed | Standalone workbench experience for developing ML models in JupyterLab |
| Distributed workloads | Parallel multi-node training or data processing to reduce task duration and handle larger or more complex workloads |
| Retrieval-Augmented Generation | RAG capabilities through the integrated Llama Stack Operator, combining model inference, semantic retrieval, and vector database storage inside a project |

## Management Layer

The Red Hat OpenShift AI Operator is the management-layer meta-operator. It
deploys and maintains OpenShift AI components and sub-operators.

Do not infer exact operator-managed CR fields from this chapter. Use the
installation, managing OpenShift AI, or component-specific documentation for CR
shape.

## Predefined Projects

When using predefined projects, installation creates these projects:

| Project | Official role |
|---------|---------------|
| `redhat-ods-operator` | Contains the Red Hat OpenShift AI Operator |
| `redhat-ods-applications` | Includes the dashboard and other required OpenShift AI components |
| `rhods-notebooks` | Default project for basic workbenches |

The chapter states that custom projects can be specified if needed.

## Application Project Boundary

Users or data scientists must create additional projects for applications that
use machine-learning models.

Independent software vendor applications must not be installed in namespaces
associated with OpenShift AI. For this demo, place custom applications, MCP
servers, databases, upload jobs, and scenario services in explicit demo
application namespaces rather than in `redhat-ods-*` or `rhods-notebooks`.

## Unresolved Items

This chapter does not define:

- exact Subscription package names or channels
- `DataScienceCluster` or `DSCInitialization` fields
- component management spec fields
- dashboard labels or annotations
- model serving runtime configuration
- Llama Stack CR fields

Use the relevant official component chapter and schema verification before
writing GitOps for those items.
