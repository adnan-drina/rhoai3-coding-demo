# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Workflow Model

Red Hat's model customization workflow includes:

- set up a supported workbench and Python package source
- prepare data for AI consumption
- generate synthetic data where useful
- train or fine-tune a model using prepared data
- track experiments
- distribute training when workloads require more capacity
- improve responses with inference-time scaling
- serve and consume the customized model

## Red Hat Python Index And Support Posture

The Red Hat Python index provides Red Hat-built package artifacts for model
customization workflows. The guide positions it as the trusted package source
for supported OpenShift AI base images and disconnected environments.

Package support boundary:

- Supported: installation of the packages from the Red Hat Python index onto a
  supported OpenShift AI environment when using provided base images.
- Supported: the underlying OpenShift AI platform and infrastructure according
  to its lifecycle.
- Not supported as product behavior: issues from custom flows or applications
  built with the packages.
- Not supported as product behavior: mixing packages outside the packages
  provided through Red Hat Python index base images.

Package names used by the guide:

- `docling`
- `sdg-hub`
- `training-hub`
- `training-hub[cuda]`
- `its-hub`
- `its-hub[lm]`
- `its-hub[experimental]`

Disconnected environments can mirror the versioned Red Hat Python index that
matches the active OpenShift AI release and runtime.

## Workbench And Examples

The guide starts from a JupyterLab workbench that is preconfigured to use the
Red Hat Python index. Most default OpenShift AI workbench images are
preconfigured for the index, with an exception noted for the Jupyter TensorFlow
ROCm Python 3.12 image, which requires a custom workbench image based on the
RHAI ROCm base image referenced by the guide.

Example repositories and branches captured by the guide:

- Docling data processing: `https://github.com/opendatahub-io/data-processing.git`,
  branch `stable`, directory `notebooks/`
- SDG Hub: `https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub.git`,
  branch `main`, directory `examples`
- Training Hub: `https://github.com/Red-Hat-AI-Innovation-Team/training_hub.git`,
  branch `main`, directory `examples`
- End-to-end Knowledge Tuning:
  `https://github.com/red-hat-data-services/red-hat-ai-examples.git`,
  branch `main`, directory `knowledge-tuning`

## Data Preparation With Docling

Docling prepares unstructured inputs for consumption by large language models.
The guide uses it for:

- converting documents such as PDFs to structured formats such as Markdown
- chunking documents into meaningful pieces
- extracting information using templates
- selecting diverse subsets of input data
- preparing RAG data sets

Docling processing can run interactively in notebooks or as KFP components in
AI Pipelines. Custom runtime images can be required when pipeline execution
needs Docling dependencies.

The focused data-preparation chapter points to the `opendatahub-io/data-processing`
repository on the `stable` branch. Its examples are the preferred starting
point when this demo needs to process unstructured documents before RAG
ingestion. Treat them as Red Hat-documented examples, then adapt them into the
repo's GitOps, scripts, and validation model.

The `kubeflow-pipelines` tree provides two Docling KFP starting points:

- `docling-standard`: first choice for ordinary PDFs and documents that need
  OCR, table structure, image export control, Markdown output, Docling JSON
  output, and optional HybridChunker chunk JSONL output.
- `docling-vlm`: use only for complex layouts, scanned or image-heavy
  documents, remote VLM conversion, custom instructions, or image descriptors.

Both pipelines support HTTP/S input and S3-compatible input. S3 runs mount a
Secret named `data-processing-docling-pipeline` with endpoint, access key,
secret key, bucket, and prefix keys. Remote VLM runs use the same Secret name
with endpoint URL, API key, and model name keys. These values must be generated
from environment-local connection data and not committed.

Use case mapping:

- Convert: PDF or other unstructured documents to structured formats such as
  Markdown, with or without a vision-language model.
- Chunk: split documents into smaller semantically meaningful pieces before
  indexing or training.
- Extract information: template-based extraction for structured fields from
  documents such as invoices, forms, or regulatory publications.
- Select subsets: reduce corpus size while preserving diversity and coverage.
- RAG preparation: end-to-end document processing before vector-store ingestion.

KFP automation mapping:

- Standard pipeline: use for normal documents containing text and structured
  elements.
- VLM pipeline: use for complex or difficult layouts, custom instructions, or
  image descriptors.
- Custom runtime image: use when pipeline execution requires Docling
  dependencies that are not present in the base runtime image.
- Branch policy: prefer the official-doc-linked `stable` branch. Use `main`
  only when a newer KFP implementation is intentionally selected and recorded.
- Output policy: inspect converted Markdown and Docling JSON before indexing;
  inspect chunk JSONL before sending data to Files API or Vector Stores API.

## Synthetic Data Generation With SDG Hub

SDG Hub provides modular synthetic data generation workflows. The guide points
to examples for:

- Knowledge Tuning
- text analysis for structured insights
- RAG evaluation
- red teaming and AI safety
- agentic use cases

The guide also includes KFP examples for SDG workflows, including domain
customization data generation and a basic KFP pattern.

## Training Hub Fine-Tuning

Training Hub simplifies fine-tuning and customization of foundation models.
The guide covers:

- SFT: supervised fine-tuning for supervised data sets, single-node or
  multi-node distributed training, configurable epochs, batch size, and
  learning rate
