# README Completion And Alignment Review

## Scope

This review covers the current documentation state for the "From Vibe Coding to Agentic Engineering" extension.

Reviewed documentation:

- root `README.md`;
- `docs/README.md`;
- `docs/developer-workflow/README.md`;
- planned stage READMEs `100-170`;
- supporting analysis notes in `docs/developer-workflow/`;
- `adnan-drina/coding-exercises` local app-repo planning branch.

The review checks completion against the planned README pattern, alignment across the storyline, repository-boundary clarity, and remaining implementation gaps.

## Review Summary

The documentation is structurally complete for a planning branch. The planned `100-170` stage READMEs all follow the agreed hybrid structure, all stage pages clearly state that deploy and validate scripts are not implemented yet, and the current storyline is internally coherent.

The biggest alignment improvement since the last iteration is that the application story is now explicit:

```text
rhpds/mca-coolstore = brownfield modernization source
adnan-drina/coding-exercises = repository to rename to coolstore-inventory-service
coolstore-inventory-service = Quarkus source, app-local GitOps state, `.tekton/` Pipelines-as-Code assets, rollout notes, promotion notes, and rollback evidence
```

The biggest remaining gap is live implementation readiness. The README set is strong as a design and planning artifact, and the app repository now has a Quarkus scaffold plus static delivery assets, but the repository is not yet renamed and no live cluster validation has been performed for the planned developer workflow stages.

## Automated Checks

Completed checks:

- all planned stage READMEs contain the required section headings;
- all planned stage READMEs include the static `Deploy And Validate` disclaimer;
- no missing local Markdown links were found across the reviewed local docs;
- static stage-flow validation still passes for implemented stages `010-090`;
- shell syntax checks pass for existing workshop scripts;
- the current `coding-exercises` Quarkus tests and package build pass in the app repository.

## Completion Matrix

| Area | Current State | Completion | Main Gap |
|------|---------------|------------|----------|
| Root `README.md` | Clearly explains platform story and points to the planned developer workflow extension | High | Does not need to enumerate every supporting analysis page; the developer-workflow index now owns that detail. |
| `docs/README.md` | Correctly indexes the developer workflow extension as documentation-only | High | No immediate issue. |
| Developer workflow index | Strong overview, source posture, stage table, supporting analysis links, implementation policy, and accepted next decisions | High | Needs updates whenever frontend, eval, standards-corpus, or live-validation choices are made. |
| Stage 100 | Good governed entry-point story with Developer Hub, model path, source, app-local GitOps, pipeline, and evidence links | Medium-high | Requires real catalog entities, TechDocs, model metadata, and workspace launch links. |
| Stage 110 | Now aligned to the renamed `coolstore-inventory-service` direction and the first Continue task | Medium | Needs the actual Continue exercise after Quarkus scaffold or source slice exists. |
| Stage 120 | Strong quality-bar breakpoint narrative | Medium | Needs the selected near-miss example, known-bad prompt, expected-good output, and eval artifact. |
| Stage 130 | Strong OpenCode governance story with rules, skills, MCP, AgentOps, tracing, and eval-driven development | Medium-high | Needs real `AGENTS.md`, skills, permission boundaries, MCP config, and trace/eval examples. |
| Stage 140 | Strong target-service framing around `coolstore-inventory-service`, Red Hat build of Quarkus 3.27.x, Java 21, in-memory first slice, and later PostgreSQL path | High | Needs repository rename and later persistence iteration. |
| Stage 150 | Strong single-repo app-local GitOps and `.tekton/` Pipelines-as-Code boundary | Medium-high | Needs OpenShift Pipelines/Pipelines-as-Code installed and a live PipelineRun. |
| Stage 155 | Strong trusted supply-chain framing across app, AI, MCP, skills, and agent artifacts | Medium | Needs concrete tool decisions for SBOM, signing, provenance, scanning, policy gates, and evidence storage. |
| Stage 160 | Strongest implementation storyline because `mca-coolstore`, `mca-devspaces`, MTA, Developer Lightspeed, and Scribe are now mapped | Medium-high | Needs exact execution path, standards corpus, Scribe deployment mode, rule test examples, and MTA validation run. |
| Stage 170 | Good horizon stage using Red Hat agent mesh pattern, AgentOps, tracing, evals, and BYOA/OpenClaw/Kagenti concepts | Medium | Should remain a horizon until earlier stages produce real artifacts and traces. |
| `mca-coolstore` assessment | Strong brownfield app decision record | High | Open decisions remain around secondary Quarkus comparison, standards source, and local audit JAR provenance. |
| Quarkus target-service assessment | Strong target-service decision record | High | Needs live validation and later persistence choices. |
| `coding-exercises` app-repo plan | Good transition artifact for the future renamed service repo | High | App repo still contains Python exercise content and has not been renamed. |
| `dls-devspaces` map | Strong Stage 160 workspace reference | Medium-high | Needs decision on whether to adapt the custom workspace image pattern. |
| `scribe` MCP map | Strong Scribe placement for MTA rule generation | Medium-high | Needs actual MCP deployment mode and agent permission design. |

