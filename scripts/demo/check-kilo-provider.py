#!/usr/bin/env python3
"""Read the Dev Spaces AI-tools init script on stdin and check the Kilo provider SHAPE it generates
(architect review B3, 2026-10-01: an endpoint string present somewhere in the script is weaker than proof
that the intended provider is configured and selectable).

Usage: oc get configmap devspace-ai-tools-init ... | check-kilo-provider.py <provider> <model> <path-segment>
Prints "provider-ok" or the first failed property."""
from __future__ import annotations

import json
import re
import sys


def kilo_config(script: str) -> dict:
    """The kilo.jsonc heredoc body, with the shell expansions replaced by placeholders."""
    m = re.search(r'cat > "\$\{HOME\}/\.config/kilo/kilo\.jsonc" <<KILOEOF\n(.*?)\n\s*KILOEOF', script, re.S)
    if not m:
        raise ValueError("no kilo.jsonc heredoc in the init script")
    body = m.group(1).replace("\\$", "$")
    body = re.sub(r"\$\{[A-Z0-9_]+\}", "PLACEHOLDER", body)
    return json.loads(body)


def check(script: str, provider: str, model: str, segment: str) -> str:
    try:
        cfg = kilo_config(script)
    except ValueError as exc:
        return str(exc)
    if provider not in (cfg.get("enabled_providers") or []):
        return "provider %s is not in enabled_providers %s" % (provider, cfg.get("enabled_providers"))
    if provider in (cfg.get("disabled_providers") or []):
        return "provider %s is disabled" % provider
    p = (cfg.get("provider") or {}).get(provider)
    if not isinstance(p, dict):
        return "no provider.%s block" % provider
    if p.get("npm") != "@ai-sdk/openai-compatible":
        return "provider.%s.npm is %r, not the OpenAI-compatible adapter" % (provider, p.get("npm"))
    url = str((p.get("options") or {}).get("baseURL") or "")
    if url != "PLACEHOLDER/v1":
        return "provider.%s.options.baseURL %r is not the common MaaS base for %s" % (provider, url, segment)
    if not (p.get("options") or {}).get("apiKey"):
        return "provider.%s.options.apiKey is empty" % provider
    if "publishers/internal-models/models/" + model not in (p.get("models") or {}):
        return "provider.%s.models has no %s" % (provider, model)
    default_provider, separator, default_model = str(cfg.get("model") or "").partition("/")
    selected = (cfg.get("provider") or {}).get(default_provider) or {}
    if not separator or default_model not in (selected.get("models") or {}):
        return "default model selector does not preserve a configured canonical model ID"
    return "provider-ok"


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: check-kilo-provider.py <provider> <model> <path-segment>", file=sys.stderr)
        sys.exit(2)
    print(check(sys.stdin.read(), *sys.argv[1:]))
