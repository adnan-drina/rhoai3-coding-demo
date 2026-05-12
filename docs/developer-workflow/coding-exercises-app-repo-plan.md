# coding-exercises To coolstore-inventory-service Repository Plan

## Purpose

This note maps `https://github.com/adnan-drina/coding-exercises` to the planned developer workflow stages and records the accepted rename direction.

The repository is the candidate service repository for `coolstore-inventory-service`. After the direction is accepted, the repository should be renamed to `coolstore-inventory-service`.

Local checkout used for this assessment:

```text
/Users/adrina/Sandbox/coding-exercises
```

Branch created for adaptation planning:

```text
feature/coolstore-inventory-service-plan
```

## Recommendation

Use a single service repository for the first live demo.

Recommended shape:

- `coding-exercises` is renamed to `coolstore-inventory-service`;
- Quarkus source lives at the repository root;
- app-local GitOps desired state lives under `gitops/`;
- Tekton or OpenShift Pipelines assets live under `tekton/`;
- rollout, promotion, and rollback evidence lives in repository documentation.

This keeps the first demo simpler than a multi-repository application-plus-deployment split while still preserving the important enterprise boundary: the platform repository remains separate from the application repository. A later iteration can split deployment state into another repository if the demo needs to teach stricter environment ownership.

## Current Repository Shape

The current `coding-exercises` repository is a useful AI developer-workspace shell:

- it has a Dev Spaces `devfile.yaml`;
- it has Continue configuration in `.vscode/config.yaml`;
- it has OpenCode configuration in `.opencode/opencode.json`;
- it has starter and solution exercises for small Python games.

It is not yet the Quarkus target service:

- no Java or Quarkus project exists;
- no Maven build exists;
- no `catalog-info.yaml` exists;
- no tests, pipeline, OpenShift manifests, or GitOps manifests exist for the target service.

## What Was Added To The App Repo

The local `coding-exercises` checkout now has a documentation-only adaptation plan:

```text
docs/coolstore-inventory-service-repository-plan.md
```

The app repo README now points to that plan and records the repository direction.

No Quarkus source code has been added yet.

## Target Responsibilities

The renamed service repository should own:

- Quarkus service source and tests;
- service README and TechDocs-ready documentation;
- `AGENTS.md` and project rules for OpenCode;
- Continue and OpenCode configuration templates;
- Dev Spaces workspace configuration;
- Developer Hub catalog metadata for the application component;
- validation commands and local developer guidance;
- app-local Kustomize bases and overlays under `gitops/`;
- Tekton or OpenShift Pipelines assets under `tekton/`;
- image reference update guidance;
- rollout, promotion, and rollback evidence;
- references to approved pipeline templates.

## Stage Mapping

| Stage | Repository Impact |
|-------|-------------------|
| Stage 100 | Developer Hub should show `mca-coolstore` as the brownfield source and `coolstore-inventory-service` as the target service component with source, app-local GitOps, pipeline, rollout, promotion, and rollback links. |
| Stage 110 | Continue can start in the renamed service repo for README, API, and test-plan alignment after the Quarkus scaffold exists. |
| Stage 120 | The app repo becomes the quality-bar breakpoint for tests, README accuracy, dependency choices, and no invented deployment claims. |
| Stage 130 | OpenCode rules and skills belong in the service repo first, with app-local GitOps write paths disabled unless explicitly approved. The first bounded coding task is `POST /api/inventory/{itemId}/reservations`. |
| Stage 140 | The app repo is where the Quarkus inventory service is scaffolded or seeded. |
| Stage 150 | Pipeline generation should create reviewable `tekton/` and `gitops/` assets in the service repo for the first demo. |
| Stage 155 | The service repo records source, image, pipeline, app-local GitOps, promotion, rollout, and rollback evidence for the first demo. |
| Stage 160 | The app repo is the target comparison point for the `mca-coolstore` brownfield inventory behavior. |
| Stage 170 | Agent mesh patterns can coordinate source, tests, docs, supply chain, app-local GitOps, and platform agents across the workflow. |

## Implementation Guidance

First implementation branch:

- keep the current app-repo branch as planning-only until the Quarkus baseline is accepted;
- preserve the existing Continue and OpenCode setup because it is useful for the demo;
- rename the repository to `coolstore-inventory-service` after this direction is accepted;
- use Red Hat build of Quarkus `3.27.x` with Java 21 for the first scaffold;
- use the OpenShift Developer Catalog / Red Hat PostgreSQL image path for the first PostgreSQL demo;
- archive the Python game exercise content under `legacy/python-exercises/` only after the Quarkus service is scaffolded;
- add `AGENTS.md`, `catalog-info.yaml`, and a real service README before adding code;
- keep app-local GitOps desired state under `gitops/` and pipeline assets under `tekton/` when Stage 150 becomes executable;
- use Continue first for README, API, and test-plan alignment, then use OpenCode for the bounded reservation endpoint task.

## Open Decisions

- Which downstream Dev Spaces, Developer Hub, and README links must be updated after the GitHub repository rename?
- Which exact directory names should hold rollout notes, promotion notes, and rollback evidence?
- Which approved Tekton or OpenShift Pipelines template should seed `tekton/`?
