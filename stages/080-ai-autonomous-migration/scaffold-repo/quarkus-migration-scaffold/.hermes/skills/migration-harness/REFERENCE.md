# Reference — model routing and cost

## Model routing

Seats are split by evaluated strength: the **orchestrator** runs MiniMax
M2 (`custom:maas-m2`, 196K window) — selected in a full-migration A/B for
lean sessions, packet-size tolerance, and long-horizon loop reliability —
and the **worker** runs the governed local Qwen3.6 27B
(`qwen27b/qwen3-6-27b`), the strongest evaluated coding seat:

```bash
hermes chat --provider custom:maas-m2 --model minimax-m2 -q "..."
```

Trade-off (temporary): `maas-m2` is a direct external endpoint, so its
tokens do not appear on the platform's MaaS dashboard and are not
governed by cluster quotas — the RHOAI 3.4 gateway cannot stream external
models (fixed in 3.5, after which this routes through the gateway too).
The worker stays on the governed local model either way. All-local runs
(27B in both seats) work behind the supervisor's failure classification;
portal models with only 32K context (e.g. gpt-oss-120b) are not
orchestrator candidates: harness sessions routinely exceed 65K input
tokens.

## Cost discipline

Both you and OpenCode run on metered MaaS developer keys. Prefer `rewrite`
(deterministic, no inference cost) wherever the change is mechanical.
Keep worker prompts bounded — one task, explicit acceptance — so retries
stay cheap.
