#!/usr/bin/env python3
"""Turn a GuideLLM benchmark-results.json into a capacity-planning report.

Reads the multi-level output of a `concurrent` or `sweep` GuideLLM run and
derives the numbers a platform or business owner needs: the optimal load,
the maximum stable concurrency, the breaking point, and how those translate
into RAG-chatbot user capacity once guardrail self-check calls are counted.

Latency SLOs are the knobs. Defaults target an interactive assistant:
  --ttft-slo-ms        p95 time-to-first-token budget (default 2000)
  --itl-slo-ms         p95 inter-token-latency budget (default 200)
  --max-error-rate     tolerated error fraction (default 0.01)
Chatbot amplification (guardrail self-check adds LLM calls per turn):
  --calls-per-turn     model calls per chatbot turn (default 3:
                       self-check input + generation + self-check output)
Cost planning (RHOAI managing-and-monitoring-models lists cost/1M tokens):
  --gpu-cost-per-hour  hourly cost of the serving GPU (default 0 = disabled;
                       e.g. an AWS g6e.2xlarge is ~1.86 USD/hr on-demand)

Usage:
  analyze-guidellm.py benchmark-results.json [--output capacity-report.md]
"""

import argparse
import json
import sys


def _stat(metric, field="successful"):
    """Return the stat block for a metric, tolerating missing fields."""
    if not isinstance(metric, dict):
        return {}
    block = metric.get(field) or metric.get("total") or {}
    return block if isinstance(block, dict) else {}


def _p(metric, pct, field="successful"):
    block = _stat(metric, field)
    pcts = block.get("percentiles") or {}
    return pcts.get(pct)


def _mean(metric, field="successful"):
    return _stat(metric, field).get("mean")


def _level_rows(report):
    rows = []
    for b in report.get("benchmarks", []):
        strat = (b.get("config") or {}).get("strategy") or {}
        m = b.get("metrics") or {}
        totals = m.get("request_totals") or {}
        ok = totals.get("successful", 0) or 0
        err = totals.get("errored", 0) or 0
        incomplete = totals.get("incomplete", 0) or 0
        attempted = ok + err + incomplete
        rows.append({
            "type": strat.get("type_", "?"),
            # For concurrent runs this is the requested concurrency; for
            # sweep runs the achieved concurrency is the meaningful axis.
            "requested": strat.get("max_concurrency") or strat.get("streams"),
            "achieved_concurrency": _mean(m.get("request_concurrency", {})),
            "throughput_rps": _mean(m.get("requests_per_second", {})),
            "output_tps": _mean(m.get("output_tokens_per_second", {})),
            "total_tps": _mean(m.get("tokens_per_second", {})),
            "ttft_p95_ms": _p(m.get("time_to_first_token_ms", {}), "p95"),
            "ttft_mean_ms": _mean(m.get("time_to_first_token_ms", {})),
            "itl_p95_ms": _p(m.get("inter_token_latency_ms", {}), "p95"),
            "e2e_p95_s": _p(m.get("request_latency", {}), "p95"),
            "e2e_mean_s": _mean(m.get("request_latency", {})),
            "out_tokens_mean": _mean(m.get("output_token_count", {})),
            "ok": ok,
            "errored": err,
            "incomplete": incomplete,
            "error_rate": (err + incomplete) / attempted if attempted else 0.0,
        })
    # Sort by the load axis so "first breaching level" is meaningful.
    rows.sort(key=lambda r: (r["requested"] or 0, r["achieved_concurrency"] or 0))
    return rows


def _within_slo(row, args):
    ttft = row["ttft_p95_ms"]
    itl = row["itl_p95_ms"]
    return (
        row["error_rate"] <= args.max_error_rate
        and (ttft is None or ttft <= args.ttft_slo_ms)
        and (itl is None or itl <= args.itl_slo_ms)
    )


def _fmt(v, suffix="", nd=1):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.{nd}f}{suffix}"
    return f"{v}{suffix}"


