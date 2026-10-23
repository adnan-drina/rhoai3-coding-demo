"""Model onboarding qualification as an AI pipeline (KFP v2): evaluate ONE candidate model against fixed gates and
record the evidence on its model registry version.

Run parameters: model_name (an InferenceService in this project), model_version_id (its model registry version),
plus one skip_<evaluation> switch per evaluation (all evaluations run unless a switch is set).

Graph, one straight chain in the style of the garak-kfp pipeline (evalhub-garak-scan): validate -> latency ->
throughput -> livecodebench -> python-tasks -> security -> risk-assessment -> verdict -> report. Every step runs
after the step before it and takes run parameters; only verdict hands report its summary, as garak's steps hand on
their datasets. The evaluation steps publish no artifacts (each job's results stay in EvalHub, MLflow and on the
registry version); verdict judges the run and records it on the registry version, and the last step, report,
publishes html_report and summary_metrics, like garak's write-kfp-outputs. A skipped evaluation step still runs in its place and ends without submitting an
EvalHub job, as garak's own steps do for benchmarks that do not need them.

Each evaluation step follows the EvalHub CI/CD pattern ("Add automated AI evaluations to your CI/CD pipeline"):
eval.yaml, `evalhub health`, `evalhub eval run --config eval.yaml --wait --timeout`. The four capability and
performance steps submit an agentic-coding-* collection; security and risk-assessment submit one garak-kfp benchmark
each (avid_security, intents), because garak-kfp needs the candidate's own URL in its kfp_config, which a collection
cannot carry. Every job uses the candidate model auth Secret garak-kfp-model-auth (api-key and ca_cert for the
evaluation sidecar, plus the pipeline, Kubernetes and helper-model keys garak-kfp needs) and logs to the MLflow
experiment models-onboarding, where the pipeline server also tracks this run and the garak-kfp pipeline runs. Every
job carries the tag run=<pipeline run id>; the verdict step reads exactly those jobs, so a verdict never mixes
results of different runs.

Steps call EvalHub, the Kubernetes API, the pipeline server and the model registry as the pipeline server's
pipeline-runner ServiceAccount (pod token and OpenShift service CA); no credential is a parameter. Compile with
compile.py (Working with AI pipelines, 1.2.2). Keep this file ASCII-only: the pipeline server's default MariaDB
stores the compiled spec in a latin1 column.
"""

import copy

from kfp import dsl, kubernetes

# Pipeline runtime image shipped with RHOAI 3.5 (imagestream redhat-ods-applications/runtime-minimal).
RUNTIME_IMAGE = (
    "registry.redhat.io/rhoai/odh-pipeline-runtime-minimal-cpu-py312-rhel9"
    "@sha256:3756f9891a27c2581201fd6696457c9b98ffefd80c88b900740f76e2bf970429"
)
EVALHUB_CLI = "eval-hub-sdk[cli]==1.0.5"
# The runtime image's default package index carries eval-hub-sdk only up to 0.4.4; the EvalHub CLI the
# article uses (and the rest of this stage pins) is 1.0.5 on PyPI.
PIP_INDEX = ["https://pypi.org/simple"]
# The SDK trusts the OpenShift service CA when it is present at this path.
SERVICE_CA_DIR = "/etc/pki/ca-trust/source/anchors"
SERVICE_CA_CONFIGMAP = "pipeline-tasks-service-ca"

