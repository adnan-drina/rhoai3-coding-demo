# KFP Pipeline Patterns

Use active `stage-*/kfp/` content as the project reference for KFP v2 pipeline
authoring once a stage has been rebuilt. Stage 230 is being reset; do not treat
the old `stage-230-private-data-rag/kfp/` content as the preferred design.
Treat
`backup/legacy-implementation-2026-06-09/steps/step-12-mlops-pipeline/kfp/` and
old `steps/step-07-rag/kfp/` content as legacy examples only.

## Pipeline Definition

Each `kfp/pipeline.py` should include:

- a module docstring with KFP version, purpose, component list, DSPA reuse, and
  official docs reference
- module-level constants for pipeline wiring values such as secret names and PVC
  names
- small private helper functions for repetitive task wiring
- `@dsl.pipeline` with `name`, `description`, and `pipeline_root`
- typed parameters with defaults
- clear step comments
- explicit task ordering with data dependencies or `.after()` where needed
- task resource requests and limits
- caching disabled for demo freshness unless there is a deliberate exception
- a compiler block for local compilation

Compiled YAML should go under repo artifacts and be uploaded by runner scripts,
not committed as continuously reconciled GitOps state unless explicitly required.

## Component Style

- Put each component in its own file under `kfp/components/`.
- Match filename and function name.
- Use `@dsl.component` or `@component` consistently with local style.
- Always specify a base image; do not rely on the KFP default Python image.
- Prefer the RHOAI base image used by the existing demo unless the task requires
  another supported Red Hat image.
- Pin minimum package versions in `packages_to_install`.
- Add `pip_index_urls` only when required by packages unavailable from the Red
  Hat Python index; remember that KFP replaces, not appends, default index URLs.
- Search reusable component catalogs before authoring a new local component:
  - `kubeflow/pipelines-components` for generic, cross-platform components
  - `red-hat-data-services/pipelines-components` for OpenShift AI-aligned or
    Red Hat Data Services-dependent components
- If a catalog component is reused or adapted, record source repository,
  component path, stability level, last verification posture, input/output
  contract, base image posture, and reason for any local modifications.

## Reusable Component Anatomy

Use the upstream component catalog layout as the reference when a component
should be reusable beyond one stage:

```text
components/<category>/<subcategory>/
  __init__.py
  OWNERS
  README.md
  shared/
  <component_name>/
    __init__.py
    component.py
    metadata.yaml
    OWNERS
    README.md
    tests/
```

Pipeline catalog examples follow the same idea:

```text
pipelines/<category>/<subcategory>/
  __init__.py
  OWNERS
  README.md
  shared/
  <pipeline_name>/
    __init__.py
    pipeline.py
    metadata.yaml
    OWNERS
    README.md
    tests/
```

This repo does not need to copy that directory structure for every stage-local
pipeline. Use it when building a component that is meant to become a reusable
asset. For stage-local components, keep the same discipline: clear metadata in
comments or docs, typed inputs/outputs, owners implied by the stage, and tests
or smoke validation where practical.

## Hermetic Components

Lightweight Python Components must be self-contained:

- only standard library and KFP imports should appear at module top level in
  reusable component files
- imports inside the function body
- heavy dependencies such as `pandas`, `torch`, `datasets`, model clients, or
  cloud SDKs imported inside the component function body
- constants used by the component defined inside the function
- no references to module-level helper symbols unless passed through
  `additional_funcs`
- utility helpers passed through `additional_funcs` must themselves be
  self-contained

## Reusable Component Design Rules

- Validate inputs at the start of the component so bad paths, credentials,
  incompatible parameters, missing checkpoints, or unsupported formats fail
  quickly.
- Use descriptive parameter names and common prefixes for related fields, such
  as `model_name`, `model_path`, `model_version`, `s3_bucket`, and
  `s3_prefix`.
- For reusable data components, support the input modes that make sense for the
  task: KFP artifacts, S3 URLs or object-storage references, and workspace or
  file paths.
- Keep each component focused on one task. Compose multi-step behavior in a
  pipeline rather than hiding it in one large component.