def analyze(report, args):
    rows = _level_rows(report)
    if not rows:
        raise SystemExit("no benchmark levels found in the results file")

    passing = [r for r in rows if _within_slo(r, args)]
    max_stable = passing[-1] if passing else None

    # Breaking point: first level (by load) that violates the SLO or errors.
    breaking = next((r for r in rows if not _within_slo(r, args)), None)

    # Optimal load / knee: the passing level with the best throughput before
    # throughput stops scaling (next level adds < 10% throughput or fails).
    optimal = None
    for i, r in enumerate(passing):
        nxt = passing[i + 1] if i + 1 < len(passing) else None
        if nxt is None:
            optimal = r
            break
        cur_t = r["throughput_rps"] or 0
        nxt_t = nxt["throughput_rps"] or 0
        if cur_t and (nxt_t - cur_t) / cur_t < 0.10:
            optimal = r
            break
    if optimal is None and passing:
        optimal = passing[-1]

    peak_tps = max((r["output_tps"] or 0) for r in rows)
    peak_rps = max((r["throughput_rps"] or 0) for r in rows)

    def users(row):
        # Interactive users a level supports, discounting guardrail
        # self-check amplification (calls_per_turn model calls per turn).
        if row is None:
            return None
        conc = row["requested"] or row["achieved_concurrency"] or 0
        return conc / max(args.calls_per_turn, 1)

    return {
        "rows": rows,
        "optimal": optimal,
        "max_stable": max_stable,
        "breaking": breaking,
        "peak_output_tps": peak_tps,
        "peak_rps": peak_rps,
        "chatbot_users_optimal": users(optimal),
        "chatbot_users_max": users(max_stable),
    }


