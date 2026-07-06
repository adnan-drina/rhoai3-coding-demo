---
name: rhoai-architecture-overview
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when describing, reviewing, or implementing the high-level Red Hat
  OpenShift AI Self-Managed architecture from the official architecture chapter:
  service-layer capabilities, the Red Hat OpenShift AI Operator management
  layer, default projects/namespaces, custom project boundaries, and the rule
  not to place ISV applications in OpenShift AI namespaces. Also use when
  creating README architecture narratives or GitOps namespace layouts that need
  to align with official RHOAI architecture. Do NOT use for specific component
  CR fields, operator install commands, or live troubleshooting; use the
  relevant component skill, official docs, and env-* skills.
---

# RHOAI Architecture Overview

Use this skill to ground project architecture narratives and namespace topology
in the official Red Hat OpenShift AI Self-Managed architecture chapter for the
active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill is high-level:
it identifies layers, included services, default projects, and namespace
boundaries, but it does not define component CR fields.

## Architecture Model

Use the official two-layer framing:

- **Service layer**: OpenShift AI dashboard, model serving, AI pipelines,
  self-managed Jupyter, distributed workloads, and RAG through the integrated
  Llama Stack Operator.
- **Management layer**: Red Hat OpenShift AI Operator as the meta-operator that
  deploys and maintains OpenShift AI components and sub-operators.

When writing README or GitOps architecture content, keep custom demo services
separate from product services. Label custom glue explicitly.

## Namespace Guidance

For predefined projects, align with the official namespace roles:

- `redhat-ods-operator`: Red Hat OpenShift AI Operator.
- `redhat-ods-applications`: dashboard and other required OpenShift AI
  components.
- `rhods-notebooks`: default project for basic workbenches.

Additional application projects are expected for workloads that use machine
learning models. Do not install independent software vendor applications in
namespaces associated with OpenShift AI.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. For architecture narratives, map every claimed capability to the official
   service-layer or management-layer component.
4. For GitOps namespace layout, keep product namespaces and demo application
   namespaces separate.
5. For implementation-specific fields or install commands, switch to the
   relevant component skill or official docs chapter.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/namespace-topology.md`
