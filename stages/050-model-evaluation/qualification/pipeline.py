"""Agentic coding model qualification as an AI pipeline (KFP v2): evaluate ONE model, rank it on the leaderboard.

Run it once with the production model (MaaS) to record the baseline, then once per candidate served in the
evaluated-models project. Run parameters: model_name, plus one skip_<evaluation> switch per evaluation (all
evaluations run unless a switch is set). The model name resolves as follows:
  - an InferenceService of that name in this project is a candidate: URL from its status, model auth Secret
    qualification-model-auth (api-key + ca_cert);
  - any other name is a production model served through MaaS: endpoint from ConfigMap qualification-endpoints,
    model auth Secret evalhub-model-auth-maas.

Graph: resolve model -> latency -> throughput -> LiveCodeBench -> Python tasks -> security quick -> security full
-> leaderboard.
A skipped evaluation step still runs in its place and ends without submitting an EvalHub job: KFP does not let a
step depend on a step inside a dsl.If, so conditions would break the order the performance numbers need.
Each collection step follows the EvalHub CI/CD pattern ("Add automated AI evaluations to your CI/CD
pipeline"): eval.yaml, `evalhub health`, `evalhub eval run --config eval.yaml --wait --timeout`, and the job
results (JSON and CSV) kept as the step artifact. Collections run one after another so the performance
numbers are not skewed by concurrent load. EvalHub stores every job; the leaderboard step reads all jobs tagged
agentic-coding-qualification, keeps the newest result per model and collection, and recommends PROMOTE or
HOLD for a candidate against the production baseline.

Steps call EvalHub and the Kubernetes API as the pipeline server's pipeline-runner ServiceAccount (pod token and
OpenShift service CA); no credential is a parameter. Compile with compile.py (Working with AI pipelines, 1.2.2). Keep this file ASCII-only: the
pipeline server's default MariaDB stores the compiled spec in a latin1 column.
"""

import copy
from typing import NamedTuple

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

# (step name, skip parameter, collection id, --timeout seconds), in run order. The dashboard lays out the run
# graph in alphabetical order of step names, so the numbers keep every next step on the same side (Argo
# rejects task names that begin with a digit, hence the "step-" prefix).
COLLECTIONS = [
    ("step-1-latency", "skip_latency", "agentic-coding-latency-v1", 3600),
    ("step-2-throughput", "skip_throughput", "agentic-coding-throughput-v1", 3600),
    # Capability runs as two collections one after the other: LiveCodeBench needs every sequence slot of the
    # model, so it runs alone; the leaderboard combines both into the weighted capability score.
    ("step-3-livecodebench", "skip_livecodebench", "agentic-coding-capability-livecodebench-v1", 2 * 3600),
    ("step-4-python-tasks", "skip_python_tasks", "agentic-coding-capability-python-v1", 3600),
    ("step-5-security-quick", "skip_security_quick", "agentic-coding-security-quick-v2", 3600),
    ("step-6-security-full", "skip_security_full", "agentic-coding-security-full-v2", 3 * 3600),
]
# Fixed for the demo: the EvalHub tag of every qualification job and the MLflow experiment of those jobs.
# Pipeline runs themselves are tracked in the MLflow experiment chosen in the run form
# (agentic-coding-qualification), so EvalHub's per-job runs use a separate experiment.
QUALIFICATION_TAG = "agentic-coding-qualification"
EVALHUB_EXPERIMENT = "agentic-coding-evaluations"
EVALHUB_URL = "https://evalhub.evalhub.svc.cluster.local:8443"
QUEUE = "lq-cpu-default"
MAX_REGRESSION = 0.05
# Gate for the weighted capability score across the code collections (benchmark weights 3:2:1).
CAPABILITY_THRESHOLD = 0.5


