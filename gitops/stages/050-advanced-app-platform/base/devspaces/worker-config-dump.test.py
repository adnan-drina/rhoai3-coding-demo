#!/usr/bin/env python3
"""The worker config dest-init writes is readable by the harness (v13, 2026-09-25).

The provider slot and the compression slot are built from the same profile
request body; a shallow copy left their nested `chat_template_kwargs` one
object, PyYAML wrote it as an &id001 anchor and *id001 alias, and the
harness reader (planner.yamlite, which the workspace's python3.9 runs
without PyYAML) refused it: v13's first start reported MODEL_PROFILE_MISMATCH
before any card ran.

This test renders the worker config with the committed producer code
(hermes-runtime/b3-b4/render_worker_config.py), applies the producer's own
dump argument expression to it, and requires that nothing mutable is shared
(no anchor can be written), while the unshared-copy step is what makes it so.
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PRODUCER = HERE / "maas-api-key-provisioning.yaml"
sys.path.insert(0, str(REPO / "stages/080-ai-autonomous-migration/hermes-runtime/b3-b4"))
if "yaml" not in sys.modules:
    try:
        import yaml  # noqa: F401
    except ImportError:   # the rendered prefix only imports it
        sys.modules["yaml"] = types.ModuleType("yaml")
from render_worker_config import render  # noqa: E402


def _shared(obj, seen=None, path="cfg"):
    seen = {} if seen is None else seen
    if isinstance(obj, (dict, list)):
        if id(obj) in seen:
            return ["%s is the same object as %s" % (path, seen[id(obj)])]
        seen[id(obj)] = path
        items = obj.items() if isinstance(obj, dict) else enumerate(obj)
        return [s for k, v in items for s in _shared(v, seen, "%s.%s" % (path, k))]
    return []


def main() -> int:
    cfg = render(REPO)
    before = _shared(cfg)
    if not before:
        print("FAIL: the rendered config no longer shares a nested value; this test must be revisited", file=sys.stderr)
        return 1
    m = re.search(r"yaml\.safe_dump\((.+), fh, default_flow_style=False, sort_keys=False\)", PRODUCER.read_text())
    if not m:
        print("FAIL: the producer's worker-config dump call was not found", file=sys.stderr)
        return 1
    dumped = eval(m.group(1), {"_pjson": json, "json": json}, {"cfg": cfg})
    after = _shared(dumped)
    if after:
        print("FAIL: the producer dumps shared nested values (a YAML anchor the harness refuses): %s" % after[:3], file=sys.stderr)
        return 1
    if dumped != cfg:
        print("FAIL: the unsharing step changed the config", file=sys.stderr)
        return 1
    print("OK: worker config dump (the rendered config shares %d nested value(s), e.g. %s; the producer's dump "
          "argument shares none and is equal to it, so no YAML anchor is written)" % (len(before), before[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
