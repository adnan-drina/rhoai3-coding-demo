#!/usr/bin/env python3
"""maas_route selftest (B1): the startup route gate, with a fake resolver and
connector, under two gateway hosts and Service addresses.

  * the governed route passes and records what it checked
  * a pod whose endpoint resolves publicly (no hostAlias) is refused, naming
    the actual and the required address
  * missing or placeholder expected values are refused, naming the source
  * an endpoint host other than the gateway is refused
  * a TLS failure through the gateway is refused
  * the real TLS path refuses an unreachable address (loopback, closed port)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.maas_route import _connect, route_gaps  # noqa: E402


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def _case(host: str, ip: str) -> int:
    env = {"RHOAI3_MAAS_HOST": host, "RHOAI3_MAAS_INTERNAL_IP": ip,
           "MAAS_API_BASE_URL": "https://%s/maas-api/v1" % host}
    ok_resolve = lambda h: {ip}
    public = lambda h: {"52.18.33.7"}
    ok_tls = lambda h, i: ""
    gaps, rec = route_gaps(env, resolve=ok_resolve, connect=ok_tls)
    if gaps or rec.get("tls") != "verified" or rec.get("resolved") != [ip]:
        return _fail("the governed route passes and records it (%s): %s %s" % (host, gaps, rec))
    gaps, _ = route_gaps(env, resolve=public, connect=ok_tls)
    if not gaps or "52.18.33.7" not in gaps[0] or ip not in gaps[0] or "public load balancer" not in gaps[0]:
        return _fail("a public resolution is refused naming actual and required addresses (%s): %s" % (host, gaps))
    for missing in ("RHOAI3_MAAS_HOST", "RHOAI3_MAAS_INTERNAL_IP"):
        e = dict(env)
        e.pop(missing)
        gaps, _ = route_gaps(e, resolve=ok_resolve, connect=ok_tls)
        if not gaps or missing not in gaps[0] or "app-migration template" not in gaps[0]:
            return _fail("a missing %s is refused naming its source: %s" % (missing, gaps))
    gaps, _ = route_gaps(dict(env, RHOAI3_MAAS_INTERNAL_IP="__RHOAI3_MAAS_INTERNAL_IP__"), resolve=ok_resolve, connect=ok_tls)
    if not gaps or "placeholder" not in gaps[0]:
        return _fail("an unrendered placeholder is refused: %s" % gaps)
    gaps, _ = route_gaps(dict(env, MAAS_API_BASE_URL="https://model.internal.example/v1"), resolve=ok_resolve, connect=ok_tls)
    if not gaps or "not the platform gateway" not in gaps[0]:
        return _fail("an endpoint that is not the gateway host is refused: %s" % gaps)
    gaps, _ = route_gaps(env, resolve=ok_resolve, connect=lambda h, i: "TLS verification for %s failed (self-signed)" % h)
    if not gaps or "not reachable" not in gaps[0] or "TLS verification" not in gaps[0]:
        return _fail("a TLS failure through the gateway is refused: %s" % gaps)
    return 0


def main() -> int:
    if _case("maas.apps.cluster-a.example.test", "172.30.250.250") or _case("gw.models.lab", "10.96.7.21"):
        return 1
    why = _connect("localhost", "127.0.0.1", timeout=1.0)
    if not why:
        return _fail("the real TLS path refuses an address with nothing listening on 443")
    print("OK: maas_route (the governed route passes and is recorded; a public resolution, a missing or placeholder "
          "expected value, a non-gateway endpoint and a TLS failure are each STARTUP_MAAS_ROUTE refusals naming what "
          "was expected and found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
