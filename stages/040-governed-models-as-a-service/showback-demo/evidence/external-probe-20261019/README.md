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
