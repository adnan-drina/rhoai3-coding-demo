"""The source's exception advice, read from the frozen structural model (H-20, D-2; v31).

A source exception advice (Spring MVC ``@ControllerAdvice`` / ``@RestControllerAdvice`` with ``@ExceptionHandler``
methods) turns exceptions into error responses application-wide. It compiles on the destination's compatibility layer,
so no compile finding ever names it, and its behaviour can silently stop: Quarkus spring-web scans only
``@RestControllerAdvice`` (https://quarkus.io/guides/spring-web). M2 therefore plans it as its own requirement, and the
comparator recognises the responses it produced by their SHAPE.

The shape is derived, never assumed: the body key sets an advice can answer are the field names of the model types
the advice references (its ``type_refs`` that carry fields -- PetClinic's ``ErrorInfo`` {className, exMessage}, another
application's own error type). Which annotations make a type an advice comes from the catalog
(compat-mapping ``exception_advice.advice_annotations``). Nothing here knows a specimen.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

DEFAULT_ANNOTATIONS = ("org.springframework.web.bind.annotation.ControllerAdvice",
                       "org.springframework.web.bind.annotation.RestControllerAdvice")
HANDLER_ANNOTATION = "org.springframework.web.bind.annotation.ExceptionHandler"


def _s(v: Any) -> str:
    return v if isinstance(v, str) else ""


def advice_annotations(catalog: dict[str, Any] | None) -> tuple[str, ...]:
    got = (((catalog or {}).get("exception_advice") or {}).get("advice_annotations")) or []
    return tuple(str(a) for a in got) or DEFAULT_ANNOTATIONS


def advice_types(types: Iterable[dict[str, Any]], catalog: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every model type annotated with a catalogued advice annotation, by fqn."""
    anns = set(advice_annotations(catalog))
    return sorted((t for t in types or [] if isinstance(t, dict) and _s(t.get("fqn"))
                   and any(_s(a.get("fqn")) in anns for a in t.get("annotations") or [] if isinstance(a, dict))),
                  key=lambda t: t["fqn"])


def handlers(advice: dict[str, Any]) -> list[dict[str, Any]]:
    """The advice's exception handlers: signature and the exception types the annotation names (empty = the
    handler's parameter types decide, as Spring does)."""
    out = []
    for m in advice.get("methods") or []:
        if not isinstance(m, dict):
            continue
        for a in m.get("annotations") or []:
            if isinstance(a, dict) and _s(a.get("fqn")) == HANDLER_ANNOTATION:
                vals = [str(x) for v in (a.get("values") or {}).values() for x in (v if isinstance(v, list) else [v])]
                out.append({"signature": _s(m.get("signature")), "handles": vals})
    return out


def body_key_sets(advice: dict[str, Any], types: Iterable[dict[str, Any]]) -> list[list[str]]:
    """The JSON key sets the advice can answer: for each model type it references that declares fields, the
    sorted field names (non-static). Empty when the model shows none (the shape is then unknown, never guessed)."""
    by_fqn = {_s(t.get("fqn")): t for t in types or [] if isinstance(t, dict)}
    out: list[list[str]] = []
    for ref in advice.get("type_refs") or []:
        t = by_fqn.get(_s(ref))
        if not t:
            continue
        names = sorted({_s(f.get("name")) for f in t.get("fields") or []
                        if isinstance(f, dict) and _s(f.get("name")) and "static" not in (f.get("modifiers") or [])})
        if names and names not in out:
            out.append(names)
    return sorted(out)


def shapes(types: Iterable[dict[str, Any]], catalog: dict[str, Any] | None) -> list[dict[str, Any]]:
    """[{fqn, path, annotation, handlers, body_keys}] for every advice in the model."""
    types = list(types or [])
    anns = set(advice_annotations(catalog))
    out = []
    for t in advice_types(types, catalog):
        ann = next(_s(a.get("fqn")) for a in t.get("annotations") or [] if isinstance(a, dict) and _s(a.get("fqn")) in anns)
        out.append({"fqn": t["fqn"], "path": _s(t.get("path")), "annotation": ann, "handlers": handlers(t),
                    "body_keys": body_key_sets(t, types)})
    return out


def shapes_of_root(root: Path) -> list[dict[str, Any]]:
    """shapes() over the run's frozen evidence bundle and catalog; [] when either is missing."""
    from planner.paths import EVIDENCE_BUNDLE
    root = Path(root)
    try:
        bundle = json.loads((root / EVIDENCE_BUNDLE).read_text(encoding="utf-8"))
        catalog = json.loads((root / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return shapes(((bundle.get("structure") or {}).get("types")) or [], catalog)


def _json_object(raw: Any) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return None
    try:
        doc = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw))
    except (UnicodeDecodeError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def advice_response(status: Any, body: Any, advice_shapes: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """The advice whose shape a SOURCE response has: an error status (4xx/5xx) and a JSON object whose keys are
    exactly one of that advice's derived key sets. None otherwise."""
    try:
        code = int(str(status))
    except ValueError:
        return None
    doc = _json_object(body)
    if code < 400 or doc is None:
        return None
    keys = sorted(doc)
    for sh in advice_shapes or []:
        if keys in (sh.get("body_keys") or []):
            return sh
    return None


def source_responses(root: Path) -> dict[str, dict[str, Any]]:
    """scenario id -> {status, body} from the frozen source's captures (every security mode's scenario directory);
    the retained response body when the capture names one."""
    base = Path(root) / "verification" / "source-oracles"
    out: dict[str, dict[str, Any]] = {}
    for d in sorted(p for p in base.glob("scenarios*") if p.is_dir()):
        for f in sorted(d.glob("*.json")):
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(doc, dict) or not doc.get("scenario") or not isinstance(doc.get("response"), dict):
                continue
            resp = doc["response"]
            ev = resp.get("evidence") if isinstance(resp.get("evidence"), dict) else {}
            body = None
            for cand in ([Path(root) / str(ev["body_file"])] if ev.get("body_file") else []) + [d / "bodies" / f.stem / "response.body"]:
                if cand.is_file():
                    body = cand.read_bytes()
                    break
            if body is None and resp.get("body_sample") is not None:
                body = resp.get("body_sample")
            out[str(doc["scenario"])] = {"status": resp.get("status"), "body": body}
    return out


def advice_scenarios(advice_shapes: Iterable[dict[str, Any]], responses: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """advice fqn -> the scenarios whose SOURCE response is that advice's (an error status in one of its shapes)."""
    shapes_ = list(advice_shapes or [])
    out: dict[str, list[str]] = {sh["fqn"]: [] for sh in shapes_}
    for sid, r in sorted((responses or {}).items()):
        sh = advice_response(r.get("status"), r.get("body"), shapes_)
        if sh is not None:
            out[sh["fqn"]].append(sid)
    return out