## Alignment Findings

### Strong Alignment

The stage sequence now reads coherently:

```text
Developer Hub entry
-> Continue-based IDE assistance
-> quality-bar breakpoint
-> OpenCode agentic engineering
-> Coolstore Inventory Quarkus target
-> governed pipeline and GitOps handoff
-> trusted software supply-chain evidence
-> MTA and Developer Lightspeed modernization
-> agent mesh modernization horizon
```

The two-track application story is also coherent:

- `mca-coolstore` carries brownfield modernization, tests-first pressure, MTA findings, Scribe-generated rule workflow, and Developer Lightspeed evaluation.
- `coolstore-inventory-service` carries the Quarkus golden path, pipeline, GitOps, supply-chain, and deployment story.

### Alignment Fixes Applied During This Review

- Stage 110 no longer says the code target or first task is broadly deferred. It now points to the future renamed `coolstore-inventory-service` repository and names README, API, and test-plan alignment as the first Continue task.
- Stage 130 no longer says the exact code target is broadly deferred. It now points to the future renamed `coolstore-inventory-service` repository and names the reservation endpoint as the first bounded OpenCode task.
- The `coding-exercises` README now marks its original Python quick start as legacy context until the Quarkus service reshape happens, and the planning docs record that Python material should move under `legacy/python-exercises/` after the scaffold exists.
- Stage 140 now records Red Hat build of Quarkus `3.27.x` with Java 21 and the OpenShift Developer Catalog / Red Hat PostgreSQL image path.
- Stage 150 now uses a single service repository with `gitops/` and `.tekton/` paths for the first demo instead of requiring another repository.
- The app repository now has the first static delivery packet: `Containerfile`, `.tekton/pull-request.yaml`, `gitops/base`, `gitops/overlays/dev`, delivery setup notes, and updated evidence records.

### Remaining Alignment Gaps

The following gaps are acceptable for a planning branch but should be closed before executable implementation:

- The app repository name is still `coding-exercises` locally, so downstream docs, Dev Spaces references, and Developer Hub links must be updated when it is renamed.
- Stage 140 mentions frontend standards as part of the broader golden-path ambition, but the first target-service slice does not require a frontend. This should stay explicitly deferred unless a frontend demo is added.
- Stage 150 adopts app-local `gitops/` and `.tekton/` directories, but live OpenShift Pipelines/Pipelines-as-Code validation is still open.
- Stage 155 identifies the evidence categories but not the concrete product/tool path for each evidence item.
- Stage 160 is well sourced, but the exact standards corpus and generated-rule evaluation set are still missing.

## Readiness By Iteration

### Ready For Discussion

These documents are ready for architectural review and annotation:

- developer workflow index;
- Stage 100-170 READMEs;
- `mca-coolstore` candidate assessment;
- Quarkus target-service options;
- `coding-exercises` app-repo plan;
- Scribe MCP map;
- `dls-devspaces` map.

### Ready For Implementation Planning

These decisions can now move into implementation planning:

- single service repository with source, app-local GitOps, `.tekton/` Pipelines-as-Code assets, and evidence;
- `coolstore-inventory-service` as the Quarkus target;
- `mca-coolstore` as the brownfield modernization source;
- Scribe as a Stage 160 candidate MCP tool;
- `mca-devspaces` as a Stage 160 workspace reference.

### Not Ready For Live Demo

These areas are not ready for live demo execution:

- repository rename from `coding-exercises` to `coolstore-inventory-service`;
- live PipelineRun, live image digest, and live app-local GitOps deployment;
- generated SBOM, scan, signature, provenance, and policy-gate evidence;
- Developer Hub registration for the new app and GitOps resources;
- real Continue/OpenCode tasks against the Quarkus service;
- live MTA, Developer Lightspeed, Scribe, RAG, AgentOps, or agent mesh execution;
- cluster-backed validation for stages `100-170`.

## Recommended Next Work

1. Plan the repository rename from `coding-exercises` to `coolstore-inventory-service`, including Dev Spaces and Developer Hub link updates.
2. Validate the `.tekton/` Pipelines-as-Code packet in a cluster with OpenShift Pipelines/Pipelines-as-Code installed.
3. Decide the live GitOps registration path for `gitops/overlays/dev`.
4. Define which Stage 155 evidence controls are advisory versus blocking after the first PipelineRun.
5. Define the Stage 160 standards corpus and first Scribe-generated MTA rule test.