- Use component stability labels in docs or metadata when a component becomes
  reusable: `alpha` for early/demo use, `beta` for working but evolving
  behavior, and `stable` only after repeated validation.
- Revalidate reusable components periodically. Treat components without recent
  validation as candidates for review before reuse.
- Start with small fixtures or sampled data before running full corpora,
  long-running training, or GPU-backed tasks.
- Prefer one-component or two-step smoke pipelines before assembling the full
  workflow.
- Use KFP control flow intentionally:
  - `dsl.ParallelFor` for independent items or splits
  - `dsl.If` / `dsl.Else` for optional work such as preprocessing already done
  - nested pipelines only when a subworkflow is itself reusable and tested
- Validate Kubernetes extension behavior inside control-flow blocks with a live
  RHOAI run, not compile alone. In the active RHOAI 3.4 runtime, Kubernetes
  Secret mounts on tasks nested inside `dsl.ParallelFor` are resolved from the
  parent DAG; a pipeline-level secret-name parameter can compile locally but
  fail at the nested task driver with `parent DAG does not have input parameter`.
  Use a GitOps-owned deterministic Secret name for nested loop tasks when the
  stage owns that Secret.
- Compile with the current KFP compiler before running in OpenShift AI.

## Types And Artifacts

- All component inputs and outputs need type annotations.
- Use KFP artifact types for Dashboard visibility:
  - `Output[Metrics]` for metrics
  - `Output[ClassificationMetrics]` for classification plots
  - `Output[HTML]` for reports
  - `Output[Model]` for model lineage
  - `Output[Dataset]` for dataset lineage
- Use `typing.NamedTuple` for multiple named outputs.
- Use `.output` for single unnamed outputs and `.outputs["name"]` for named
  outputs.

## Image And Dependency Posture

- KFP component `base_image` is an explicit runtime dependency. It is not an
  operator-managed operand image.
- For OpenShift AI-aligned or Red Hat Data Services-derived components, prefer
  approved Red Hat images or images explicitly allowed by the source repository.
- For generic upstream components, review custom image guidance and record any
  non-Red Hat image as a demo exception before adopting it into this repo.
- Use `packages_to_install` for small, deliberate runtime dependencies.
- Use a custom image when dependencies are heavy, slow to install, require
  system packages, or must be pre-scanned.
- Do not present a component image as Red Hat-supported unless the Red Hat
  source says so.

## Runtime Data Flow

Project convention for shared intermediate data is the AI Pipelines per-run
workspace configured with `dsl.PipelineConfig(workspace=...)`. Pass
`dsl.WORKSPACE_PATH_PLACEHOLDER` into components and use descriptive
subdirectories such as:

```python
SHARED = Path(workspace_path)
DATASET_DIR = SHARED / "dataset"
MODEL_DIR = SHARED / "model"
METRICS_DIR = SHARED / "metrics"
```

Do not pre-create a GitOps-managed EBS PVC for KFP task-to-task file exchange.
`WaitForFirstConsumer` PVCs can block Argo CD sync waves before a pipeline pod
exists to bind them.

For RHOAI 3.4 DSPA-backed runs, make the workspace PVC access mode explicit in
the compiled IR. An empty `pvcSpecPatch` can fail run creation with
`workspace PVC spec must specify accessModes`:

```python
dsl.PipelineConfig(
    workspace=dsl.WorkspaceConfig(
        size="5Gi",
        kubernetes=dsl.KubernetesWorkspaceConfig(
            pvcSpecPatch={"accessModes": ["ReadWriteOnce"]},
        ),
    ),
)
```

## Control Flow

Use the simplest control flow that makes the demo clear:

| Pattern | Use when |
|---------|----------|
| `dsl.ParallelFor` | processing independent items |
| `RuntimeError` quality gate | a failed step should be visible in the Dashboard |
| `dsl.If` / `dsl.Else` | branches both produce valid downstream outputs |
| `dsl.ExitHandler` | cleanup must happen regardless of success |