@dsl.component(base_image=RUNTIME_IMAGE)
def resolve_model(model_name: str) -> NamedTuple(
        "Model", [("model_id", str), ("model_url", str), ("auth_secret", str), ("target", str), ("tenant", str)]):
    """Find where the model is served: a candidate InferenceService here, or a production model on MaaS."""
    import json
    import ssl
    import urllib.error
    import urllib.request
    from collections import namedtuple

    sa = "/var/run/secrets/kubernetes.io/serviceaccount"
    tenant = open(f"{sa}/namespace").read().strip()
    token = open(f"{sa}/token").read().strip()
    ctx = ssl.create_default_context(cafile=f"{sa}/ca.crt")

    def get(path):
        req = urllib.request.Request(f"https://kubernetes.default.svc{path}", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    Model = namedtuple("Model", ["model_id", "model_url", "auth_secret", "target", "tenant"])
    isvc = get(f"/apis/serving.kserve.io/v1beta1/namespaces/{tenant}/inferenceservices/{model_name}")
    if isvc is not None:
        ready = {c["type"]: c["status"] for c in (isvc.get("status") or {}).get("conditions") or []}.get("Ready")
        url = (isvc.get("status") or {}).get("url")
        if ready != "True" or not url:
            raise RuntimeError(f"candidate InferenceService {model_name} is not Ready; start it in the "
                               f"Evaluated Models project (Deployments) and run the pipeline again")
        print(f"{model_name}: candidate InferenceService in {tenant}, {url}")
        return Model(model_name, url.rstrip("/") + "/v1", "qualification-model-auth", "candidate", tenant)
    endpoints = get(f"/api/v1/namespaces/{tenant}/configmaps/qualification-endpoints")
    if endpoints is None:
        raise RuntimeError("ConfigMap qualification-endpoints is missing (Stage 050 provisioner hook)")
    model_id = model_name if "/" in model_name else f"publishers/internal-models/models/{model_name}"
    print(f"{model_name}: production model on MaaS as {model_id}")
    return Model(model_id, endpoints["data"]["maas_base_url"], "evalhub-model-auth-maas", "production", tenant)


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI], pip_index_urls=PIP_INDEX)
def evaluate_collection(
    model_name: str,
    model_id: str,
    model_url: str,
    auth_secret: str,
    target: str,
    tenant: str,
    collection_id: str,
    qualification_tag: str,
    evalhub_experiment: str,
    evalhub_url: str,
    queue: str,
    run_name: str,
    timeout_seconds: int,
    skip: bool,
    results: dsl.Output[dsl.Artifact],
    scores: dsl.Output[dsl.Metrics],
) -> NamedTuple(
        "Model", [("model_id", str), ("model_url", str), ("auth_secret", str), ("target", str), ("tenant", str)]):
    """Run one EvalHub collection on the model and keep the job body and results. The model details are
    passed on unchanged, so each step feeds the next and the run graph stays one sequential chain."""
    import json
    from collections import namedtuple
    Model = namedtuple("Model", ["model_id", "model_url", "auth_secret", "target", "tenant"])
    passed_on = Model(model_id, model_url, auth_secret, target, tenant)
    if skip:
        print(f"{collection_id}: skipped by the run's skip parameter; no EvalHub job submitted")
        with open(results.path, "w") as f:
            json.dump({"collection_id": collection_id, "skipped": True}, f)
        scores.log_metric("skipped", 1.0)
        return passed_on
    import os
    import re
    import subprocess
    import tempfile

    import httpx
    import yaml

    work = tempfile.mkdtemp()
    profile = os.path.join(work, "evalhub.yaml")
    with open(profile, "w") as f:
        yaml.safe_dump({"active_profile": "default",
                        "profiles": {"default": {"base_url": evalhub_url, "tenant": tenant}}}, f)
    env = dict(os.environ, EVALHUB_CONFIG=profile)
    subprocess.run(["evalhub", "health"], env=env, check=True)

    version = collection_id.rsplit("-", 1)[-1]
    tags = {"qualification_run": run_name, "model": model_name, "target": target,
            "collection": collection_id, "collection_version": version}
    body = {
        "name": f"{collection_id}-{model_name}-{run_name}"[:120],
        "description": f"Model qualification run {run_name}: {target} model {model_name} on {collection_id}",
        "tags": [qualification_tag, f"target={target}", f"model={model_name}"],
        "model": {"url": model_url, "name": model_id, "auth": {"secret_ref": auth_secret}},
        "collection": {"id": collection_id},
        "experiment": {"name": evalhub_experiment, "tags": [{"key": k, "value": v} for k, v in tags.items()]},
        "queue": {"kind": "kueue", "name": queue},
    }
    path = os.path.join(work, "eval.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(body, f, sort_keys=False)
    print(open(path).read())

    # The gate: --wait blocks until the job is terminal and exits 1 when the job fails (before printing it),
    # so the job id comes from the "Job submitted" line.
    run = subprocess.run(["evalhub", "eval", "run", "--config", path, "--wait", "--timeout", str(timeout_seconds),
                          "--format", "json"], env=env, capture_output=True, text=True)
    print(run.stderr, end="")
    submitted = re.search(r"Job submitted: (\S+)", run.stderr)
    if not submitted:
        raise RuntimeError(f"evalhub eval run submitted no job (exit {run.returncode})")
    job_id = submitted.group(1)

    # The SDK job model (1.0.5) drops the gate results (results.test, benchmarks[].test), so the job is read
    # from the documented jobs endpoint with the same ServiceAccount token and service CA.
    token = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
    response = httpx.get(f"{evalhub_url}/api/v1/evaluations/jobs/{job_id}", timeout=60,
                         headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant},
                         verify="/etc/pki/ca-trust/source/anchors/service-ca.crt")
    response.raise_for_status()
    job = response.json()
    csv = subprocess.run(["evalhub", "eval", "results", job_id, "--format", "csv"],
                         env=env, capture_output=True, text=True).stdout
    with open(results.path, "w") as f:
        json.dump({"eval_yaml": body, "job": job, "results_csv": csv}, f, indent=1)
    state = (job.get("status") or {}).get("state")
    # Scalar metrics: logged by the pipeline server's MLflow integration to this task's nested run and shown
    # in the KFP and MLflow run comparison views. A benchmark whose metrics are all zero had no successful
    # requests, so it gets no score.
    for b in (job.get("results") or {}).get("benchmarks") or []:
        t = b.get("test") or {}
        numbers = [v for v in (b.get("metrics") or {}).values() if isinstance(v, (int, float))]
        if isinstance(t.get("primary_score"), (int, float)) and any(numbers):
            scores.log_metric(f"{b['id']}.{t.get('primary_score_metric')}".replace("/", "_").replace(":", "_"),
                              float(t["primary_score"]))
            scores.log_metric(f"{b['id']}.pass".replace("/", "_").replace(":", "_"), 1.0 if t.get("pass") else 0.0)
    print(f"{collection_id}: job {job_id} {state} (exit {run.returncode})")
    if state not in ("completed", "failed", "cancelled", "partially_failed"):
        raise RuntimeError(f"job {job_id} did not finish within {timeout_seconds}s (state {state})")
    return passed_on


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI], pip_index_urls=PIP_INDEX)
def leaderboard(
    model_name: str,
    target: str,
    tenant: str,
    qualification_tag: str,
    evalhub_url: str,
    max_regression: float,
    capability_threshold: float,
    run_name: str,
    report: dsl.Output[dsl.HTML],
    scores: dsl.Output[dsl.Metrics],
) -> str:
    """Rank every qualified model per benchmark; for a candidate, recommend PROMOTE or HOLD vs production."""
    import html
    import json
    import os
    import subprocess
    import tempfile

    import httpx
    import yaml

    profile = os.path.join(tempfile.mkdtemp(), "evalhub.yaml")
    with open(profile, "w") as f:
        yaml.safe_dump({"active_profile": "default",
                        "profiles": {"default": {"base_url": evalhub_url, "tenant": tenant}}}, f)
    env = dict(os.environ, EVALHUB_CONFIG=profile)
    token = open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
    client = httpx.Client(base_url=evalhub_url, timeout=60, verify="/etc/pki/ca-trust/source/anchors/service-ca.crt",
                          headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant})

    jobs, offset = [], 0
    while True:
        page = client.get("/api/v1/evaluations/jobs",
                          params={"tags": qualification_tag, "limit": 100, "offset": offset}).raise_for_status().json()
        jobs += page.get("items") or []
        offset += 100
        if not page.get("next") or offset >= page.get("total_count", 0):
            break

    def tag(job, key):
        return next((t.split("=", 1)[1] for t in job.get("tags") or [] if t.startswith(key + "=")), None)

    # Newest finished job per (model, collection).
    latest = {}
    for job in sorted(jobs, key=lambda j: j["resource"]["created_at"]):
        if (job.get("status") or {}).get("state") not in ("completed", "partially_failed", "failed"):
            continue
        cid = (job.get("collection") or {}).get("id")
        model = tag(job, "model")
        if cid and model:
            latest[(model, cid)] = job
    targets = {}
    for (model, _), job in latest.items():
        targets[model] = tag(job, "target") or "candidate"
    order = ["latency", "throughput", "livecodebench", "python", "capability", "security-quick", "security-full"]
    collections = sorted({cid for _, cid in latest},
                         key=lambda c: order.index(next((k for k in order if k in c), "capability")))
    models = sorted(targets, key=lambda m: (targets[m] != "production", m != model_name, m))
    production = next((m for m in models if targets[m] == "production"), None)

    def describe(cid):
        out = subprocess.run(["evalhub", "collections", "describe", cid, "--format", "json"],
                             env=env, capture_output=True, text=True, check=True).stdout
        c = json.loads(out)
        return c[0] if isinstance(c, list) else c

    def score(job, bdef):
        """Primary score and pass for one benchmark, or (None, False) when the run produced nothing."""
        if job is None:
            return None, None
        primary = bdef.get("primary_score") or {}
        metric, lower = primary.get("metric", ""), bool(primary.get("lower_is_better"))
        threshold = (bdef.get("pass_criteria") or {}).get("threshold")
        b = {x.get("id"): x for x in (job.get("results") or {}).get("benchmarks") or []}.get(bdef["id"]) or {}
        numbers = [v for v in (b.get("metrics") or {}).values() if isinstance(v, (int, float))]
        if not numbers or not any(numbers):
            return None, False  # no metrics, or all zero: no request succeeded
        t = b.get("test") or {}
        value = t.get("primary_score", (b.get("metrics") or {}).get(metric))
        passed = t.get("pass")
        if passed is None and isinstance(value, (int, float)) and threshold is not None:
            passed = value <= threshold if lower else value >= threshold
        return value, passed

    reasons, sections = [], []
    weighted = {m: [] for m in models}  # (weight, value) of every code benchmark per model
    for cid in collections:
        col = describe(cid)
        rows = []
        for bdef in col.get("benchmarks") or []:
            primary = bdef.get("primary_score") or {}
            metric, lower = primary.get("metric", ""), bool(primary.get("lower_is_better"))
            threshold = (bdef.get("pass_criteria") or {}).get("threshold")
            cells = {m: score(latest.get((m, cid)), bdef) for m in models}
            for m, (v, _) in cells.items():
                if isinstance(v, (int, float)):
                    scores.log_metric(f"{m}.{bdef['id']}.{metric}".replace("/", "_"), float(v))
            rows.append((bdef["id"], metric, lower, threshold, cells))
            if col.get("category") == "code":
                for m, (v, _) in cells.items():
                    weighted[m].append((float(bdef.get("weight") or 1), v))
            if target == "candidate":
                v, p = cells.get(model_name, (None, None))
                if p is not True:
                    reasons.append(f"{cid}/{bdef['id']}: misses its gate ({metric} {v}, threshold {threshold})")
                pv = cells.get(production, (None, None))[0] if production else None
                if isinstance(v, (int, float)) and isinstance(pv, (int, float)) and pv:
                    delta = (v - pv) / abs(pv) * (-1 if lower else 1)
                    if delta < -max_regression:
                        reasons.append(f"{cid}/{bdef['id']}: {abs(delta):.0%} worse than production on {metric}")
        col_threshold = (col.get("pass_criteria") or {}).get("threshold")
        col_scores = {m: ((latest.get((m, cid)) or {}).get("results") or {}).get("test") or {} for m in models}
        if target == "candidate" and col_threshold is not None and col_scores.get(model_name, {}).get("pass") is not True:
            reasons.append(f"{cid}: collection score {col_scores.get(model_name, {}).get('score')} misses {col_threshold}")
        sections.append((col.get("name") or cid, rows, col_threshold, col_scores))

    # Weighted capability score over every code benchmark (LiveCodeBench 3, MBPP 2, HumanEval 1); a model
    # needs a result for each of them to get one.
    capability = {m: (sum(w * v for w, v in pairs) / sum(w for w, _ in pairs)
                      if pairs and all(isinstance(v, (int, float)) for _, v in pairs) else None)
                  for m, pairs in weighted.items()}
    for m, c in capability.items():
        if c is not None:
            scores.log_metric(f"{m}.capability.weighted", float(c))
    if target == "candidate":
        c = capability.get(model_name)
        if c is None:
            reasons.append("no complete capability result (LiveCodeBench, MBPP and HumanEval)")
        elif c < capability_threshold:
            reasons.append(f"capability score {c:.3f} misses its gate {capability_threshold}")
    verdict = "BASELINE RECORDED" if target == "production" else None
    if target == "candidate":
        if production is None:
            reasons.append("no production baseline yet: run this pipeline with the production model first")
        else:
            c, p = capability.get(model_name), capability.get(production)
            if not (isinstance(c, (int, float)) and isinstance(p, (int, float))):
                reasons.append("no capability scores to compare")
            elif c <= p:
                reasons.append(f"capability score {c:.3f} does not beat production {p:.3f}")
        verdict = "PROMOTE" if not reasons else "HOLD"

    def fmt(v):
        return f"{v:.4g}" if isinstance(v, (int, float)) else "-"

    def cell(v, p, best):
        cls = {True: "pass", False: "fail"}.get(p, "na")
        star = " *" if best else ""
        return f"<td class={cls}>{fmt(v)}{star}</td>"

    head = "".join(f"<th>{html.escape(m)}<br><small>{targets[m]}</small></th>" for m in models)
    h = ["<h1>Agentic coding model leaderboard</h1>",
         f"<p class=note>Run {html.escape(run_name)} evaluated <b>{html.escape(model_name)}</b> ({target}).</p>",
         f"<h2 class={'promote' if verdict == 'PROMOTE' else 'hold' if verdict == 'HOLD' else 'base'}>{verdict}</h2>"]
    if target == "candidate":
        h.append("<ul>" + "".join(f"<li>{html.escape(r)}</li>" for r in reasons) + "</ul>" if reasons else
                 f"<p>{html.escape(model_name)} passes every gate, beats production on capability and is not more "
                 f"than {max_regression:.0%} worse on any benchmark.</p>")
    h.append(f"<h3>Capability (weighted 3:2:1, gate {capability_threshold})</h3><table><tr><th>Score</th>{head}</tr>"
             "<tr><td>LiveCodeBench, MBPP, HumanEval</td>"
             + "".join(cell(capability[m], None if capability[m] is None else capability[m] >= capability_threshold,
                            False) for m in models) + "</tr></table>")
    for title, rows, col_threshold, col_scores in sections:
        body = []
        for bid, metric, lower, threshold, cells in rows:
            vals = [v for v, _ in cells.values() if isinstance(v, (int, float))]
            best = (min(vals) if lower else max(vals)) if vals else None
            body.append(f"<tr><td>{html.escape(bid)}<br><small>{html.escape(metric)}, "
                        f"{'lower' if lower else 'higher'} is better, gate {fmt(threshold)}</small></td>"
                        + "".join(cell(cells[m][0], cells[m][1], cells[m][0] == best and len(vals) > 1) for m in models)
                        + "</tr>")
        if col_threshold is not None:
            body.append(f"<tr><td><b>Collection score</b><br><small>weighted, gate {fmt(col_threshold)}</small></td>"
                        + "".join(cell(col_scores[m].get("score"), col_scores[m].get("pass"), False) for m in models)
                        + "</tr>")
        h.append(f"<h3>{html.escape(title)}</h3><table><tr><th>Benchmark</th>{head}</tr>{''.join(body)}</table>")
    h.append("<p class=note>Each cell is the newest qualification result for that model; * marks the best value, "
             "green passes its gate, red fails it. Compare individual runs in the dashboard: Develop &amp; train &gt; "
             "Evaluations, select runs and click Compare (MLflow experiment agentic-coding-evaluations), or compare "
             "pipeline runs in the MLflow experiment agentic-coding-qualification. Production models "
             "are reached through the MaaS gateway and candidates directly, so production latency includes the "
             "gateway hop.</p>")
    style = ("<style>body{font-family:system-ui,sans-serif;margin:24px;color:#151515}table{border-collapse:collapse;"
             "margin:8px 0 20px}th,td{border:1px solid #d2d2d2;padding:6px 10px;text-align:left;vertical-align:top}"
             "th{background:#f0f0f0}td.pass{background:#f3faf2}td.fail{background:#faeaea}small{color:#555}"
             "h2.promote{color:#3e8635}h2.hold{color:#c9190b}h2.base{color:#0066cc}.note{color:#555;font-size:.9em}</style>")
    with open(report.path, "w") as f:
        f.write(f"<!doctype html><html><head><meta charset=utf-8>{style}</head><body>{''.join(h)}</body></html>")
    print(verdict)
    for r in reasons:
        print(f"  - {r}")
    return verdict


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
    description="Evaluates one model on the agentic coding EvalHub collections and ranks it on the "
                "qualification leaderboard.",
)
def qualification(
    model_name: str,
    skip_latency: bool = False,
    skip_throughput: bool = False,
    skip_livecodebench: bool = False,
    skip_python_tasks: bool = False,
    skip_security_quick: bool = False,
    skip_security_full: bool = False,
):
    skips = {"skip_latency": skip_latency, "skip_throughput": skip_throughput, "skip_livecodebench": skip_livecodebench,
             "skip_python_tasks": skip_python_tasks,
             "skip_security_quick": skip_security_quick, "skip_security_full": skip_security_full}
    model = _small(_named(resolve_model, "step-0-resolve-model")(model_name=model_name))
    # Each step takes the model details from the step before it, so the graph is one chain.
    previous = model
    for label, skip_name, collection_id, timeout in COLLECTIONS:
        step = _small(_named(evaluate_collection, label)(
            model_name=model_name, model_id=previous.outputs["model_id"], model_url=previous.outputs["model_url"],
            auth_secret=previous.outputs["auth_secret"], target=previous.outputs["target"],
            tenant=previous.outputs["tenant"],
            collection_id=collection_id, qualification_tag=QUALIFICATION_TAG, evalhub_experiment=EVALHUB_EXPERIMENT,
            evalhub_url=EVALHUB_URL, queue=QUEUE,
            run_name=dsl.PIPELINE_JOB_NAME_PLACEHOLDER, timeout_seconds=timeout, skip=skips[skip_name],
        ))
        previous = step
    board = _small(_named(leaderboard, "step-7-leaderboard")(
        model_name=model_name, target=previous.outputs["target"], tenant=previous.outputs["tenant"],
        qualification_tag=QUALIFICATION_TAG, evalhub_url=EVALHUB_URL, max_regression=MAX_REGRESSION,
        capability_threshold=CAPABILITY_THRESHOLD, run_name=dsl.PIPELINE_JOB_NAME_PLACEHOLDER,
    ))
