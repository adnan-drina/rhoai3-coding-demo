#!/usr/bin/env python3
"""yamlite: PyYAML-less parse of the app-migration PetClinic stamp."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.yamlite import YamlLiteError, loads  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def main() -> int:
    got = loads("acceptance:\n  idFields: [id]\n")
    if got != {"acceptance": {"idFields": ["id"]}}:
        return _fail("idFields: [id] must parse without PyYAML: %r" % got)
    got = loads("k: [a, b]\n")
    if got != {"k": ["a", "b"]}:
        return _fail("simple flow sequence: %r" % got)
    try:
        loads("k: [{a: 1}]\n")
    except YamlLiteError:
        pass
    else:
        return _fail("nested flow map must still refuse")
    stamp = (
        "configTransforms:\n"
        "  - from: server.port\n"
        "    to: quarkus.http.port\n"
        "    valueMap:\n"
        '      "9966": "8080"\n'
    )
    got = loads(stamp)
    if got != {
        "configTransforms": [
            {"from": "server.port", "to": "quarkus.http.port", "valueMap": {"9966": "8080"}}
        ]
    }:
        return _fail("quoted valueMap keys must parse without PyYAML: %r" % got)
    # the parser is a planning input: load_yaml reads the golden decisions.yaml
    # with this parser whatever else is importable (PyYAML refuses that file)
    import sys
    import types
    from pathlib import Path as _P
    from planner.yamlite import load_yaml
    decisions = _P(__file__).resolve().parents[3] / "decisions.yaml"
    want = loads(decisions.read_text(encoding="utf-8"))
    fake = types.ModuleType("yaml")
    fake.safe_load = lambda _t: {"parsed": "by an importable yaml module"}
    prev = sys.modules.get("yaml")
    sys.modules["yaml"] = fake
    try:
        got = load_yaml(decisions)
    finally:
        if prev is None:
            sys.modules.pop("yaml", None)
        else:
            sys.modules["yaml"] = prev
    if got != want or not isinstance(got, dict) or not got:
        return _fail("load_yaml must use the subset parser even when a yaml module is importable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
