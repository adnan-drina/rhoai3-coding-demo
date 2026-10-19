# Bounded external model probe — 2026-10-19

`probe.json` contains sanitized observed receipts for exactly two nonstreaming Nemotron 3 Ultra 550B requests through
the existing governed MaaS route, using the genuine `ai-admin` owner and `personal-ai-admin` subscription. Each request
had `max_tokens: 128`, thinking disabled, a 60-second timeout and no retry. The observed period was
2026-10-19 10:29:28–10:29:30 UTC. Both requests returned HTTP 200 with successful transport and provider usage of
21 input tokens and 2 output tokens each: **2 requests, 42 input tokens, 4 output tokens**.

The inventory lists all three configured external models: GPT-6 Luna, Claude Sonnet 5.5 and Nemotron 3 Ultra 550B.
Only Nemotron was probed. No request or token totals are asserted for the other models.

`key-revocation-confirmation.json` records the independent owner metadata read after cleanup: the temporary key was
`revoked`. Raw HTTP bodies, headers, login credentials, API keys and cluster URLs remain outside Git.

The sanitized probe SHA-256 is `f8571896dc9d653c27cc0112fe3785ddc99dd99527c0b27164c82164e9bf886c`.
Render its immutable receipt gauges without a network request:

```bash
bash stages/040-governed-models-as-a-service/showback-demo/render-external-probe.sh \
  --probe stages/040-governed-models-as-a-service/showback-demo/evidence/external-probe-20261019/probe.json \
  --output /private/tmp/external-probe.prom
```

To compose those gauges into a new publisher file offline, add
`--publisher gitops/stages/040-governed-models-as-a-service/040-showback-demo/publisher-report.yaml`
and choose a new `.yaml` output path. The renderer replaces only its `showback_external_*` metrics and comments;
existing Qwen metrics and the selected Qwen report annotation remain unchanged.

Focused capture validation is `bash stages/040-governed-models-as-a-service/showback-demo/tests/test-external-probe.sh`.
It uses offline substitutes to check the two-request ceiling, separate platform and genuine-owner contexts, key
revocation and a failed response with unavailable token usage. The live probe itself verified successful completion
and independent key revocation; the failed-response path is fixture evidence.

This is response-receipt evidence for a bounded probe, with one observed user. Gateway token-counter reconciliation,
monthly statements, prices, provider invoices, cache categories, quality, capacity and production reliability were
not qualified. Costs and unmeasured usage remain unknown. NVIDIA identifies its catalog endpoint as a free prototype
service, which does not establish a monthly tariff or paid-provider rate:
[official model catalog](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b).

The three offer comparison dashboards were deployed through the dedicated Application at
`52b921c04fc5395f766d922023deffc56eb5507d`, followed by two display-only label mappings at
`bae0521f62ed05959d93bff24b491ef1b0a06ffa`. The [independent validation](offer-dashboard-validation.json)
records all 58 native datasource queries, exact installed Table transformations, 24-resource source readback,
all nine external metric series and the unchanged Qwen report. The existing publisher remained Ready with zero
restarts. The original three bounded dashboards and five monthly candidates remain byte-identical.

[Browser acceptance](offer-dashboard-browser-readback.json) covers all 28 new panels at 788 px and 1440 px.
All 23 tables rendered; authored panel interiors had no horizontal overflow. External shows the three configured
models, Nemotron's exact 2/42/4 counts and one verified caller. Dedicated shows explicit missing states. Shared
preserves Engineering $0.15, Support $0.07 and platform idle $0.12, with exact 653/1,100 team token counts.
Monthly rates and recovery remain Unknown. The final External labels read **Request test** and **OK**.
The native application's tab strip still scrolls; live chart time and report UTC periods remain separate.

Rollback uses the matching checkout and published prior revision through the same Stage 040 component entrypoint.
No MaaS access policy, model deployment, GPU capacity or native Loki/metering activation changed in this update.
Implementation and independent validation used GPT-6.1 Sol sub-agents under the lead agent; human review remains
required before merge.
