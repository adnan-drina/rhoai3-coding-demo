# KFP Pipeline Patterns (repo authoring guidance)

Repo-owned conventions for KFP v2 pipelines in this demo. The reference
implementation is the Stage 050 qualification pipeline:
`stages/050-model-evaluation/qualification/pipeline.py` (source) and
`compile.py` (compiler), output in
`gitops/stages/050-model-evaluation/050-model-qualification/pipeline/`.
Product behavior (pipeline server, storage modes, caching levels, runs) is in
the OpenShift AI 3.5 "Working with AI pipelines" guide; see `rhoai-ai-pipelines`.

## Layout

- `stages/<stage>/<name>/pipeline.py`: components and the `@dsl.pipeline`.
- `stages/<stage>/<name>/compile.py`: compiles to Kubernetes-native manifests
  (`kubernetes_manifest_format=True`, `KubernetesManifestOptions` with pipeline
  name, display name, version name, namespace, `include_pipeline_manifest=True`).
- Output YAML lives in the consuming component's `pipeline/` folder under
  `gitops/`, with a kustomization that puts the `Pipeline` one sync wave before
  its `PipelineVersion` (the version webhook needs the pipeline) and adds
  `SkipDryRunOnMissingResource=true`. Never edit the compiled YAML by hand.
- Each compile gets a new version name (`<pipeline>-v<N>`); the previous
  `PipelineVersion` is deleted by hand after the re-pin, because Argo CD does
  not prune it.

## SDK and images

- Compile with `kfp==2.16.1` and `kfp-kubernetes==2.16.1` on Python 3.11+;
  tasks install the compiling SDK version, and the runtime image's package
  index offers 2.16.1.
- `base_image` is always set, pinned by digest. Default: the RHOAI pipeline
  runtime image `odh-pipeline-runtime-minimal-cpu-py312-rhel9` (the
  `runtime-minimal` imagestream in `redhat-ods-applications`).
- `packages_to_install` pins exact versions. `pip_index_urls` replaces the
  default index; Stage 050 sets `https://pypi.org/simple` because the runtime
  image's index carries an old `eval-hub-sdk`. Tasks then need egress to PyPI.

## Components

- Lightweight Python components are hermetic: imports, constants and helpers
  inside the function body; nothing from module scope except values passed as
  parameters.
- Every input and output is typed. Use `NamedTuple` for several named
  outputs and `dsl.Output[dsl.Metrics]`, `dsl.Output[dsl.HTML]` or
  `dsl.Output[dsl.Artifact]` for dashboard-visible results.
- Validate inputs at the start and fail with an actionable `RuntimeError`.
- Credentials are never parameters. Tasks use the pod ServiceAccount token
  (`pipeline-runner-<dspa>`) and Secrets/ConfigMaps mounted through
  `kfp.kubernetes` (Stage 050 mounts the service CA ConfigMap
  `pipeline-tasks-service-ca`).
- Grant the runner ServiceAccount what the tasks call, in GitOps next to the
  pipeline server (`pipeline-runner-evalhub-access` in Stage 050).

## Task wiring

- One named component per step: deep-copy the component and set
  `component_spec.name`. Do not use `set_display_name`; the dashboard looks up
  logs and inputs by task key, which must equal the label.
- Step names start with a letter (`step-0-...`); Argo rejects task names that
  begin with a digit. The dashboard lays the graph out alphabetically, so
  numbered names keep the order readable.
- Optional steps take a `skip_*` parameter and exit early instead of using
  `dsl.If` when later steps must depend on them in a fixed order.
- Set requests and limits on every task, and `set_caching_options(False)` on
  steps that read live external state, even though the server has caching on.
- Keep pipeline source ASCII-only: the default pipeline-server MariaDB stores
  the spec in a `latin1` column
  (`LC_ALL=C grep -nP '[^\x00-\x7F]' pipeline.py` prints nothing).

## Runs

- Runs are created in the dashboard with an MLflow experiment, or by
  `POST /apis/v2beta1/runs` with `plugins_input.mlflow.experiment_name`. The
  KFP SDK `create_run_from_pipeline_*` helpers do not send it.
- Start with a cheap run (skip the long steps) before a full run.

## Reuse before authoring

Before writing a new component, check the Kubeflow
(`kubeflow/pipelines-components`) and Red Hat Data Services
(`red-hat-data-services/pipelines-components`) catalogs. Record the source,
path and image of an adopted component in the pipeline docstring; treat a
non-Red Hat image as a documented demo exception.

## Checklist

- [ ] docstring: purpose, graph, run parameters, how to compile
- [ ] base image pinned by digest; packages pinned
- [ ] components hermetic, typed, input-validated
- [ ] one named component per step, no `set_display_name`
- [ ] resources and caching set per task
- [ ] no credential parameters; runner RBAC in GitOps
- [ ] ASCII-only source; new version name; old version deleted after re-pin