- OSFT: orthogonal subspace fine-tuning for controlling how much existing
  model behavior to preserve, with single-node or multi-node support
- LoRA and QLoRA: parameter-efficient fine-tuning that trains low-rank
  adaptation matrices rather than full model weights

Algorithm/backend mapping captured by the guide:

- SFT uses `instructlab.training`
- OSFT uses `mini-trainer`
- LoRA/QLoRA uses `Unsloth`

Supported model architecture examples captured by the guide include GPT OSS,
Llama, Qwen 2.5, Qwen 3, Granite 3, Granite 4 MoE hybrid, Phi 3/4, and Mistral
families, with model-specific caveats in the official matrix.

Liger kernel caveat:

- if a listed OSFT model class fails or behaves unstably with `use_liger=True`,
  try `use_liger=False` and check current Liger support.

## Memory And Algorithm Tradeoffs

The Training Hub memory estimator currently supports SFT and OSFT. Use it to
estimate whether a model and training configuration fit the available GPU
memory before promising a live run.

Algorithm tradeoff guidance extracted from the guide:

- OSFT can preserve prior behavior and can be lighter for continual learning
  patterns, but adds unique matrix storage overhead.
- LoRA and QLoRA reduce memory by training low-rank adaptation matrices.
- QLoRA can still briefly require placing a Float16 model on the GPU, which can
  create a memory bottleneck.
- OSFT, SFT, and LoRA should be selected based on learning goal, memory
  budget, replay-data constraints, and training time.

## Training Hub In OpenShift AI

OpenShift AI can run Training Hub interactively in a notebook environment. The
guide recommends the Training Jupyter PyTorch CUDA Python notebook image for
in-workbench training because it is prepackaged with Training Hub libraries and
dependencies distributed through the Red Hat package index.

This mode is best for:

- small experiments
- quick iteration
- immediate feedback
- debugging from a running workbench

Use Kubeflow Trainer or AI Pipelines when the workflow needs distributed
training, long-running jobs, retraining schedules, or repeatable automation.

## MLflow Tracking With Training Hub

Training Hub can automatically log to MLflow.

Captured logging categories:

- training hyperparameters
- training metrics
- model configuration and architecture details
- run metadata such as timestamps, duration, and hardware configuration

In distributed training, only rank 0 logs to avoid duplicate entries.

Configuration can be passed through API parameters or environment variables:

- tracking URI: `mlflow_tracking_uri` or `MLFLOW_TRACKING_URI`, required
- experiment name: `mlflow_experiment_name` or `MLFLOW_EXPERIMENT_NAME`,
  optional
- run name: `mlflow_run_name` or `MLFLOW_RUN_NAME`, optional

Use `rhoai-mlflow` for MLflow platform setup, SDK authentication, storage, and
workspace access.

## Distributed Fine-Tuning

Kubeflow Trainer supports distributed fine-tuning with Training Hub. Use it
when a training workload requires multi-node or larger-scale orchestration.

Use `rhoai-distributed-workload-workflows` for Training Operator, Kubeflow
Trainer, `PyTorchJob`, `TrainJob`, image preparation, queueing, monitoring,
and user-side distributed workload troubleshooting.

## Inference-Time Scaling

Inference-time scaling improves response quality by generating multiple
candidate outputs and selecting one without modifying model weights. It
increases compute per query.

ITS Hub works with OpenAI-compatible endpoints, including models served by
vLLM on Red Hat OpenShift AI and external compatible APIs.

Prerequisites:

- Python 3.11 or later
- endpoint URL
- API key or documented no-key local endpoint behavior
- model name

Algorithms captured by the guide:

- Self-Consistency: generate multiple responses and select the most common
  answer
- Best-of-N: generate multiple candidates, score them, and select the best
  response
- Beam Search, Particle Filtering, and Entropic Particle Filtering for
  step-by-step reasoning with a process reward model and experimental package
  extra

Use ITS as an inference behavior pattern, not as model customization that
changes weights.

## End-To-End Workflows

The guide points to:

- a Knowledge Tuning notebook tutorial that combines Docling, Training Hub,
  and KServe deployment
- a Kubeflow Pipeline example that automates Knowledge Tuning steps
- a fine-tuning AI pipeline that fine-tunes, evaluates, and registers a model

Treat these examples as source-grounded starting points. They are not active
repo implementation until adapted to the clean-slate GitOps structure and
validated.

## Verification Signals

Expected signals:

- workbench uses a supported Red Hat AI package source
- required package imports succeed from the workbench
- example repository clone uses the documented branch and directory
- Docling converts or chunks data into the intended output format
- SDG examples generate expected synthetic outputs without leaking sensitive
  records
- Training Hub run starts and writes checkpoints or outputs
- memory estimator output is reviewed before GPU scheduling claims
- MLflow logs show expected parameters, metrics, and metadata
- distributed training jobs have expected workload status and rank-0 logging
- ITS examples return selected responses and release HTTP resources

Failure signals:

- notebook installs packages from arbitrary indexes without justification
- disconnected mirror does not match the product baseline and runtime
- custom package mix breaks the support posture
- training is promised without GPU/memory review
- model family is outside the supported algorithm matrix
- distributed logging duplicates runs from multiple ranks
- ITS endpoint lacks `/v1` for OpenAI-compatible clients
