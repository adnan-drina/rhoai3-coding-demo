# KFP Advanced Patterns Reference

Informational patterns extracted from previous KFP pipeline guidance. These are
"good to know" patterns for future adoption, not current requirements.

## Component Authoring Styles (3 types)

KFP v2 provides three component authoring approaches:

| Style | Decorator | Use case | Hermeticism | Deps |
|-------|-----------|----------|-------------|------|
| Lightweight Python | `@dsl.component` | Pure Python, quick iteration | Required | `packages_to_install` (runtime) |
| Containerized Python | `@dsl.component(target_image=...)` | Python with complex deps | Not required | Baked into image |
| Container | `@dsl.container_component` | Non-Python, shell scripts, custom binaries | N/A | In the image |

**This project uses Lightweight Python Components.** Dependencies are installed from
the Red Hat Python index on every run, adding 30-60s startup per task. Acceptable for
a demo, but the KFP docs recommend Containerized Components for production.

**Container Components** (`@dsl.container_component`) return a
`dsl.ContainerSpec(image=..., command=[...], args=[...])`. Step-06's GuideLLM benchmark
is a candidate since it already uses a custom image (`GUIDELLM_IMAGE`).

**Reusable components** can be loaded from compiled YAML via
`components.load_component_from_file('component.yaml')` or from a URL.

## KFP 2.15 Decorator Features

Available in KFP 2.15+ (may be useful when RHOAI upgrades):

- **`embedded_artifact_path`** — embed a local file/directory into the component at
  compile time. At runtime, the content is extracted and accessible via
  `dsl.EmbeddedInput[T]`. Useful for bundling config files without PVCs.
- **`task_config_passthroughs`** — pass task-level config (resources, env, volumes)
  through to sub-resources like Kubeflow TrainJobs.

## Local Execution for Development

KFP supports local execution via `local.init(runner=local.DockerRunner())`, then calling
components/pipelines as normal Python functions. Outputs are materialized values, not
futures. Limitations: no ParallelFor, no ExitHandler, no resource limits, no cluster auth.
Useful for testing component logic, not full pipeline topology.

Ref: https://www.kubeflow.org/docs/components/pipelines/user-guides/core-functions/execute-kfp-pipelines-locally/

## RHOAI DSPA Authentication

RHOAI uses DSPA (Data Science Pipelines Application) instead of standard Kubeflow
Pipelines. Authentication differs from upstream:

```python
kfp_client = kfp.Client(
    host=DSPA_URL,           # https://ds-pipeline-dspa-rag-private-ai.apps...
    namespace=NAMESPACE,      # "private-ai"
    existing_token=OC_TOKEN,  # from `oc whoami -t`
)
```

This is NOT the standard `kfp.Client()` with Dex auth or ServiceAccount tokens.
The DSPA route and oc token are resolved in the runner script before the Python heredoc.

Inside pipeline pods, `KF_PIPELINES_SA_TOKEN_PATH` points to the ServiceAccount token
for authenticating with cluster services (e.g., Model Registry). Set it explicitly:
```python
os.environ["KF_PIPELINES_SA_TOKEN_PATH"] = "/var/run/secrets/kubernetes.io/serviceaccount/token"
```