# (step name, skip parameter, collection id or "", garak-kfp benchmark id or "", --timeout seconds), in run order.
EVALUATIONS = [
    ("latency", "skip_latency", "agentic-coding-latency-v1", "", 3600),
    ("throughput", "skip_throughput", "agentic-coding-throughput-v2", "", 3600),
    # Capability runs as two collections one after the other: LiveCodeBench needs every sequence slot of the
    # model, so it runs alone; the report combines both into the weighted capability score.
    ("livecodebench", "skip_livecodebench", "agentic-coding-livecodebench-v2", "", 2 * 3600),
    ("python-tasks", "skip_python_tasks", "agentic-coding-python-tasks-v1", "", 3600),
    # garak-kfp runs the scan as its own pipeline run and the adapter waits up to twice the benchmark timeout.
    ("security", "skip_security", "", "avid_security", 3 * 3600),
    ("risk-assessment", "skip_risk_assessment", "", "intents", 5 * 3600),
]
TENANT_SECRET = "garak-kfp-model-auth"
EXPERIMENT = "models-onboarding"
EVALHUB_URL = "https://evalhub.evalhub.svc.cluster.local:8443"
REGISTRY_URL = "https://demo-registry.rhoai-model-registries.svc:8443/api/model_registry/v1alpha3"
KFP_URL = "https://ds-pipeline-dspa.evaluated-models.svc.cluster.local:8443"
S3_SECRET = "evaluation-models-pipelines-connection"
QUEUE = "lq-cpu-default"
# Risk assessment helper model: the abliterated model in this project generates the attack prompts (SDG), judges the
# responses and drives TAP (attacker and evaluator default to the judge, guide 7.7.4). Translation uses the provider's
# documented default (Helsinki-NLP models from Hugging Face). sdg_max_tokens stays unset: in the 3.5.2 provider it
# rebuilds the SDG block without its model and the step fails ("Model not configured").
RISK_MODEL = "gemma-2-9b-abliterated"
INTENTS_TIMEOUT = 7200
SDG_NUM_SAMPLES = 5
# Gate for the weighted capability score across the code collections (benchmark weights 3:2:1).
CAPABILITY_THRESHOLD = 0.5


