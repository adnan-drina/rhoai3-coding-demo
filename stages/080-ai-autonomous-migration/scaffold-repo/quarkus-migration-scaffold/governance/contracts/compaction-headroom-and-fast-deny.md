# Compaction headroom + fast-deny (AD-009)

## Compaction headroom

Auto-compress **must** trigger at or below:

```
context_length − max_tokens − margin
```

For this demo pin (`context_length=131072`, `max_tokens=8192`, `margin≥4096`):

```
threshold_tokens ≤ 118784
```

Never treat `context_length` alone as the compress trigger — one token past
`context_length − max_tokens` is a hard vLLM 400.

Tip/live config:

```yaml
compression:
 enabled: true
 threshold_tokens: 110000 # headroom under 118784
```

`ensure-provider-max-tokens.py --apply` also pins this.

## Fast-deny

A **4xx validation** error about context/max_tokens (`VLLMValidationError`,
`maximum context length`, `you requested … output tokens`) is **terminal for
that prompt**. Do **not** sleep-retry the same over-limit request (r3 burned
~34 min on 15-min retries).

Caller: `kanban-stuck-watchdog` invokes
`check-vllm-validation-fast-deny.py --stamp` for every `running` task.

On match: stamp `context_budget` (trigger `vllm_validation_error`) and alert.
Board block remains dispatcher after stamp + human steward action.
