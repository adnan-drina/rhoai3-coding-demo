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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