@dsl.component(base_image=RUNTIME_IMAGE)
def validate(model_name: str, model_version_id: str, registry_url: str, risk_model: str,
             skip_risk_assessment: bool):
    """Fail before any job when the candidate, its registry version or (unless skipped) the risk assessment model
    is not ready, or the endpoints ConfigMap is missing."""
    import json
    import ssl
    import urllib.error
    import urllib.request

    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    tenant = open(f"{sa}/namespace").read().strip()
    token = open(f"{sa}/token").read().strip()
    kube_ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")
    service_ctx = ssl.create_default_context(cafile="/etc/pki/ca-trust/source/anchors/service-ca.crt")

    def get(url, ctx):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def ready(name):
        isvc = get(f"https://kubernetes.default.svc/apis/serving.kserve.io/v1beta1/namespaces/{tenant}"
                   f"/inferenceservices/{name}", kube_ctx)
        if isvc is None:
            raise RuntimeError(f"no InferenceService {name} in {tenant}; deploy it in the Evaluated Models project")
        status = isvc.get("status") or {}
        if {c["type"]: c["status"] for c in status.get("conditions") or []}.get("Ready") != "True":
            raise RuntimeError(f"InferenceService {name} is not Ready; start it in the Evaluated Models project "
                               f"(Deployments) and run the pipeline again")
        return status.get("url")

    print(f"candidate {model_name}: {ready(model_name)}")
    if not skip_risk_assessment:
        print(f"risk assessment model {risk_model}: {ready(risk_model)}")
    version = get(f"{registry_url}/model_versions/{model_version_id}", service_ctx)
    if version is None or "name" not in version:
        raise RuntimeError(f"model registry version {model_version_id} not found")
    registered = get(f"{registry_url}/registered_models/{version['registeredModelId']}", service_ctx) or {}
    print(f"registry: {registered.get('name')} version {model_version_id} ({version['name']})")
    if get(f"https://kubernetes.default.svc/api/v1/namespaces/{tenant}/configmaps/qualification-endpoints",
           kube_ctx) is None:
        raise RuntimeError("ConfigMap qualification-endpoints is missing (Stage 050 provisioner hook)")


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI], pip_index_urls=PIP_INDEX)
def evaluate(
    model_name: str,
    collection_id: str,
    benchmark_id: str,
    auth_secret: str,
    experiment: str,
    evalhub_url: str,
    queue: str,
    s3_secret: str,
    risk_model: str,
    intents_timeout: int,
    sdg_num_samples: int,
    run_name: str,
    run_id: str,
    timeout_seconds: int,
    skip: bool,
):
    """Run one EvalHub collection, or one garak-kfp benchmark, on the candidate and wait for it."""
    what = collection_id or f"garak-kfp/{benchmark_id}"
    if skip:
        print(f"{what}: skipped by the run's skip parameter; no EvalHub job submitted")
        return
    import json
    import os
    import re
    import ssl
    import subprocess
    import tempfile
    import urllib.request

    import httpx
    import yaml

    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    tenant = open(f"{sa}/namespace").read().strip()
    token = open(f"{sa}/token").read().strip()
    kube_ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")

    def kube(path):
        req = urllib.request.Request(f"https://kubernetes.default.svc{path}", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, context=kube_ctx, timeout=30) as r:
            return json.load(r)

    model_url = kube(f"/apis/serving.kserve.io/v1beta1/namespaces/{tenant}/inferenceservices/{model_name}")[
        "status"]["url"].rstrip("/") + "/v1"
    client = httpx.Client(base_url=evalhub_url, timeout=60, verify="/etc/pki/ca-trust/source/anchors/service-ca.crt",
                          headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant})
    work = tempfile.mkdtemp()
    profile = os.path.join(work, "evalhub.yaml")
    with open(profile, "w") as f:
        yaml.safe_dump({"active_profile": "default",
                        "profiles": {"default": {"base_url": evalhub_url, "tenant": tenant}}}, f)
    env = dict(os.environ, EVALHUB_CONFIG=profile)
    subprocess.run(["evalhub", "health"], env=env, check=True)

    tags = {"run": run_id, "run_name": run_name, "model": model_name, "evaluation": what}
    body = {
        "name": f"{(collection_id or benchmark_id).replace('_', '-')}-{model_name}-{run_name}"[:120],
        "description": f"Onboarding qualification run {run_name}: {model_name} on {what}",
        "tags": ["model-onboarding", f"run={run_id}", f"model={model_name}"],
        "model": {"url": model_url, "name": model_name, "auth": {"secret_ref": auth_secret}},
        "experiment": {"name": experiment, "tags": [{"key": k, "value": v} for k, v in tags.items()]},
        "queue": {"kind": "kueue", "name": queue},
    }
    if collection_id:
        body["collection"] = {"id": collection_id}
    else:
        # The provider catalog's primary metric, direction and threshold, as the dashboard form sends them.
        catalog = client.get("/api/v1/evaluations/providers/garak-kfp").raise_for_status().json()
        bdef = next(b for b in catalog.get("benchmarks") or [] if b.get("id") == benchmark_id)
        parameters = {"kfp_config": {"namespace": tenant, "s3_secret_name": s3_secret, "model_url": model_url}}
        if benchmark_id == "intents":
            risk_url = f"https://{risk_model}-predictor.{tenant}.svc.cluster.local:8443/v1"
            parameters.update({
                "timeout": intents_timeout, "disable_cache": True, "sdg_num_samples": sdg_num_samples,
                "intents_models": {
                    "judge": {"url": risk_url, "name": risk_model},
                    "sdg": {"url": risk_url, "name": f"hosted_vllm/{risk_model}"},
                }})
        body["benchmarks"] = [{"id": benchmark_id, "provider_id": "garak-kfp", "parameters": parameters,
                               "primary_score": bdef["primary_score"], "pass_criteria": bdef["pass_criteria"]}]
    path = os.path.join(work, "eval.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(body, f, sort_keys=False)
    print(open(path).read())

    # --wait blocks until the job is terminal and exits 1 when the job fails (before printing it), so the job id
    # comes from the "Job submitted" line.
    run = subprocess.run(["evalhub", "eval", "run", "--config", path, "--wait", "--timeout", str(timeout_seconds),
                          "--format", "json"], env=env, capture_output=True, text=True)
    print(run.stderr, end="")
    submitted = re.search(r"Job submitted: (\S+)", run.stderr)
    if not submitted:
        raise RuntimeError(f"evalhub eval run submitted no job (exit {run.returncode})")
    job_id = submitted.group(1)
    # The SDK job model (1.0.5) drops the gate results (results.test, benchmarks[].test), so the job is read from
    # the documented jobs endpoint.
    job = client.get(f"/api/v1/evaluations/jobs/{job_id}").raise_for_status().json()
    state = (job.get("status") or {}).get("state")
    for b in (job.get("results") or {}).get("benchmarks") or []:
        t = b.get("test") or {}
        print(f"  {b.get('id')}: {t.get('primary_score_metric')} {t.get('primary_score')} "
              f"(threshold {t.get('threshold')}) {'pass' if t.get('pass') else 'fail'}")
    print(f"{what}: job {job_id} {state} (exit {run.returncode})")
    if state not in ("completed", "failed", "cancelled", "partially_failed"):
        raise RuntimeError(f"job {job_id} did not finish within {timeout_seconds}s (state {state})")


@dsl.component(base_image=RUNTIME_IMAGE)
def verdict(
    model_version_id: str,
    evalhub_url: str,
    registry_url: str,
    kfp_url: str,
    capability_threshold: float,
    evaluations: list,
    run_name: str,
    run_id: str,
) -> str:
    """Judge this run's jobs against their gates (QUALIFIED only when every evaluation ran and passed) and record the
    evidence on the model version: per benchmark evalhub.<benchmark>.* (job, results page, verdict, MLflow run,
    garak-kfp pipeline run) and evalhub.qualification.* (verdict and this pipeline run). References, not copies; the
    version's other properties are kept, as stages/050-model-evaluation/evaluation/record.sh does. Returns the summary
    (verdict, reasons, capability score, one row per benchmark) as JSON for the report step."""
    import datetime
    import json
    import ssl
    import urllib.parse
    import urllib.request

    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    tenant = open(f"{sa}/namespace").read().strip()
    token = open(f"{sa}/token").read().strip()
    kube_ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")
    ctx = ssl.create_default_context(cafile="/etc/pki/ca-trust/source/anchors/service-ca.crt")

    def call(url, method="GET", data=None, tenant_header=False, context=ctx):
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if tenant_header:
            headers["X-Tenant"] = tenant
        req = urllib.request.Request(url, method=method, headers=headers,
                                     data=json.dumps(data).encode() if data is not None else None)
        with urllib.request.urlopen(req, context=context, timeout=60) as r:
            return json.load(r)

    jobs, offset = [], 0
    while True:
        page = call(f"{evalhub_url}/api/v1/evaluations/jobs?" + urllib.parse.urlencode(
            {"tags": f"run={run_id}", "limit": 100, "offset": offset}), tenant_header=True)
        jobs += page.get("items") or []
        offset += 100
        if not page.get("next") or offset >= page.get("total_count", 0):
            break
    by_evaluation = {}
    for job in sorted(jobs, key=lambda j: j["resource"]["created_at"]):
        key = (job.get("collection") or {}).get("id") or "garak-kfp/" + (job.get("benchmarks") or [{}])[0].get("id", "")
        by_evaluation[key] = job

    def benchmark_result(b):
        """(value, pass, note) for one benchmark result of a job."""
        t = b.get("test") or {}
        metrics = b.get("metrics") or {}
        if (b.get("provider_id") or "").startswith("garak") or "attack_success_rate" in metrics:
            # A Garak result always has one <probe>_asr per probe; only the aggregate means the adapter skipped the
            # results download and scored an empty scan.
            if not any(k.endswith("_asr") and k != "attack_success_rate" for k in metrics):
                return None, False, "no per-probe results (empty scan)"
        elif not any(isinstance(v, (int, float)) and v for v in metrics.values()):
            return None, False, "no successful requests"
        return t.get("primary_score"), t.get("pass"), t.get("primary_score_metric") or ""

    rows, reasons, capability = [], [], []
    weights = {"lcb:codegeneration_v6": 3, "inspect/mbpp": 2, "inspect/humaneval": 1}
    for evaluation in evaluations:
        job = by_evaluation.get(evaluation)
        if job is None:
            reasons.append(f"{evaluation}: not run in this pipeline run")
            rows.append([evaluation, "-", None, None, "not run", None])
            continue
        state = (job.get("status") or {}).get("state")
        results = job.get("results") or {}
        if state != "completed":
            reasons.append(f"{evaluation}: job {job['resource']['id']} {state}")
        thresholds = {b.get("id"): (b.get("pass_criteria") or {}).get("threshold") for b in job.get("benchmarks") or []}
        for b in results.get("benchmarks") or []:
            value, passed, note = benchmark_result(b)
            threshold = thresholds.get(b["id"])
            if threshold is None:
                threshold = (b.get("test") or {}).get("threshold")
            rows.append([evaluation, b["id"], value, passed, note, threshold])
            if passed is not True:
                reasons.append(f"{evaluation}/{b['id']}: misses its gate ({note} {value}, threshold {threshold})")
            if b["id"] in weights:
                capability.append((weights[b["id"]], value))
        col_test = results.get("test") or {}
        if job.get("collection") and col_test.get("pass") is False:
            reasons.append(f"{evaluation}: collection score {col_test.get('score')} misses "
                           f"{col_test.get('threshold')}")
    cap = (sum(w * v for w, v in capability) / sum(w for w, _ in capability)
           if len(capability) == len(weights) and all(isinstance(v, (int, float)) for _, v in capability) else None)
    if cap is None:
        reasons.append("no complete capability result (LiveCodeBench, MBPP and HumanEval)")
    elif cap < capability_threshold:
        reasons.append(f"capability score {cap:.3f} misses its gate {capability_threshold}")
    result = "QUALIFIED" if not reasons else "NOT QUALIFIED"
    print(result)
    for r in reasons:
        print(f"  - {r}")

    # Record on the model registry version.
    dashboard_url = call(f"https://kubernetes.default.svc/api/v1/namespaces/{tenant}/configmaps/qualification-endpoints",
                         context=kube_ctx)["data"]["dashboard_url"]
    completed = [j for j in jobs if (j.get("status") or {}).get("state") == "completed"]
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def s(v):
        return {"metadataType": "MetadataStringValue", "string_value": str(v)}

    version = call(f"{registry_url}/model_versions/{model_version_id}")
    benchmark_ids = {b.get("id") for j in completed for b in (j.get("benchmarks") or [])}
    props = {k: v for k, v in (version.get("customProperties") or {}).items()
             if not k.startswith("evalhub.qualification.")
             and not any(k.startswith(f"evalhub.{b}.") for b in benchmark_ids)}
    for job in completed:
        jid = job["resource"]["id"]
        results = {b.get("id"): b for b in (job.get("results") or {}).get("benchmarks") or []}
        garak_run = ""
        if any(b.get("provider_id") == "garak-kfp" for b in job.get("benchmarks") or []):
            flt = json.dumps({"predicates": [{"key": "display_name", "operation": "EQUALS",
                                              "string_value": f"evalhub-garak-{jid}"}]})
            try:
                runs = call(f"{kfp_url}/apis/v2beta1/runs?" + urllib.parse.urlencode(
                    {"namespace": tenant, "page_size": 5, "filter": flt})).get("runs") or []
                garak_run = " ".join(f"{dashboard_url}/develop-train/pipelines/runs/{tenant}/runs/{r['run_id']}"
                                     for r in runs)
            except Exception as e:  # the link is a convenience; the job id and results page remain
                print(f"garak-kfp pipeline run of job {jid} not found: {e}")
        for b in job.get("benchmarks") or []:
            k = f"evalhub.{b['id']}."
            r = results.get(b["id"]) or {}
            t = r.get("test")
            lower = bool((b.get("primary_score") or {}).get("lower_is_better"))
            props[k + "job_id"] = s(jid)
            props[k + "job_name"] = s(job.get("name", ""))
            props[k + "evaluation_url"] = s(f"{dashboard_url}/evaluation/{tenant}/results/{jid}")
            props[k + "provider"] = s(b.get("provider_id", ""))
            props[k + "model_name"] = s((job.get("model") or {}).get("name", ""))
            if t:
                props[k + "result"] = s(f"{t.get('primary_score_metric') or 'score'} {t.get('primary_score')} "
                                        f"(threshold {t.get('threshold')}, {'lower' if lower else 'higher'} is better) "
                                        f"{'pass' if t.get('pass') else 'fail'}")
                props[k + "pass"] = s("true" if t.get("pass") else "false")
            props[k + "mlflow_experiment"] = s((job.get("experiment") or {}).get("name", ""))
            if r.get("mlflow_run_id"):
                props[k + "mlflow_run_id"] = s(r["mlflow_run_id"])
            if garak_run:
                props[k + "pipeline_run_url"] = s(garak_run)
            props[k + "recorded_at"] = s(now)
    props["evalhub.qualification.verdict"] = s(result)
    props["evalhub.qualification.pipeline_run"] = s(run_name)
    props["evalhub.qualification.pipeline_run_url"] = s(
        f"{dashboard_url}/develop-train/pipelines/runs/{tenant}/runs/{run_id}")
    props["evalhub.qualification.recorded_at"] = s(now)
    updated = call(f"{registry_url}/model_versions/{model_version_id}", "PATCH", {"customProperties": props})
    count = len([k for k in updated.get("customProperties") or {} if k.startswith("evalhub.")])
    print(f"recorded {len(completed)} completed jobs and verdict {result} on model version {model_version_id} "
          f"({updated.get('name')}, {count} evalhub properties)")
    return json.dumps({"verdict": result, "reasons": reasons, "capability": cap, "rows": rows})


@dsl.component(base_image=RUNTIME_IMAGE)
def report(
    model_name: str,
    model_version_id: str,
    capability_threshold: float,
    run_name: str,
    summary: str,
    html_report: dsl.Output[dsl.HTML],
    summary_metrics: dsl.Output[dsl.Metrics],
):
    """Publish the run's result like garak's write-kfp-outputs: an HTML report and the summary metrics."""
    import html
    import json

    data = json.loads(summary)
    result, reasons, cap, rows = data["verdict"], data["reasons"], data["capability"], data["rows"]
    for _, bid, value, _, note, _ in rows:
        if isinstance(value, (int, float)):
            summary_metrics.log_metric(f"{bid}.{note}".replace("/", "_").replace(":", "_"), float(value))
    if isinstance(cap, (int, float)):
        summary_metrics.log_metric("capability.weighted", float(cap))
    summary_metrics.log_metric("qualified", 1.0 if result == "QUALIFIED" else 0.0)

    def fmt(v):
        return f"{v:.4g}" if isinstance(v, (int, float)) else "-"

    def css(p):
        return {True: "pass", False: "fail"}.get(p, "na")

    body = "".join(
        f"<tr><td>{html.escape(e)}</td><td>{html.escape(b)}<br><small>{html.escape(n or '')}</small></td>"
        f"<td class={css(p)}>{fmt(v)}</td><td>{fmt(t)}</td></tr>" for e, b, v, p, n, t in rows)
    h = [f"<h1>Model onboarding qualification</h1><p class=note>Run {html.escape(run_name)}: "
         f"<b>{html.escape(model_name)}</b>, model registry version {html.escape(model_version_id)}</p>",
         f"<h2 class={'pass' if result == 'QUALIFIED' else 'fail'}>{result}</h2>",
         "<ul>" + "".join(f"<li>{html.escape(r)}</li>" for r in reasons) + "</ul>" if reasons
         else "<p>Every evaluation ran and passed its gate.</p>",
         f"<h3>Capability (weighted 3:2:1, gate {capability_threshold}): {fmt(cap)}</h3>",
         f"<table><tr><th>Evaluation</th><th>Benchmark</th><th>Score</th><th>Gate</th></tr>{body}</table>",
         "<p class=note>Attack success rates (security, risk assessment) and latency pass at or below their gate; "
         "every other score passes at or above it. Each job is under Develop &amp; train &gt; Evaluations and in the "
         "MLflow experiment models-onboarding; the verdict is also recorded on the model registry version.</p>"]
    style = ("<style>body{font-family:system-ui,sans-serif;margin:24px;color:#151515}table{border-collapse:collapse;"
             "margin:8px 0 20px}th,td{border:1px solid #d2d2d2;padding:6px 10px;text-align:left;vertical-align:top}"
             "th{background:#f0f0f0}td.pass{background:#f3faf2}td.fail{background:#faeaea}small{color:#555}"
             "h2.pass{color:#3e8635}h2.fail{color:#c9190b}.note{color:#555;font-size:.9em}</style>")
    with open(html_report.path, "w") as f:
        f.write(f"<!doctype html><html><head><meta charset=utf-8>{style}</head><body>{''.join(h)}</body></html>")
    print(result)


def _named(component, name):
    # Each step is its own component name rather than one component with display-name overrides: the task
    # key, which the run metadata records as task_name, then equals the step label the dashboard looks up
    # for logs and inputs/outputs.
    named = copy.deepcopy(component)
    named.component_spec.name = name
    return named


def _small(task):
    task.set_caching_options(False)
    task.set_cpu_request("100m").set_memory_request("256Mi").set_cpu_limit("500m").set_memory_limit("512Mi")
    kubernetes.use_config_map_as_volume(task, config_map_name=SERVICE_CA_CONFIGMAP, mount_path=SERVICE_CA_DIR)
    return task


@dsl.pipeline(
    name="agentic-coding-model-qualification",
    description="Evaluates one candidate model on the agentic coding collections and the garak-kfp security and "
                "risk assessments, and records the verdict on its model registry version.",
)
def qualification(
    model_name: str,
    model_version_id: str,
    skip_latency: bool = False,
    skip_throughput: bool = False,
    skip_livecodebench: bool = False,
    skip_python_tasks: bool = False,
    skip_security: bool = False,
    skip_risk_assessment: bool = False,
):
    skips = {"skip_latency": skip_latency, "skip_throughput": skip_throughput, "skip_livecodebench": skip_livecodebench,
             "skip_python_tasks": skip_python_tasks, "skip_security": skip_security,
             "skip_risk_assessment": skip_risk_assessment}
    previous = _small(_named(validate, "validate")(
        model_name=model_name, model_version_id=model_version_id, registry_url=REGISTRY_URL, risk_model=RISK_MODEL,
        skip_risk_assessment=skip_risk_assessment))
    # One straight chain: each step runs after the one before it and takes only run parameters.
    for label, skip_name, collection_id, benchmark_id, timeout in EVALUATIONS:
        previous = _small(_named(evaluate, label)(
            model_name=model_name, collection_id=collection_id, benchmark_id=benchmark_id,
            auth_secret=TENANT_SECRET, experiment=EXPERIMENT, evalhub_url=EVALHUB_URL, queue=QUEUE,
            s3_secret=S3_SECRET, risk_model=RISK_MODEL, intents_timeout=INTENTS_TIMEOUT, sdg_num_samples=SDG_NUM_SAMPLES,
            run_name=dsl.PIPELINE_JOB_NAME_PLACEHOLDER, run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
            timeout_seconds=timeout, skip=skips[skip_name],
        ).after(previous))
    judged = _small(_named(verdict, "verdict")(
        model_version_id=model_version_id, evalhub_url=EVALHUB_URL, registry_url=REGISTRY_URL, kfp_url=KFP_URL,
        capability_threshold=CAPABILITY_THRESHOLD, evaluations=[c or f"garak-kfp/{b}" for _, _, c, b, _ in EVALUATIONS],
        run_name=dsl.PIPELINE_JOB_NAME_PLACEHOLDER, run_id=dsl.PIPELINE_JOB_ID_PLACEHOLDER,
    ).after(previous))
    _small(_named(report, "report")(
        model_name=model_name, model_version_id=model_version_id, capability_threshold=CAPABILITY_THRESHOLD,
        run_name=dsl.PIPELINE_JOB_NAME_PLACEHOLDER, summary=judged.output,
    ))
