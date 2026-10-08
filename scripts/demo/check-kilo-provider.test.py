#!/usr/bin/env python3
"""check-kilo-provider.py on the init script GitOps actually ships, and on broken variants of it."""
import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("k", ROOT / "scripts" / "demo" / "check-kilo-provider.py")
K = importlib.util.module_from_spec(spec)
spec.loader.exec_module(K)
docs = yaml.safe_load_all((ROOT / "gitops/stages/070-advanced-app-platform/base/devspaces/maas-api-key-provisioning.yaml").read_text())
S = next(d for d in docs if d and d.get("kind") == "ConfigMap" and "init-ai-tools.sh" in (d.get("data") or {}))["data"]["init-ai-tools.sh"]

cases = [
    (S, ("qwen27b", "qwen3-6-27b", "qwen3-6-27b"), "ok"),
    (S, ("qwen38", "qwen3-8-27b-int4", "qwen3-8-27b-int4"), "ok"),
    (S.replace('"enabled_providers": ["qwen38", "qwen27b"]', '"enabled_providers": ["qwen38"]'), ("qwen27b", "qwen3-6-27b", "qwen3-6-27b"), "enabled_providers"),
    (S.replace("/internal-models/qwen3-6-27b/v1", "/internal-models/qwen3-8-27b-int4/v1"), ("qwen27b", "qwen3-6-27b", "qwen3-6-27b"), "baseURL"),
    (S.replace('"qwen3-6-27b": {', '"qwen3-6-27b-x": {'), ("qwen27b", "qwen3-6-27b", "qwen3-6-27b"), "models has no"),
    ("echo no kilo here", ("qwen27b", "qwen3-6-27b", "qwen3-6-27b"), "no kilo.jsonc"),
]
ok = True
for text, args, want in cases:
    got = K.check(text, *args)
    good = got == "provider-ok" if want == "ok" else (got != "ok" and want in got)
    print(("ok " if good else "FAIL ") + "%s -> %s" % (want, got))
    ok = ok and good
print("OK: check-kilo-provider" if ok else "FAIL")
sys.exit(0 if ok else 1)