Step 12 uses failure as a visible quality gate because it is clearer in a demo
than a skipped branch.

## Caching

Disable caching for demo tasks because demo runs should execute fresh, external
state changes between runs, and cached results can hide failures. For production
pipelines, enable caching only on expensive deterministic steps.

## Runner Scripts

Runner scripts should:

- source the repo helper library for logging, local config, and login checks
- parse `--key=value` options for non-trivial inputs
- create or reuse the shared KFP virtual environment at repo root
- compile pipeline YAML when needed
- use DSPA-compatible KFP client authentication
- upload a new pipeline version per run
- for DSPA servers that use Kubernetes API pipeline storage, create or update
  `Pipeline` and timestamped `PipelineVersion` custom resources instead of
  relying on route-based binary upload; keep `spec.pipelineSpec` and
  `spec.platformSpec` from the compiled KFP output
- create or reuse the target experiment
- submit a new run with explicit parameters
- record a small run-evidence ConfigMap or equivalent validation marker when a
  deployment script depends on the run succeeding

Keep runner behavior idempotent: repeated runs should create new versions/runs
without corrupting existing pipeline or experiment objects.

## Modular Pipeline Assembly

When building a pipeline from reusable components:

1. Write the pipeline goal and unique business logic in the stage plan.
2. Search reusable catalogs before creating new code.
3. Select the smallest component set that proves the workflow.
4. Pass outputs from one component into the next through KFP outputs/artifacts,
   not ad hoc shared global state.
5. Parallelize only independent work and validate resource limits first.
6. Use conditional logic for optional steps such as skip preprocessing,
   evaluate only if training passes, or deploy only if metrics meet a gate.
7. Run the smallest fixture first, then scale the same compiled pipeline to the
   full data set.
8. Preserve pipeline run evidence: parameters, artifacts, metrics, logs, and
   experiment grouping.

## GitOps Integration

Pipeline infrastructure such as PVCs, RBAC, and supporting services belongs in
GitOps. Pipeline definitions are compiled and uploaded to DSPA through runner
scripts. They are not continuously reconciled resources by default.

## RAG / Docling Reuse Pattern

For the rebuilt Stage 230, the preferred Docling KFP implementation reference
is the Red Hat-documented
`opendatahub-io/data-processing/kubeflow-pipelines` tree, not the previous
whoami pipeline. Use the official-doc-linked `stable` branch by default and
compare `main` only when a newer reference implementation is intentionally
selected. Active Stage 230 intentionally uses `main/kubeflow-pipelines`
because the user selected the newer modular Docling implementation.

The target ingestion shape is:

```text
ODF/NooBaa source OBC
  -> data-processing import_pdfs
  -> docling-standard or docling-vlm conversion
  -> optional docling_chunk HybridChunker output
  -> Files API / Vector Stores API ingestion
  -> Llama Stack hybrid retrieval validation
```

Apply these rules:

- start with `docling-standard` for ordinary PDFs, OCR, table structure,
  Markdown output, Docling JSON output, and optional chunk JSONL output
- preserve the modular task graph in the OpenShift AI Pipelines dashboard:
  source selection, `import-pdfs`, `create-pdf-splits`,
  `download-docling-models`, `docling-convert-standard`, `docling-chunk`, and
  separate publish and final repo-specific normalization components
- do not expect Docling data-preparation components to appear in the RHOAI
  project `Deployments` tab. KFP components are validated through the
  `Pipelines` page, run graph, task logs, metrics, and S3 artifacts. The
  `Deployments` tab is for served endpoints such as KServe `InferenceService`
  resources.
- use `docling-vlm` only for complex layouts, scanned or image-heavy
  documents, remote VLM conversion, or custom page-level instructions
- preserve the upstream `ParallelFor` split pattern for scale-out conversion;
  adjust parallelism to the workspace PVC access mode and project resources
- keep Dashboard-visible `Output[Metrics]` summaries for ingestion counts
- use the `data-processing-docling-pipeline` Secret pattern for S3 and remote
  VLM configuration, but generate the Secret from local environment values or
  project connection data instead of committing credentials
