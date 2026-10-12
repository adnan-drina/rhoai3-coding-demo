"""Agentic coding model qualification: production baseline vs candidate, as an AI pipeline (KFP v2).

Graph: performance -> capability -> security quick -> security full -> leaderboard. Each collection
step evaluates both models side by side and follows the EvalHub CI/CD pattern ("Add automated AI
evaluations to your CI/CD pipeline"): an eval.yaml per model, `evalhub health`, then `evalhub eval run
--config eval.yaml --wait --timeout`, keeping the job results (JSON and CSV) as the step's artifact.
Collections run one after another so the performance numbers are not skewed by concurrent load.

The steps call EvalHub as the pipeline server's pipeline-runner ServiceAccount: the SDK reads the pod's
ServiceAccount token and the OpenShift service CA, so no credential is passed as a parameter. Results
are tracked in one MLflow experiment, where the dashboard's Evaluations > Compare view shows the runs
side by side.

Compile: stages/050-model-evaluation/qualification/compile.sh. Keep the source ASCII-only: the pipeline
server's default MariaDB stores the compiled spec in a latin1 column and rejects other characters.
"""

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
SERVICE_CA_CONFIGMAP = "pipelines-service-ca"

COLLECTIONS = [
    ("performance", "agentic-coding-performance-v1", 2 * 3600),
    ("capability", "agentic-coding-capability-v1", 3 * 3600),
    ("security quick", "agentic-coding-security-quick-v1", 2 * 3600),
    ("security full", "agentic-coding-security-full-v1", 4 * 3600),
]


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI], pip_index_urls=PIP_INDEX)
def evaluate_collection(
    collection_id: str,
    collection_version: str,
    baseline_model_name: str,
    baseline_model_url: str,
    baseline_auth_secret: str,
    candidate_model_name: str,
    candidate_model_url: str,
    candidate_auth_secret: str,
    experiment: str,
    queue: str,
    evalhub_url: str,
    tenant: str,
    qualification_id: str,
    timeout_seconds: int,
    results: dsl.Output[dsl.Artifact],
):
    """Run one EvalHub collection on the baseline and the candidate in parallel and keep both results."""
    import json
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

    models = {"baseline": (baseline_model_name, baseline_model_url, baseline_auth_secret),
              "candidate": (candidate_model_name, candidate_model_url, candidate_auth_secret)}
    bodies, procs = {}, {}
    for role, (name, url, auth) in models.items():
        model = {"url": url, "name": name}
        if auth:
            model["auth"] = {"secret_ref": auth}
        tags = {"qualification_id": qualification_id, "role": role, "model": name,
                "collection": collection_id, "collection_version": collection_version}
        bodies[role] = {
            "name": f"{collection_id}-{role}-{qualification_id}"[:120],
            "description": f"Model qualification {qualification_id}: {role} {name} on {collection_id}",
            "tags": ["model-qualification", role, collection_version],
            "model": model,
            "collection": {"id": collection_id},
            "experiment": {"name": experiment, "tags": [{"key": k, "value": v} for k, v in tags.items()]},
            "queue": {"kind": "kueue", "name": queue},
        }
        path = os.path.join(work, f"eval-{role}.yaml")
        with open(path, "w") as f:
            yaml.safe_dump(bodies[role], f, sort_keys=False)
        # The gate: --wait blocks until the job is terminal and exits 1 when the job fails.
        procs[role] = subprocess.Popen(
            ["evalhub", "eval", "run", "--config", path, "--wait", "--timeout", str(timeout_seconds),
             "--format", "json"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # The CLI exits before printing the job when it fails, so the id comes from "Job submitted", and the
    # job is read from the documented jobs endpoint because the SDK job model (1.0.5) drops the gate
    # results (results.test, benchmarks[].test).
    with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
        token = f.read().strip()
    out, problems = {"collection_id": collection_id, "qualification_id": qualification_id}, []
    for role, proc in procs.items():
        stdout, stderr = proc.communicate()
        print(f"--- {role}\n{stderr}", end="")
        submitted = re.search(r"Job submitted: (\S+)", stderr)
        if not submitted:
            problems.append(f"{role}: no job submitted (exit {proc.returncode})")
            continue
        job_id = submitted.group(1)
        response = httpx.get(f"{evalhub_url}/api/v1/evaluations/jobs/{job_id}", timeout=60,
                             headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant},
                             verify="/etc/pki/ca-trust/source/anchors/service-ca.crt")
        response.raise_for_status()
        job = response.json()
        state = (job.get("status") or {}).get("state")
        if state not in ("completed", "failed", "cancelled", "partially_failed"):
            problems.append(f"{role}: job {job_id} not finished within {timeout_seconds}s (state {state})")
        csv = subprocess.run(["evalhub", "eval", "results", job_id, "--format", "csv"],
                             env=env, capture_output=True, text=True).stdout
        out[role] = {"eval_yaml": bodies[role], "job": job, "results_csv": csv}
        print(f"{role} {models[role][0]}: job {job_id} {state} (exit {proc.returncode})")
    with open(results.path, "w") as f:
        json.dump(out, f, indent=1)
    if problems:
        raise RuntimeError("; ".join(problems))


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI], pip_index_urls=PIP_INDEX)
def leaderboard(
    evalhub_url: str,
    tenant: str,
    qualification_id: str,
    max_regression: float,
    performance: dsl.Input[dsl.Artifact],
    capability: dsl.Input[dsl.Artifact],
    security_quick: dsl.Input[dsl.Artifact],
    security_full: dsl.Input[dsl.Artifact],
    report: dsl.Output[dsl.HTML],
    scores: dsl.Output[dsl.Metrics],
) -> str:
    """Compare baseline and candidate per benchmark and recommend PROMOTE or HOLD."""
    import html
    import json
    import os
    import subprocess
    import tempfile

    import yaml

    profile = os.path.join(tempfile.mkdtemp(), "evalhub.yaml")
    with open(profile, "w") as f:
        yaml.safe_dump({"active_profile": "default",
                        "profiles": {"default": {"base_url": evalhub_url, "tenant": tenant}}}, f)
    env = dict(os.environ, EVALHUB_CONFIG=profile)
    roles = ("baseline", "candidate")

    runs = []
    for art in (performance, capability, security_quick, security_full):
        with open(art.path) as f:
            runs.append(json.load(f))
    names = {r: runs[0][r]["eval_yaml"]["model"]["name"] for r in roles}

    reasons, sections, capability_delta = [], [], None
    for run in runs:
        cid = run["collection_id"]
        col = json.loads(subprocess.run(["evalhub", "collections", "describe", cid, "--format", "json"],
                                        env=env, capture_output=True, text=True, check=True).stdout)
        col = col[0] if isinstance(col, list) else col
        res = {r: run[r]["job"].get("results") or {} for r in roles}
        state = {r: (run[r]["job"].get("status") or {}).get("state") for r in roles}
        by_bench = {r: {b.get("id"): b for b in res[r].get("benchmarks") or []} for r in roles}
        rows = []
        for bdef in col.get("benchmarks") or []:
            bid = bdef["id"]
            primary = bdef.get("primary_score") or {}
            metric, lower = primary.get("metric", ""), bool(primary.get("lower_is_better"))
            threshold = (bdef.get("pass_criteria") or {}).get("threshold")
            vals, passes = {}, {}
            for r in roles:
                b = by_bench[r].get(bid) or {}
                t = b.get("test") or {}
                vals[r] = t.get("primary_score", (b.get("metrics") or {}).get(metric))
                passes[r] = t.get("pass")
                numbers = [v for v in (b.get("metrics") or {}).values() if isinstance(v, (int, float))]
                if numbers and not any(numbers):
                    # Every metric zero means no request succeeded; a lower-is-better gate would pass it.
                    vals[r], passes[r] = None, False
                    reasons.append(f"{cid}/{bid}: {r} produced no successful requests (all metrics 0)")
                if passes[r] is None and isinstance(vals[r], (int, float)) and threshold is not None:
                    passes[r] = vals[r] <= threshold if lower else vals[r] >= threshold
                if isinstance(vals[r], (int, float)):
                    scores.log_metric(f"{r}.{bid}.{metric}".replace("/", "_"), float(vals[r]))
            b, c = vals["baseline"], vals["candidate"]
            delta = None
            if isinstance(b, (int, float)) and isinstance(c, (int, float)) and b:
                delta = (c - b) / abs(b) * (-1 if lower else 1)  # positive = candidate better
            if passes["candidate"] is not True:
                reasons.append(f"{cid}/{bid}: candidate misses its gate ({metric} {c}, threshold {threshold})")
            if delta is not None and delta < -max_regression:
                reasons.append(f"{cid}/{bid}: candidate is {abs(delta):.0%} worse than production on {metric}")
            rows.append((bid, metric, "lower" if lower else "higher", threshold, b, passes["baseline"],
                         c, passes["candidate"], delta))
        col_test = {r: res[r].get("test") or {} for r in roles}
        col_threshold = (col.get("pass_criteria") or {}).get("threshold")
        if col_threshold is not None:
            if col_test["candidate"].get("pass") is not True:
                reasons.append(f"{cid}: candidate collection score {col_test['candidate'].get('score')} "
                               f"misses {col_threshold}")
            cb, cc = col_test["baseline"].get("score"), col_test["candidate"].get("score")
            if col.get("category") == "code" and isinstance(cb, (int, float)) and isinstance(cc, (int, float)):
                capability_delta = cc - cb
        for r in roles:
            if state[r] != "completed":
                reasons.append(f"{cid}: {r} job ended {state[r]}")
        sections.append((col.get("name") or cid, rows, col_test, col_threshold))

    if capability_delta is None:
        reasons.append("no capability collection score to compare")
    elif capability_delta <= 0:
        reasons.append(f"candidate does not improve the capability score ({capability_delta:+.3f})")
    verdict = "PROMOTE" if not reasons else "HOLD"

    def fmt(v):
        return f"{v:.4g}" if isinstance(v, (int, float)) else ("-" if v is None else str(v))

    def cell(v, p):
        mark = {True: "pass", False: "fail"}.get(p, "n/a")
        return f"<td class={mark}>{fmt(v)} <small>{mark}</small></td>"

    h = [f"<h1>Model qualification</h1><p class=note>{html.escape(qualification_id)}</p>",
         f"<p><b>Production (baseline):</b> {html.escape(names['baseline'])}<br>"
         f"<b>Candidate:</b> {html.escape(names['candidate'])}</p>",
         f"<h2 class={verdict.lower()}>Recommendation: {verdict}</h2>"]
    if reasons:
        h.append("<ul>" + "".join(f"<li>{html.escape(r)}</li>" for r in reasons) + "</ul>")
    else:
        h.append("<p>The candidate passes every gate, improves the capability score and is not more than "
                 f"{max_regression:.0%} worse than production on any benchmark.</p>")
    head = ("<tr><th>Benchmark</th><th>Metric</th><th>Better</th><th>Threshold</th><th>Production</th>"
            "<th>Candidate</th><th>Candidate vs production</th></tr>")
    for title, rows, col_test, col_threshold in sections:
        body = []
        for bid, metric, better, thr, b, bp, c, cp, delta in rows:
            d = "-" if delta is None else f"{delta:+.1%}"
            body.append(f"<tr><td>{html.escape(bid)}</td><td>{html.escape(metric)}</td><td>{better}</td>"
                        f"<td>{fmt(thr)}</td>{cell(b, bp)}{cell(c, cp)}<td>{d}</td></tr>")
        if col_threshold is not None:
            body.append(f"<tr><td colspan=3><b>Collection score (weighted)</b></td><td>{fmt(col_threshold)}</td>"
                        f"{cell(col_test['baseline'].get('score'), col_test['baseline'].get('pass'))}"
                        f"{cell(col_test['candidate'].get('score'), col_test['candidate'].get('pass'))}<td></td></tr>")
        h.append(f"<h3>{html.escape(title)}</h3><table>{head}{''.join(body)}</table>")
    h.append("<p class=note>Compare the individual runs in the dashboard: Develop &amp; train &gt; Evaluations, "
             "select the runs of this qualification and click Compare (MLflow experiment "
             "agentic-coding-qualification, tag qualification_id). Production is reached through the MaaS "
             "gateway and the candidate directly, so production latency includes the gateway hop.</p>")
    style = ("<style>body{font-family:system-ui,sans-serif;margin:24px;color:#151515}table{border-collapse:collapse;"
             "margin:8px 0 20px}th,td{border:1px solid #d2d2d2;padding:6px 10px;text-align:left}th{background:#f0f0f0}"
             "td.pass small{color:#3e8635}td.fail small{color:#c9190b}h2.promote{color:#3e8635}"
             "h2.hold{color:#c9190b}.note{color:#555;font-size:.9em}</style>")
    with open(report.path, "w") as f:
        f.write(f"<!doctype html><html><head><meta charset=utf-8>{style}</head><body>{''.join(h)}</body></html>")
    print(f"Recommendation: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    return verdict


def _small(task):
    task.set_caching_options(False)
    task.set_cpu_request("100m").set_memory_request("256Mi").set_cpu_limit("500m").set_memory_limit("512Mi")
    kubernetes.use_config_map_as_volume(task, config_map_name=SERVICE_CA_CONFIGMAP, mount_path=SERVICE_CA_DIR)
    return task


@dsl.pipeline(
    name="agentic-coding-model-qualification",
    description="Runs the agentic coding EvalHub collections on the production model and a candidate, "
                "then publishes a leaderboard and a promote/hold recommendation.",
)
def qualification(
    baseline_model_name: str = "publishers/internal-models/models/qwen3-6-27b",
    baseline_model_url: str = "https://maas.apps.ocp.h275t.sandbox1768.opentlc.com/v1",
    baseline_auth_secret: str = "evalhub-model-auth-maas",
    candidate_model_name: str = "qwen3-8-27b-int4",
    candidate_model_url: str = "https://qwen3-8-27b-int4-predictor.evaluated-models.svc.cluster.local:8443/v1",
    candidate_auth_secret: str = "qualification-model-ca",
    collection_version: str = "v1",
    experiment: str = "agentic-coding-qualification",
    queue: str = "lq-cpu-default",
    evalhub_url: str = "https://evalhub.evalhub.svc.cluster.local:8443",
    tenant: str = "evaluated-models",
    max_regression: float = 0.05,
):
    results, previous = {}, None
    for label, collection_id, timeout in COLLECTIONS:
        task = _small(evaluate_collection(
            collection_id=collection_id, collection_version=collection_version,
            baseline_model_name=baseline_model_name, baseline_model_url=baseline_model_url,
            baseline_auth_secret=baseline_auth_secret,
            candidate_model_name=candidate_model_name, candidate_model_url=candidate_model_url,
            candidate_auth_secret=candidate_auth_secret,
            experiment=experiment, queue=queue, evalhub_url=evalhub_url, tenant=tenant,
            qualification_id=dsl.PIPELINE_JOB_NAME_PLACEHOLDER, timeout_seconds=timeout,
        ))
        task.set_display_name(label)
        if previous is not None:
            task.after(previous)
        results[label] = task.outputs["results"]
        previous = task

    _small(leaderboard(
        evalhub_url=evalhub_url, tenant=tenant, qualification_id=dsl.PIPELINE_JOB_NAME_PLACEHOLDER,
        max_regression=max_regression,
        performance=results["performance"], capability=results["capability"],
        security_quick=results["security quick"], security_full=results["security full"],
    )).set_display_name("leaderboard")
