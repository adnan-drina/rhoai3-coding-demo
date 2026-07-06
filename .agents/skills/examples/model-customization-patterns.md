# Model Customization Patterns

These examples are review patterns. Verify active workbench images, package
index configuration, GPU capacity, storage, MLflow availability, model
endpoints, and project access before copying anything into GitOps, notebooks,
or runbooks.

## Workflow Decision Record

```text
Use case: <domain-specific task>
Source data: <owned data set or synthetic data source>
Data preparation: Docling conversion | chunking | extraction | subset selection
Synthetic data: none | SDG Hub <example-family>
Training method: SFT | OSFT | LoRA | QLoRA | no weight update
Execution mode: notebook | AI Pipeline | Kubeflow Trainer
Tracking: MLflow enabled | not required
Serving target: KServe/vLLM | external OpenAI-compatible endpoint | deferred
Inference-time scaling: none | Self-Consistency | Best-of-N
```

Review points:

- Keep the business objective separate from the algorithm choice.
- Do not claim fine-tuning when the workflow only uses inference-time scaling.
- Use MLflow when comparing runs or presenting reproducibility evidence.

## Package Source Review

```bash
pip install docling
pip install sdg-hub
pip install training-hub[cuda]
pip install its-hub[lm]
```

Review points:

- Run these from a workbench configured for the Red Hat Python index.
- In disconnected environments, use a mirrored index matching the active
  product baseline and runtime.
- Do not add arbitrary extra indexes unless the README records the support
  exception.

## Example Repository Map

```text
Docling data processing:
  repository: https://github.com/opendatahub-io/data-processing.git
  branch: stable by default; main only with explicit stage decision
  directories:
    notebooks/
    kubeflow-pipelines/common
    kubeflow-pipelines/docling-standard
    kubeflow-pipelines/docling-vlm
    scripts/subset_selection

SDG Hub:
  repository: https://github.com/Red-Hat-AI-Innovation-Team/sdg_hub.git
  branch: main
  directory: examples

Training Hub:
  repository: https://github.com/Red-Hat-AI-Innovation-Team/training_hub.git
  branch: main
  directory: examples

Knowledge Tuning:
  repository: https://github.com/red-hat-data-services/red-hat-ai-examples.git
  branch: main
  directory: knowledge-tuning
```

Review points:

- Treat upstream repositories as source-grounded examples, not active demo
  implementation.
- Adapt examples into this repo only after reviewing package source,
  credentials, data, model choices, and validation.

## Training Hub Algorithm Review

## Docling And KFP Data Preparation Review

```text
Corpus: <RHOAI product documents | other>
Input format: plain text | PDF | HTML | Office document | scanned image | mixed
Docling needed: yes | no
Docling task: convert | chunk | extract | subset-select | RAG preparation
Execution mode: notebook | Kubernetes Job | KFP standard pipeline | KFP VLM pipeline
Runtime image: Red Hat image | reviewed custom image | demo exception
Input source: HTTP/S | S3-compatible object storage
Secret contract: none | data-processing-docling-pipeline
Output target: Files API | Vector Stores API | object storage | training dataset
Validation: converted Markdown exists | chunks inspected | metadata extracted | vector store populated
```

Review points:

- Do not add Docling to already-structured text examples unless it validates a
  real data-preparation need.
- Use the standard KFP pipeline for ordinary documents and the VLM pipeline for
  complex layouts, scanned content, or image descriptors.
- For S3 input, generate the `data-processing-docling-pipeline` Secret from
  local object-storage connection data; do not commit S3 or remote VLM
  credentials.
- Enable chunking only after conversion output is good enough for retrieval.
- Inspect converted output before embedding; bad conversion quality becomes
  bad retrieval quality.
- Keep source documents and converted outputs out of Git unless they are public
  fixtures approved for the demo.

```text
SFT:
  Good fit: supervised fine-tuning with configurable training parameters
  Backend: instructlab.training

OSFT:
  Good fit: preserving prior behavior or continual-learning style needs
  Backend: mini-trainer

LoRA/QLoRA:
  Good fit: parameter-efficient fine-tuning and lower memory use
  Backend: Unsloth
```

Review points:

- Confirm selected model family is supported for the chosen algorithm.
- Use the memory estimator before promising GPU fit.
- Record Liger behavior when `use_liger=True` is involved.

## Training Hub MLflow Handoff

```text
MLFLOW_TRACKING_URI=<tracking-uri>
MLFLOW_EXPERIMENT_NAME=<experiment-name>
MLFLOW_RUN_NAME=<run-name>
```

Review points:

- Use `rhoai-mlflow` for tracking URI, authentication, workspace, and artifact
  storage details.
- In distributed training, only rank 0 should log to avoid duplicate runs.
- Use experiment and run names that can survive a presentation or audit.

## Kubeflow Trainer Handoff

```text
Distributed training needed: yes | no
Training API: Training Hub
Orchestration: Kubeflow Trainer
Queueing: Kueue if enabled for the project
Evidence: logs, checkpoint output, MLflow run, final artifact
```

Review points:

- Use distributed training only when interactive notebook training is not
  enough.
- Route resource details to `rhoai-distributed-workload-workflows`.
- Do not hide queueing, checkpoint, or failure recovery behavior from the
  README or runbook.

## Inference-Time Scaling Review

```text
Endpoint: https://<endpoint>/v1
Model: <model-name>
Algorithm: Self-Consistency | Best-of-N
Budget: <candidate-count>
Expected tradeoff: better answer selection, higher compute per query
```

Review points:

- ITS does not modify model weights.
- Keep provider API keys out of notebooks and committed files.
- Choose budget values intentionally; every extra candidate has cost.
- Close HTTP client resources after use.
