"""Agentic coding model qualification: production baseline vs candidate, as an AI pipeline (KFP v2).

Each evaluation step follows the EvalHub CI/CD pattern ("Add automated AI evaluations to your CI/CD
pipeline"): write the job body to eval.yaml, `evalhub health`, then `evalhub eval run --config eval.yaml
--wait --timeout`, and keep the job's JSON and CSV results as artifacts. The pipeline runs the same
versioned collections on both models, one collection at a time so the performance numbers are not
skewed by concurrent load, and ends with a leaderboard and a promote/hold recommendation.

The steps call EvalHub as the pipeline server's pipeline-runner ServiceAccount: the SDK reads the pod's
ServiceAccount token and the OpenShift service CA, so no credential is passed as a parameter. Results
are tracked in one MLflow experiment, where the dashboard's Evaluations > Compare view shows the runs
side by side.

Compile: stages/050-model-evaluation/qualification/compile.sh
"""

from typing import NamedTuple

from kfp import dsl, kubernetes

# Pipeline runtime image shipped with RHOAI 3.5 (imagestream redhat-ods-applications/runtime-minimal).
RUNTIME_IMAGE = (
    "registry.redhat.io/rhoai/odh-pipeline-runtime-minimal-cpu-py312-rhel9"
    "@sha256:3756f9891a27c2581201fd6696457c9b98ffefd80c88b900740f76e2bf970429"
)
EVALHUB_CLI = "eval-hub-sdk[cli]==1.0.5"
# The SDK trusts the OpenShift service CA when it is present at this path.
SERVICE_CA_DIR = "/etc/pki/ca-trust/source/anchors"
SERVICE_CA_CONFIGMAP = "pipelines-service-ca"

COLLECTIONS = [
    "agentic-coding-performance-v1",
    "agentic-coding-capability-v1",
    "agentic-coding-security-quick-v1",
    "agentic-coding-security-full-v1",
]


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI])
def run_collection(
    role: str,
    model_name: str,
    model_url: str,
    model_auth_secret: str,
    collection_id: str,
    collection_version: str,
    experiment: str,
    queue: str,
    evalhub_url: str,
    tenant: str,
    qualification_id: str,
    timeout_seconds: int,
    eval_config: dsl.Output[dsl.Artifact],
    results_json: dsl.Output[dsl.Artifact],
    results_csv: dsl.Output[dsl.Artifact],
) -> NamedTuple("Outputs", [("job_id", str), ("state", str)]):
    """Run one EvalHub collection on one model and keep the job body and results."""
    import json
    import os
    import re
    import subprocess
    import tempfile
    from collections import namedtuple

    import yaml

    profile = os.path.join(tempfile.mkdtemp(), "evalhub.yaml")
    with open(profile, "w") as f:
        yaml.safe_dump({"active_profile": "default",
                        "profiles": {"default": {"base_url": evalhub_url, "tenant": tenant}}}, f)
    env = dict(os.environ, EVALHUB_CONFIG=profile)

    def evalhub(*args, check=True):
        result = subprocess.run(["evalhub", *args], env=env, capture_output=True, text=True)
        print(result.stderr, end="")
        if check and result.returncode != 0:
            raise RuntimeError(f"evalhub {args[0]} {args[1] if len(args) > 1 else ''} exited {result.returncode}")
        return result

    evalhub("health")

    model = {"url": model_url, "name": model_name}
    if model_auth_secret:
        model["auth"] = {"secret_ref": model_auth_secret}
    tags = {"qualification_id": qualification_id, "role": role, "model": model_name,
            "collection": collection_id, "collection_version": collection_version}
    body = {
        "name": f"{collection_id}-{role}-{qualification_id}"[:120],
        "description": f"Model qualification {qualification_id}: {role} {model_name} on {collection_id}",
        "tags": ["model-qualification", role, collection_version],
        "model": model,
        "collection": {"id": collection_id},
        "experiment": {"name": experiment, "tags": [{"key": k, "value": v} for k, v in tags.items()]},
        "queue": {"kind": "kueue", "name": queue},
    }
    with open(eval_config.path, "w") as f:
        yaml.safe_dump(body, f, sort_keys=False)

    # The gate: --wait blocks until the job is terminal and exits 1 when the job fails (before printing
    # the job), so the job id comes from the "Job submitted" line and the job itself from eval status.
    run = evalhub("eval", "run", "--config", eval_config.path, "--wait",
                  "--timeout", str(timeout_seconds), "--format", "json", check=False)
    submitted = re.search(r"Job submitted: (\S+)", run.stderr)
    if not submitted:
        raise RuntimeError(f"evalhub eval run submitted no job (exit {run.returncode})")
    job_id = submitted.group(1)
    print(f"{role} {model_name} {collection_id}: job {job_id}, exit {run.returncode}")

    # The SDK job model (1.0.5) drops the gate results (results.test and benchmarks[].test), so the job
    # is read from the documented REST endpoint with the same ServiceAccount token and service CA.
    import httpx
    with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
        token = f.read().strip()
    response = httpx.get(f"{evalhub_url}/api/v1/evaluations/jobs/{job_id}", timeout=60,
                         headers={"Authorization": f"Bearer {token}", "X-Tenant": tenant},
                         verify="/etc/pki/ca-trust/source/anchors/service-ca.crt")
    response.raise_for_status()
    full = response.json()
    with open(results_json.path, "w") as f:
        json.dump({"role": role, "collection_id": collection_id, "job": full}, f, indent=1)
    with open(results_csv.path, "w") as f:
        f.write(evalhub("eval", "results", job_id, "--format", "csv", check=False).stdout)
    state = ((full.get("status") or {}).get("state")) or "unknown"
    if state not in ("completed", "failed", "cancelled", "partially_failed"):
        raise RuntimeError(f"job {job_id} did not finish within {timeout_seconds}s (state {state}, exit {run.returncode})")
    return namedtuple("Outputs", ["job_id", "state"])(job_id, state)


