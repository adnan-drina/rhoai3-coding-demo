"""The in-cluster MaaS route, checked before any card is dispatched (B1).

v12 (2026-09-24) was created without the pod hostAlias that routes the
worker's MaaS endpoint to the in-cluster gateway Service, so its model
traffic took the public load balancer, whose idle timeout cuts silent
tool-call streams. The factory now stamps the alias, but a stale catalog, a
hand-made devfile or a direct start could still reach dispatch without it.

This is the one startup check, shared by auto-start (every start and every
continuation) and the Operator preflight. It asks four questions:

  1. the platform told this workspace which gateway host and internal
     Service address to use (RHOAI3_MAAS_HOST / RHOAI3_MAAS_INTERNAL_IP,
     stamped into the devfile by the app-migration template);
  2. the worker's MaaS endpoint (MAAS_API_BASE_URL) is that host;
  3. that host resolves, in this pod, to exactly that address;
  4. a TCP connection and a verified TLS handshake (SNI = the host) succeed
     through it -- the governed gateway, never a direct model endpoint.

Any "no" is REFUSE STARTUP_MAAS_ROUTE naming what was expected, what was
found and where the expected value comes from; nothing is dispatched. The
result is recorded in run control (route.json) with the values checked.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import socket
import ssl
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

HOST_RE = re.compile(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*")
IPV4_RE = re.compile(r"(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}")
SOURCE = "the app-migration template's devfile env, stamped from the platform entity at creation"


def _resolve(host: str) -> set[str]:
    return {a[4][0] for a in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}


def _connect(host: str, ip: str, timeout: float = 5.0) -> str:
    """'' when a TCP connection to ip:443 completes a TLS handshake verified for
    `host` with the trust the worker's client uses, else why not."""
    cafile = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE") or None
    try:
        ctx = ssl.create_default_context(cafile=cafile)
    except (OSError, ssl.SSLError) as exc:
        return "the CA bundle %s cannot be loaded (%s)" % (cafile, exc)
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host):
                return ""
    except ssl.SSLCertVerificationError as exc:
        return "TLS verification for %s failed (%s)" % (host, exc.verify_message or exc)
    except OSError as exc:
        return "no TLS connection to %s:443 (%s)" % (ip, exc)


def route_gaps(environ: dict[str, str], *, resolve: Callable[[str], set[str]] = _resolve,
               connect: Callable[[str, str], str] = _connect) -> tuple[list[str], dict[str, Any]]:
    """(refusals, record). Empty refusals = the route is the governed one."""
    host = (environ.get("RHOAI3_MAAS_HOST") or "").strip()
    ip = (environ.get("RHOAI3_MAAS_INTERNAL_IP") or "").strip()
    url = (environ.get("MAAS_API_BASE_URL") or "").strip()
    rec: dict[str, Any] = {"expected_host": host, "expected_ip": ip, "endpoint": url}
    gaps: list[str] = []
    for name, value, rx in (("RHOAI3_MAAS_HOST", host, HOST_RE), ("RHOAI3_MAAS_INTERNAL_IP", ip, IPV4_RE)):
        if not value:
            gaps.append("%s is not set; its source is %s" % (name, SOURCE))
        elif "_" in value or not rx.fullmatch(value):
            gaps.append("%s is %r, not a valid value (an unrendered placeholder?); its source is %s" % (name, value, SOURCE))
    if not url:
        gaps.append("MAAS_API_BASE_URL is not set: the worker has no MaaS endpoint")
    if gaps:
        return gaps, rec
    got_host = (urlsplit(url).hostname or "").lower()
    rec["endpoint_host"] = got_host
    if got_host != host:
        return ["the worker's MaaS endpoint host is %s, not the platform gateway %s" % (got_host or "(none)", host)], rec
    try:
        addrs = resolve(host)
    except OSError as exc:
        return ["%s does not resolve in this pod (%s)" % (host, exc)], rec
    rec["resolved"] = sorted(addrs)
    if addrs != {ip}:
        return ["endpoint %s resolves to %s; required gateway Service address %s: the pod has no hostAlias for it and "
                "would reach MaaS over the public load balancer" % (host, ", ".join(sorted(addrs)) or "nothing", ip)], rec
    why = connect(host, ip)
    if why:
        return ["the governed gateway at %s (%s) is not reachable: %s" % (host, ip, why)], rec
    rec["tls"] = "verified"
    return [], rec


def record(root: Path, gaps: list[str], rec: dict[str, Any]) -> None:
    try:
        from planner import run_control
    except Exception:
        return
    decl = run_control.declared(root)
    if not decl or decl.get("error"):
        return
    doc = dict(rec, ok=not gaps, gaps=gaps,
               checked_at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    # the run's harness state directory (the declared run_control.state); the
    # read-only platform record cannot hold it
    p = decl["state"] / "route.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="")
    a = ap.parse_args(argv)
    gaps, rec = route_gaps(dict(os.environ))
    if a.root:
        record(Path(a.root), gaps, rec)
    if gaps:
        print("REFUSE STARTUP_MAAS_ROUTE: %s; no card dispatched" % gaps[0], file=sys.stderr)
        return 1
    print("OK: MaaS route %s -> %s, TLS verified through the governed gateway" % (rec["expected_host"], rec["expected_ip"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
