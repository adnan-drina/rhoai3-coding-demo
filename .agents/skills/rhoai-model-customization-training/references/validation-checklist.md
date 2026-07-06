# Validation Checklist

Use this checklist before accepting model customization README content,
notebooks, KFP pipelines, runbooks, GitOps manifests, or demo scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Customize Models for Gen AI and Agentic AI Applications source
  is recorded when model customization behavior is introduced.
- Package source and support posture are tied to the Red Hat Python index and
  supported OpenShift AI base images.
- Workbench lifecycle is checked with `rhoai-project-workflows`.
- JupyterLab and notebook workflows are checked with
  `rhoai-data-science-ide-workflows`.
- AI Pipelines product behavior is checked with `rhoai-ai-pipelines`.
- Repo KFP implementation is checked with `rhoai-kfp-pipeline-authoring`.
- Distributed fine-tuning behavior is checked with
  `rhoai-distributed-workload-workflows`.
- MLflow behavior is checked with `rhoai-mlflow`.
- Serving and OpenAI-compatible endpoint behavior is checked with
  `rhoai-model-serving-platform`.

## Package And Workbench Review

- Workbench image is a Red Hat-provided image or a reviewed custom image.
- Workbench package installation uses the Red Hat Python index unless an
  exception is documented.
- Disconnected package mirror matches the active product version and runtime.
- Package examples install only needed packages:
  - `docling` for data preparation
  - `sdg-hub` for synthetic data generation
  - `training-hub` or `training-hub[cuda]` for fine-tuning
  - `its-hub` or `its-hub[lm]` for inference-time scaling
- Custom package mixing is not presented as Red Hat-supported product
  behavior.

## Data Preparation Review

- Docling is used for supported data preparation patterns such as conversion,
  chunking, extraction, subset selection, or RAG data preparation.
- Input data ownership and sensitivity are documented before processing.
- Generated structured outputs do not expose secrets or regulated data in
  committed artifacts.
- KFP data processing examples use reviewed runtime images with required
  dependencies.
- The `opendatahub-io/data-processing` stable branch is used as the first
  example source when implementing Docling notebooks or Docling KFP pipelines.
- Use of the `main` branch KFP examples is recorded as an explicit stage
  decision when a newer reference implementation is needed.
- Standard versus VLM Docling pipeline choice is documented.
- Standard Docling KFP is used first for ordinary PDFs and text-heavy
  documents; VLM KFP is reserved for complex layouts, scanned/image-heavy
  content, custom page instructions, or remote VLM conversion.
- S3 KFP runs use a generated `data-processing-docling-pipeline` Secret with
  `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`, and
  `S3_PREFIX`.
- Remote VLM KFP runs use a generated `data-processing-docling-pipeline`
  Secret with `REMOTE_MODEL_ENDPOINT_URL`, `REMOTE_MODEL_API_KEY`, and
  `REMOTE_MODEL_NAME`.
- Pipeline output is inspected before it is attached to a vector store,
  training dataset, or evaluation dataset.
- If a Red Hat container image is required by the official example, the image
  source is verified and the pipeline is recompiled after replacement.

## Synthetic Data Review

- SDG Hub examples are clearly labeled as synthetic.
- Synthetic data is separated from real enterprise records.
- Knowledge Tuning, text analysis, RAG evaluation, red teaming, AI safety, or
  agentic examples are mapped to the demo concept before use.
- Generated synthetic data is reviewed for quality, bias, and data leakage
  before use in training or evaluation.

## Training Hub Review

- Algorithm choice is explicit:
  - SFT for supervised full fine-tuning
  - OSFT for preserving prior behavior or continual-learning style needs
  - LoRA/QLoRA for parameter-efficient fine-tuning
- Selected model family appears in the official algorithm/model support matrix.
- Liger kernel caveats are recorded when `use_liger=True` is used.
- Memory estimator output is reviewed for SFT or OSFT sizing.
- LoRA or QLoRA rank choices are documented when memory reduction is the goal.
- GPU capacity, node shape, and storage are verified before live training.
- In-workbench training uses the Training Jupyter PyTorch CUDA Python image or
  another reviewed image.

## MLflow And Distributed Training Review

- MLflow tracking URI is configured through Training Hub API parameters or
  environment variables when experiment evidence is required.
- MLflow experiment and run names are meaningful for comparison.
- Distributed training logs only rank 0 to MLflow.
- Kubeflow Trainer is used only when distributed training is needed.
- Training Operator or Kubeflow Trainer resource details are handed off to
  `rhoai-distributed-workload-workflows`.

## Inference-Time Scaling Review

- ITS is described as inference-time behavior that does not change model
  weights.
- Endpoint is OpenAI-compatible and includes `/v1` where required.
- API key handling avoids committed secrets.
- Python version is 3.11 or later.
- Self-Consistency or Best-of-N budget values are chosen intentionally because
  higher budgets increase compute cost.
- Step-by-step reasoning algorithms are labeled as requiring process reward
  model infrastructure and experimental installation.
- HTTP client resources are closed after use.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get notebooks -A
oc get pods -A | rg -i 'training|pytorch|trainer|kubeflow'
oc get datasciencepipelinesapplications -A
oc get trainjobs -A 2>/dev/null || true
oc get pytorchjobs -A 2>/dev/null || true
```

Workbench package checks:

```bash
python -c "import docling; print('docling ok')"
python -c "import training_hub; print('training hub ok')"
python -c "import its_hub; print('its hub ok')"
```

## Fail Conditions

Stop and correct the work if any of these are true:

- README or presentation claims Red Hat supports arbitrary custom flows built
  from the Python packages.
- Demo notebooks install from arbitrary package indexes without a documented
  exception.
- Disconnected mirror URL or package set does not match the active baseline.
- Training is promised without memory and GPU sizing review.
- Selected model architecture is not in the official support matrix for the
  chosen algorithm.
- Synthetic data is mixed with real data without labeling.
- Sensitive source data or generated outputs are committed.
- MLflow tracking is promised without MLflow availability and workspace access.
- Distributed training logs duplicate metrics from all ranks.
- ITS is presented as model fine-tuning or weight customization.
