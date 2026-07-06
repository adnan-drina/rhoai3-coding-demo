# Validation Checklist

Use this checklist before accepting AI Pipelines documentation, manifests,
notebooks, KFP code, runbooks, or demo examples.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The Working with AI pipelines guide is recorded when AI Pipelines behavior is
  introduced.
- Repo-specific KFP code authoring is delegated to
  `rhoai-kfp-pipeline-authoring`.
- Project, workbench, connection, and cluster storage lifecycle is delegated to
  `rhoai-project-workflows`.
- Non-pipeline IDE workflow is delegated to
  `rhoai-data-science-ide-workflows`.
- S3-compatible notebook data operations are delegated to
  `rhoai-s3-object-storage-data`.
- DSCI trusted CA bundle changes are delegated to
  `rhoai-certificate-management`.

## Pipeline Server Review

- A project exists before pipeline server configuration is described.
- S3-compatible object storage endpoint, access key, secret key, region, and
  bucket are treated as secrets or project-owned configuration.
- Incorrect object storage settings are documented as requiring pipeline server
  recreation.
- The default on-cluster database is labeled development/test only.
- Production-positioned pipeline workloads use external MySQL or MariaDB in
  the design.
- External database minimum and recommended versions match the official docs.
- MySQL 8.4 or later includes a plan for `mysql_native_password`.
- Pipeline definition storage mode is explicit: Kubernetes API storage or
  internal database storage.
- GitOps claims use Kubernetes API storage or active schema verification.

## Definition And GitOps Review

- KFP compilation prerequisites include Python 3.11 or later and `kfp` 2.14.3
  or later unless the active docs change.
- Normal compilation output is checked for `pipelineSpec`.
- Kubernetes-native manifest output is used only with Kubernetes API storage.
- `Pipeline` and `PipelineVersion` API version and kind match official docs or
  active CRD schema.
- `PipelineVersion.spec.pipelineSpec` is present.
- FIPS-mode custom pipeline images are based on UBI 9 or RHEL 9.
- Migration from database to Kubernetes API storage is treated as exceptional
  and unsupported by Red Hat.
- If a pipeline is assembled from reusable components, source catalogs are
  recorded and product lifecycle validation stays in OpenShift AI Pipelines.

## Reusable Component Pipeline Review

- Existing component catalogs were searched before custom code was introduced:
  `kubeflow/pipelines-components` for generic components and
  `red-hat-data-services/pipelines-components` for OpenShift AI-aligned
  components.
- Selected component stability is recorded: `alpha`, `beta`, `stable`, or
  local demo-only.
- Component README, metadata, inputs, outputs, limitations, base image posture,
  and last verification status were reviewed before adoption.
- A single-component or minimal two-step run was validated before the full
  workflow.
- Small fixture or sampled data was used before scaling to full data, long
  training, or GPU-backed workloads.
- Run evidence is visible in OpenShift AI: graph, parameters, artifacts,
  metrics where applicable, task logs, and experiment grouping.
- Parallel or conditional pipeline behavior is visible and intentional, not
  hidden inside a monolithic component.
- Component image and dependency posture is reviewed through
  `rhoai-kfp-pipeline-authoring`; this product skill verifies runtime behavior.

## SDK And Token Review

- KFP SDK authentication uses an OpenShift token from the current user or a
  secure prompt.
- Tokens are not passed as literal command arguments or committed to scripts.
- `API_URL`, `NAMESPACE`, and token handling are environment-variable based.
- Custom/self-signed certificates are handled through a trusted certificate
  bundle, not by silently disabling validation in product guidance.
- Client verification lists experiments or pipelines successfully.

## Lifecycle Review

- Imported pipelines identify whether the source is a local file or URL.
- Pipeline versions are used for iterative changes instead of overwriting
  history.
- Archive and delete actions are distinguished clearly.
- Deleting pipeline servers, pipelines, versions, archived experiments, or
  archived runs requires explicit confirmation and post-delete verification.
- Pipeline server deletion is treated as destructive.

## Caching Review

- Caching behavior is intentional and documented for the pipeline.
- Task-level, submit-time, compile-time, and server-level cache settings are
  not conflated.
- Server-level cache settings are reviewed as DSPA or dashboard pipeline server
  configuration.
- Disabling caching includes compute and runtime impact notes.
- Cached task UI markers are verified where caching is expected.
- Cached tasks are not expected to have fresh execution logs.

## Experiment And Run Review

- Experiments group logically related runs.
- Run names, descriptions, pipeline versions, and parameters are clear enough
  for later comparison.
- Comparison claims stay within documented capabilities, including up to 10
  runs at a time.
- Scheduled runs document trigger type, concurrency limit, start/end behavior,
  and catch-up behavior.
- Red Hat's catch-up recommendation is considered when the pipeline handles
  backfill itself.

## Workspace And Artifact Review

- Workspace support is enabled in DSPA before workspace-dependent pipeline code
  is documented.
- Pipeline code enables workspace support with `dsl.PipelineConfig`.
- Workspace size, access mode, storage class, and PVC request values are
  verified against the active cluster.
- `dsl.WORKSPACE_PATH_PLACEHOLDER` is used rather than hard-coded workspace
  paths.
- External artifacts imported with `dsl.importer` are copied into the
  workspace in a separate step when subsequent tasks need workspace access.
- Mutable artifact examples are replaced with verified demo artifacts before
  committing.

## Logs And Elyra Review

- Pipeline run details show graph, execution details, parameters, logs, and
  output where expected.
- Downloaded logs include current or all task logs intentionally.
- Elyra workflows use a supported JupyterLab workbench image.
- code-server, RStudio, Minimal Python, and CUDA-based workbenches are not used
  for Elyra workflows.
- Runtime configuration exists before running or exporting Elyra pipelines.

## DSPA Troubleshooting Review

- DSPA `Ready` conditions are inspected before guessing root cause.
- Object storage TLS, reachability, and credential errors are separated.
- Database timeout, TLS trust, and blocked-host errors are separated.
- Project names for pipeline-server projects are kept under the official
  route-length guidance.
- Missing service account errors are allowed to settle during startup before
  recreation is recommended.
- CrashLoopBackOff and pod-level failures include pod log collection.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencepipelinesapplications.opendatahub.io -n <project-name>
oc get dspa -n <project-name>
oc get pipeline,pipelineversion -n <project-name>
oc get routes -n <project-name>
oc get pods -n <project-name>
oc get events -n <project-name> --sort-by=.lastTimestamp
```

Local or workbench checks:

```bash
python --version
python -m pip show kfp
kfp dsl compile --py <pipeline_file>.py --output <compiled_pipeline_file>.yaml
head -n 10 <compiled_pipeline_file>.yaml
```

## Fail Conditions

Stop and correct the work if any of these are true:

- Secret keys, database passwords, object storage credentials, or OpenShift
  tokens appear in committed files.
- Internal database storage is presented as production recommended.
- GitOps pipeline definitions are claimed while the server stores definitions
  only in the internal database.
- Unsupported migration tooling is presented as Red Hat-supported.
- Server-level caching is changed without noting override behavior.
- Elyra is documented for code-server, RStudio, Minimal Python, or CUDA-based
  workbenches.
- DSPA field names are guessed without official docs or CRD verification.