- for S3 input, provide `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
  `S3_BUCKET`, and `S3_PREFIX`
- for remote VLM conversion, provide `REMOTE_MODEL_ENDPOINT_URL`,
  `REMOTE_MODEL_API_KEY`, and `REMOTE_MODEL_NAME`
- use a fixed DSPA artifact bucket only when the
  `DataSciencePipelinesApplication` spec needs a stable
  `objectStorage.externalStorage.bucket` value
- read source corpus objects from the active project `ObjectBucketClaim`
  Secret and ConfigMap generated by ODF/NooBaa; discover generated bucket names
  at runner time, not in committed GitOps manifests
- for DSPA artifact storage backed by in-cluster NooBaa, keep the DSPA
  `objectStorage.externalStorage` endpoint and the pipeline S3 Secret endpoint
  consistent. If the pipeline server was created with the wrong endpoint,
  recreate the DSPA; do not treat generated workflow-controller ConfigMaps as
  durable desired state
- review upstream component base images before adoption. KFP component images
  are explicit runtime dependencies; classify them as Red Hat image, reviewed
  custom image, or demo exception
- for Docling components, make runtime cache behavior explicit. If a notebook or
  component image runs with a non-writable application home, set writable cache
  paths such as `HOME`, `XDG_CACHE_HOME`, `EASYOCR_MODULE_PATH`, and
  `TORCH_HOME` under `/tmp`. Disable OCR for text-native PDF smoke paths; enable
  OCR only when the target corpus requires it and the runtime image has been
  validated for the required model downloads/cache writes.
- use the active Llama Stack client/API shape from `rhoai-llama-stack` and the
  live client. For the current RHOAI 3.4 line, create stores through
  `client.vector_stores.create(...)`, upload source text through
  `client.files.create(...)`, attach files with
  `client.vector_stores.files.create(...)`, and validate retrieval with
  `client.vector_stores.search(...)`. Do not use the removed
  `client.vector_dbs` or `client.tool_runtime.rag_tool` paths.
- pass Llama Stack chat/completion model IDs from a dedicated pipeline
  parameter, not from the Kubernetes MaaS resource name. Validate the selected
  value against `client.models.list()` before assuming that a short model name
  such as `nemotron-3-nano-30b-a3b` is callable.
- keep the vector store embedding dimension aligned with the actual embedding
  model output. In Stage 230, `sentence-transformers/all-MiniLM-L6-v2` uses a
  384-dimensional vector store; a 768-dimensional store causes file attachment
  failures during vectorization.
- introduce Docling/KFP when the stage processes RHOAI product-document PDFs
  or another unstructured corpus

## New Pipeline Checklist

- [ ] module docstring with KFP version, purpose, and docs reference
- [ ] reusable component catalog search recorded
- [ ] selected component stability and source recorded when reused
- [ ] module constants for wiring values
- [ ] helper for resource requests and limits
- [ ] typed pipeline parameters with defaults
- [ ] descriptive parameter names and common prefixes
- [ ] explicit task ordering
- [ ] small-fixture test path before full data
- [ ] caching disabled for demo freshness
- [ ] components split into separate files
- [ ] component imports inside function bodies
- [ ] heavy dependencies imported only inside component functions
- [ ] input validation at component start
- [ ] typed component inputs and outputs
- [ ] Dashboard-visible artifacts where useful
- [ ] base image and dependency posture recorded
- [ ] runner script sources repo helper library
- [ ] pipeline infrastructure in GitOps

## References

- KFP v2 docs: https://www.kubeflow.org/docs/components/pipelines/
- Current RHOAI baseline AI pipelines docs: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_ai_pipelines/
- Red Hat Developer reusable components article: https://developers.redhat.com/articles/2026/06/03/build-modular-ai-pipelines-openshift-ai-and-reusable-components
- Generic component catalog: https://github.com/kubeflow/pipelines-components
- Red Hat Data Services component catalog: https://github.com/red-hat-data-services/pipelines-components