def render_md(report, res, args):
    meta = report.get("metadata") or {}
    model = (report.get("args") or {}).get("model") or meta.get("model") or "model"
    lines = []
    lines.append(f"# Model Capacity Report — {model}")
    lines.append("")
    lines.append(
        f"SLOs: TTFT p95 ≤ {args.ttft_slo_ms} ms, ITL p95 ≤ {args.itl_slo_ms} ms, "
        f"error rate ≤ {args.max_error_rate:.0%}. "
        f"Chatbot amplification: {args.calls_per_turn} model calls per turn "
        "(guardrail self-check input + generation + self-check output)."
    )
    lines.append("")

    lines.append("## Headlines")
    opt, mx, br = res["optimal"], res["max_stable"], res["breaking"]
    if opt:
        lines.append(
            f"- **Optimal load**: ~{_fmt(opt['requested'], nd=0)} concurrent requests — "
            f"{_fmt(opt['throughput_rps'],' req/s')}, {_fmt(opt['output_tps'],' out tok/s')}, "
            f"TTFT p95 {_fmt(opt['ttft_p95_ms'],' ms')}. Best throughput before scaling flattens."
        )
    if mx:
        lines.append(
            f"- **Max stable concurrency (within SLO)**: {_fmt(mx['requested'], nd=0)} concurrent requests, "
            f"error rate {_fmt(mx['error_rate']*100,'%')}."
        )
    if br:
        lines.append(
            f"- **Breaking point**: {_fmt(br['requested'], nd=0)} concurrent requests — "
            f"TTFT p95 {_fmt(br['ttft_p95_ms'],' ms')}, ITL p95 {_fmt(br['itl_p95_ms'],' ms')}, "
            f"error rate {_fmt(br['error_rate']*100,'%')} (first level to breach an SLO)."
        )
    else:
        lines.append("- **Breaking point**: not reached in this run — push higher concurrency to find it.")
    lines.append(
        f"- **Peak observed throughput**: {_fmt(res['peak_output_tps'],' output tok/s')} "
        f"({_fmt(res['peak_rps'],' req/s')})."
    )
    lines.append("")

    lines.append("## Business planning")
    u_opt = res["chatbot_users_optimal"]
    if u_opt is not None:
        note = " — this is a single-user demo footprint; relax the TTFT SLO or add a GPU replica for real concurrency" if u_opt < 1 else ""
        lines.append(
            f"- **Recommended concurrent RAG-chatbot users**: "
            f"~{_fmt(u_opt, nd=1)} at optimal load "
            f"(one governed answer costs {args.calls_per_turn} model calls){note}."
        )
    if res["chatbot_users_max"] is not None:
        lines.append(
            f"- **Maximum concurrent chatbot users before SLO breach**: "
            f"~{_fmt(res['chatbot_users_max'], nd=1)}."
        )
    if opt and opt["output_tps"]:
        tok_hr = opt["output_tps"] * 3600
        lines.append(
            f"- **Sustained token capacity at optimal load**: "
            f"~{tok_hr/1e6:.1f}M output tokens/hour ({opt['output_tps']*86400/1e6:.0f}M/day)."
        )
        # Peak throughput sets the best-case cost floor (cost/1M tokens is a
        # key planning metric in the RHOAI managing-and-monitoring guide).
        if args.gpu_cost_per_hour > 0:
            peak_tok_hr = res["peak_output_tps"] * 3600
            if peak_tok_hr > 0:
                cost_per_m_best = args.gpu_cost_per_hour / (peak_tok_hr / 1e6)
                cost_per_m_opt = args.gpu_cost_per_hour / (tok_hr / 1e6)
                lines.append(
                    f"- **Cost per 1M output tokens**: "
                    f"~${cost_per_m_best:.2f} at peak throughput, "
                    f"~${cost_per_m_opt:.2f} at the interactive optimal load "
                    f"(GPU at ${args.gpu_cost_per_hour:.2f}/hr; the gap is the "
                    f"price of low-latency headroom)."
                )
    if mx and mx["out_tokens_mean"] and mx["throughput_rps"]:
        ans_hr = mx["throughput_rps"] * 3600
        lines.append(
            f"- **Answer volume at max stable load**: ~{ans_hr:,.0f} answers/hour "
            f"(~{mx['out_tokens_mean']:.0f} output tokens each)."
        )
    lines.append(
        "- **Scale-out signal**: sustained load near the optimal level with TTFT approaching "
        "the SLO is the trigger to add a model replica (GPU) rather than let latency degrade."
    )
    lines.append("")

    lines.append("## Per-level results")
    lines.append("")
    lines.append(
        "| Concurrency | Throughput (req/s) | Output tok/s | TTFT p95 (ms) | ITL p95 (ms) | "
        "E2E p95 (s) | Errors | Within SLO |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in res["rows"]:
        lines.append(
            f"| {_fmt(r['requested'], nd=0)} | {_fmt(r['throughput_rps'])} | {_fmt(r['output_tps'])} | "
            f"{_fmt(r['ttft_p95_ms'])} | {_fmt(r['itl_p95_ms'])} | {_fmt(r['e2e_p95_s'])} | "
            f"{_fmt(r['error_rate']*100,'%')} | {'yes' if _within_slo(r, args) else 'NO'} |"
        )
    lines.append("")
    lines.append(
        "_Latency percentiles are p95 unless noted. Run this against the direct engine "
        "endpoint (default) to measure the model; run against the MaaS gateway to measure "
        "the governed path including quotas._"
    )
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", help="path to benchmark-results.json")
    ap.add_argument("--output", help="write the report here (default: stdout)")
    ap.add_argument("--ttft-slo-ms", type=float, default=2000.0)
    ap.add_argument("--itl-slo-ms", type=float, default=200.0)
    ap.add_argument("--max-error-rate", type=float, default=0.01)
    ap.add_argument("--calls-per-turn", type=int, default=3)
    ap.add_argument("--gpu-cost-per-hour", type=float, default=0.0)
    args = ap.parse_args()

    with open(args.results) as f:
        report = json.load(f)

    res = analyze(report, args)
    md = render_md(report, res, args)

    if args.output:
        with open(args.output, "w") as f:
            f.write(md)
        print(f"capacity report written to {args.output}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
