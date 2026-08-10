# AD-009 §3.3 / §3.5 — Context budget / harness ceiling BLOCK

When `prompt_tokens + max_tokens > max-model-len`, the harness **must refuse
emit** client-side (AD-002 §1 pre-flight ceiling guard). Do **not** discover the
ceiling via `VLLMValidationError` on the serving tier.

## Verdict fields (required)

| Field | Example |
|-------|---------|
| `block_class` | `context_budget` |
| `harness_ceiling_guard` | `true` |
| `prompt_tokens` / `max_tokens` / `max_model_len` | integers |
| `trigger` | `preflight_ceiling_guard` \| `vllm_validation_error` \| `compound_secondary` |
| `secondary_to` | optional primary class (e.g. `environmental_provider`) |

```bash
# Check (exit 2 = REFUSE):
python3 .hermes/home/scripts/check-preflight-ceiling.py \
  --prompt-tokens 122881 --max-tokens 8192 --max-model-len 131072

# Stamp on refuse:
python3 .hermes/home/scripts/check-preflight-ceiling.py \
  --prompt-tokens 122881 --max-tokens 8192 --task-id t_xxx --stamp

# Or stamp directly (e.g. compound secondary after server reject was observed):
python3 .hermes/home/scripts/stamp-context-budget-block.py \
  --task-id t_xxx --model-id qwen3-6-27b \
  --prompt-tokens 122881 --max-tokens 8192 \
  --trigger compound_secondary --secondary-to environmental_provider
```

## Compound terminals

When an earlier window is `environmental_provider` and a later window is ceiling
overflow, stamp **both** (AD-009 §3.5). Overflow alone is **not** wall-fit sizing
evidence. No MiniMax (AD-008).