@dsl.component(base_image=RUNTIME_IMAGE, packages_to_install=[EVALHUB_CLI])
def leaderboard(
    evalhub_url: str,
    tenant: str,
    qualification_id: str,
    baseline_model: str,
    candidate_model: str,
    max_regression: float,
    r1: dsl.Input[dsl.Artifact], r2: dsl.Input[dsl.Artifact], r3: dsl.Input[dsl.Artifact],
    r4: dsl.Input[dsl.Artifact], r5: dsl.Input[dsl.Artifact], r6: dsl.Input[dsl.Artifact],
    r7: dsl.Input[dsl.Artifact], r8: dsl.Input[dsl.Artifact],
    report: dsl.Output[dsl.HTML],
    summary: dsl.Output[dsl.Markdown],
    scores: dsl.Output[dsl.Metrics],
    decision: dsl.Output[dsl.Artifact],
) -> str:
    """Compare baseline and candidate per benchmark and recommend promote or hold."""
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

    runs = {}
    for art in (r1, r2, r3, r4, r5, r6, r7, r8):
        with open(art.path) as f:
            d = json.load(f)
        runs[(d["collection_id"], d["role"])] = d["job"]
    collections = list(dict.fromkeys(c for c, _ in runs))

    def describe(cid):
        out = subprocess.run(["evalhub", "collections", "describe", cid, "--format", "json"],
                             env=env, capture_output=True, text=True, check=True).stdout
        return json.loads(out)

    reasons, rows_md, sections = [], [], []
    capability_delta = None
    for cid in collections:
        col = describe(cid)
        bench_defs = {b["id"]: b for b in col.get("benchmarks") or []}
        res = {role: (runs[(cid, role)].get("results") or {}) for role in ("baseline", "candidate")}
        state = {role: (runs[(cid, role)].get("status") or {}).get("state") for role in ("baseline", "candidate")}
        by_bench = {role: {b.get("id"): b for b in res[role].get("benchmarks") or []} for role in res}
        rows = []
        for bid, bdef in bench_defs.items():
            primary = bdef.get("primary_score") or {}
            metric, lower = primary.get("metric", ""), bool(primary.get("lower_is_better"))
            threshold = (bdef.get("pass_criteria") or {}).get("threshold")
            vals, passes = {}, {}
            for role in ("baseline", "candidate"):
                b = by_bench[role].get(bid) or {}
                t = b.get("test") or {}
                vals[role] = t.get("primary_score", (b.get("metrics") or {}).get(metric))
                passes[role] = t.get("pass")
                if passes[role] is None and isinstance(vals[role], (int, float)) and threshold is not None:
                    passes[role] = vals[role] <= threshold if lower else vals[role] >= threshold
            b, c = vals["baseline"], vals["candidate"]
            delta = None
            if isinstance(b, (int, float)) and isinstance(c, (int, float)) and b:
                delta = (c - b) / abs(b) * (-1 if lower else 1)  # positive = candidate better
            if passes["candidate"] is not True:
                reasons.append(f"{cid}/{bid}: candidate does not pass its gate ({metric} {c} vs threshold {threshold})")
            if delta is not None and delta < -max_regression:
                reasons.append(f"{cid}/{bid}: candidate regresses {abs(delta):.0%} on {metric}")
            if isinstance(c, (int, float)):
                scores.log_metric(f"candidate.{bid}.{metric}".replace("/", "_"), float(c))
            if isinstance(b, (int, float)):
                scores.log_metric(f"baseline.{bid}.{metric}".replace("/", "_"), float(b))
            rows.append((bid, bdef.get("weight", 1), metric, "lower" if lower else "higher", threshold,
                         b, passes["baseline"], c, passes["candidate"], delta))
        col_test = {role: (res[role].get("test") or {}) for role in res}
        col_threshold = (col.get("pass_criteria") or {}).get("threshold")
        if col_threshold is not None:
            if col_test["candidate"].get("pass") is not True:
                reasons.append(f"{cid}: candidate collection score {col_test['candidate'].get('score')} misses {col_threshold}")
            cb, cc = col_test["baseline"].get("score"), col_test["candidate"].get("score")
            if col.get("category") == "code" and isinstance(cb, (int, float)) and isinstance(cc, (int, float)):
                capability_delta = cc - cb
        for role in ("baseline", "candidate"):
            if state[role] != "completed":
                reasons.append(f"{cid}: {role} job ended {state[role]}")
        sections.append((cid, col, rows, col_test, col_threshold, state))

    if capability_delta is None:
        reasons.append("no capability score comparison available")
    elif capability_delta <= 0:
        reasons.append(f"candidate does not improve the capability score ({capability_delta:+.3f})")
    verdict = "PROMOTE" if not reasons else "HOLD"

    def fmt(v):
        return f"{v:.4g}" if isinstance(v, (int, float)) else ("—" if v is None else str(v))

    def badge(p):
        return {True: "pass", False: "fail"}.get(p, "n/a")

    h = [f"<h1>Model qualification {html.escape(qualification_id)}</h1>",
         f"<p><b>Baseline (production):</b> {html.escape(baseline_model)}<br>"
         f"<b>Candidate:</b> {html.escape(candidate_model)}</p>",
         f"<h2>Recommendation: {verdict}</h2>"]
    md = [f"# Model qualification {qualification_id}", "",
          f"Baseline (production): `{baseline_model}`  ", f"Candidate: `{candidate_model}`", "",
          f"## Recommendation: {verdict}", ""]
    if reasons:
        h.append("<ul>" + "".join(f"<li>{html.escape(r)}</li>" for r in reasons) + "</ul>")
        md += [f"- {r}" for r in reasons] + [""]
    else:
        h.append("<p>The candidate passes every gate, improves the capability score and does not regress "
                 f"more than {max_regression:.0%} on any benchmark.</p>")
    head = ("<tr><th>Benchmark</th><th>Weight</th><th>Metric</th><th>Better</th><th>Threshold</th>"
            "<th>Baseline</th><th>Candidate</th><th>Candidate vs baseline</th></tr>")
    for cid, col, rows, col_test, col_threshold, state in sections:
        h.append(f"<h3>{html.escape(col.get('name') or cid)}</h3>")
        md += [f"### {col.get('name') or cid}", "",
               "| Benchmark | Metric | Better | Threshold | Baseline | Candidate | Δ (candidate better > 0) |",
               "|---|---|---|---|---|---|---|"]
        body = []
        for bid, w, metric, better, thr, b, bp, c, cp, delta in rows:
            d = "—" if delta is None else f"{delta:+.1%}"
            body.append(f"<tr><td>{html.escape(bid)}</td><td>{w}</td><td>{html.escape(metric)}</td><td>{better}</td>"
                        f"<td>{fmt(thr)}</td><td>{fmt(b)} ({badge(bp)})</td><td>{fmt(c)} ({badge(cp)})</td>"
                        f"<td>{d}</td></tr>")
            md.append(f"| {bid} | {metric} | {better} | {fmt(thr)} | {fmt(b)} ({badge(bp)}) | {fmt(c)} ({badge(cp)}) | {d} |")
        if col_threshold is not None:
            body.append(f"<tr><td colspan=4><b>Collection score (weighted)</b></td><td>{fmt(col_threshold)}</td>"
                        f"<td>{fmt(col_test['baseline'].get('score'))} ({badge(col_test['baseline'].get('pass'))})</td>"
                        f"<td>{fmt(col_test['candidate'].get('score'))} ({badge(col_test['candidate'].get('pass'))})</td>"
                        "<td></td></tr>")
            md.append(f"| **collection score** | weighted | higher | {fmt(col_threshold)} | "
                      f"{fmt(col_test['baseline'].get('score'))} | {fmt(col_test['candidate'].get('score'))} | |")
        h.append(f"<table>{head}{''.join(body)}</table>")
        h.append(f"<p class=note>Jobs: baseline {state['baseline']}, candidate {state['candidate']}.</p>")
        md.append("")
    h.append("<p class=note>Compare the individual runs in the dashboard: Develop &amp; train → Evaluations, "
             "select the runs of this qualification and click Compare (MLflow experiment "
             "agentic-coding-qualification, tag qualification_id). The baseline is reached through the MaaS "
             "gateway and the candidate directly, so latency includes the gateway hop for the baseline only.</p>")
    style = ("<style>body{font-family:system-ui,sans-serif;margin:24px;color:#151515}table{border-collapse:collapse;"
             "margin:8px 0 16px}th,td{border:1px solid #d2d2d2;padding:6px 10px;text-align:left}"
             "th{background:#f0f0f0}.note{color:#555;font-size:.9em}</style>")
    with open(report.path, "w") as f:
        f.write(f"<!doctype html><html><head><meta charset=utf-8>{style}</head><body>{''.join(h)}</body></html>")
    with open(summary.path, "w") as f:
        f.write("\n".join(md))
    with open(decision.path, "w") as f:
        json.dump({"qualification_id": qualification_id, "verdict": verdict, "reasons": reasons,
                   "baseline": baseline_model, "candidate": candidate_model}, f, indent=1)
    print(f"Recommendation: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    return verdict


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
    candidate_auth_secret: str = "",
    collection_version: str = "v1",
    experiment: str = "agentic-coding-qualification",
    queue: str = "lq-cpu-default",
    evalhub_url: str = "https://evalhub.evalhub.svc.cluster.local:8443",
    tenant: str = "evaluated-models",
    max_regression: float = 0.05,
):
    qualification_id = dsl.PIPELINE_JOB_NAME_PLACEHOLDER
    timeouts = {"agentic-coding-security-full-v1": 4 * 3600}
    previous = []
    results = []
    for collection in COLLECTIONS:
        stage = []
        for role, name, url, auth in (
            ("baseline", baseline_model_name, baseline_model_url, baseline_auth_secret),
            ("candidate", candidate_model_name, candidate_model_url, candidate_auth_secret),
        ):
            task = run_collection(
                role=role, model_name=name, model_url=url, model_auth_secret=auth,
                collection_id=collection, collection_version=collection_version, experiment=experiment,
                queue=queue, evalhub_url=evalhub_url, tenant=tenant, qualification_id=qualification_id,
                timeout_seconds=timeouts.get(collection, 2 * 3600),
            )
            task.set_display_name(f"{collection.removeprefix('agentic-coding-')} · {role}")
            task.set_caching_options(False)
            task.set_cpu_request("100m").set_memory_request("256Mi").set_cpu_limit("500m").set_memory_limit("512Mi")
            kubernetes.use_config_map_as_volume(task, config_map_name=SERVICE_CA_CONFIGMAP, mount_path=SERVICE_CA_DIR)
            if previous:
                task.after(*previous)
            stage.append(task)
            results.append(task.outputs["results_json"])
        previous = stage

    board = leaderboard(
        evalhub_url=evalhub_url, tenant=tenant, qualification_id=qualification_id,
        baseline_model=baseline_model_name, candidate_model=candidate_model_name,
        max_regression=max_regression,
        r1=results[0], r2=results[1], r3=results[2], r4=results[3],
        r5=results[4], r6=results[5], r7=results[6], r8=results[7],
    )
    board.set_display_name("leaderboard and recommendation")
    board.set_caching_options(False)
    board.set_cpu_request("100m").set_memory_request("256Mi").set_cpu_limit("500m").set_memory_limit("512Mi")
    kubernetes.use_config_map_as_volume(board, config_map_name=SERVICE_CA_CONFIGMAP, mount_path=SERVICE_CA_DIR)
