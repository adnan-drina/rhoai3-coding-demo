"""Every application-wide source component is owned by the plan (H-20 early gate, v31).

v31: the source's exception advice compiled on the destination's compatibility layer, so no compile finding named it
and no card owned it; it was found hours into M3, one behaviour card at a time. This gate runs at M2 admission: every
source type the cross-cutting catalog classifies (an annotation such as an exception advice, a security or web
configuration, a filter, an aspect; a supertype such as a servlet Filter or a WebMvcConfigurer) must be OWNED --

  * a planned outcome's ``plan_paths`` or a requirement's ``paths`` hold its file, or
  * decisions.yaml ``retired_sources`` retires its file (with its ADR), or
  * the bootstrap handles it by catalog (compat-mapping ``main_class``: the annotation the bootstrap deletes).

Anything else is ``UNPLANNED_SOURCE_COMPONENT``, named with the classification that made it one. Pure; nothing here
knows a specimen.
"""
from __future__ import annotations

from typing import Any, Iterable


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def classified(t: dict[str, Any], cross_cutting: dict[str, Any]) -> list[str]:
    """The catalog classifications a type carries: its annotations and supertypes the cross-cutting catalog names."""
    anns = set((cross_cutting or {}).get("annotations") or {})
    sups = set((cross_cutting or {}).get("supertypes") or {})
    got = {_s(a.get("fqn")) for a in t.get("annotations") or [] if isinstance(a, dict) and _s(a.get("fqn")) in anns}
    got |= {_s(x) for x in t.get("supertypes") or [] if _s(x) in sups}
    return sorted(got)


def unplanned(types: Iterable[dict[str, Any]], *, cross_cutting: dict[str, Any], plan_nodes: Iterable[dict[str, Any]],
              requirements: Iterable[dict[str, Any]], retired_paths: Iterable[str], bootstrap_annotations: Iterable[str]
              ) -> list[dict[str, Any]]:
    """[{fqn, path, classified_by}] for every classified source type nothing owns."""
    owned = {_s(p) for n in plan_nodes or [] if isinstance(n, dict) for p in n.get("plan_paths") or []}
    owned |= {_s(p) for r in requirements or [] if isinstance(r, dict) for p in r.get("paths") or []}
    owned |= {_s(p) for p in retired_paths or []}
    boot = set(bootstrap_annotations or [])
    out = []
    for t in sorted((t for t in types or [] if isinstance(t, dict) and _s(t.get("fqn"))), key=lambda t: t["fqn"]):
        path = _s(t.get("path"))
        if not path or "/src/test/" in "/" + path:
            continue
        why = classified(t, cross_cutting)
        if not why or path in owned:
            continue
        if any(_s(a.get("fqn")) in boot for a in t.get("annotations") or [] if isinstance(a, dict)):
            continue
        out.append({"fqn": t["fqn"], "path": path, "classified_by": why})
    return out


def bootstrap_annotations(catalog: dict[str, Any]) -> list[str]:
    """The annotations whose types the bootstrap itself handles (compat-mapping ``main_class``)."""
    mc = (catalog or {}).get("main_class") or {}
    return [_s(mc.get("annotation"))] if _s(mc.get("annotation")) and _s(mc.get("action")) else []
