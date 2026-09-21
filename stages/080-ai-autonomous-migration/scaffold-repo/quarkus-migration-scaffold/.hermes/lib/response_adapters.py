"""Source-preserving response adapters (ADR-019): contracts, rendering, install.

Two harness capabilities, each with its OWN naming contract and its OWN
obligation, sharing only this plumbing:

  ``source-cors-response-adapter/v1``          the SOURCE's cross-origin
      behaviour, reproduced at the platform's HTTP route level (it reaches the
      platform's early preflight answer). Authorized by a PARITY_CORS
      obligation. Its permissions are RENDERED from the frozen source's own CORS
      policy (M1's structural model: every @CrossOrigin, the handler mappings it
      covers, and the source's security configuration), never from a capture.
  ``source-media-type-parameter-adapter/v1``   one decided media-type
      parameter removed from the decided media types. Authorized by a
      PARITY_CONTENT_TYPE obligation; a CORS obligation never authorizes it.

Each adapter is a fixed Java file (no application value in it) installed
byte-for-byte at the path its contract names, plus explicit configuration rows
in ``src/main/resources/application.properties`` inside a marked block. The
installer replaces only rows of the capability's OWN key family, records every
row it replaced, refuses a profile-scoped row of that family (it would silently
diverge in that profile) and refuses an adapter file whose bytes are not the
template's. Re-running it changes nothing.

Specimen-agnostic: every application value comes from the evidence (the
structural model, decisions.yaml, the recorded diff). Framework facts (Spring's
@CrossOrigin defaults and mapping annotations) are the only constants.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent / "skills" / "migration" / "restore-source-response-shape"
TEMPLATE_DIR = SKILL_DIR / "templates"
APP_PROPERTIES = "src/main/resources/application.properties"
STRUCTURE = Path("evidence") / "structure" / "structure.json"
RECEIPT_DIR = Path("evidence") / "response-adapters"
ADAPTER_PACKAGE = "io.rhoai3.migration.response"

CORS = "cors"
MEDIA_TYPE = "media-type"
KINDS = (CORS, MEDIA_TYPE)

_SPRING_DOCS = "https://docs.spring.io/spring-framework/docs/5.3.x/javadoc-api/org/springframework/web/bind/annotation/CrossOrigin.html"
_QUARKUS_CORS = "https://quarkus.io/version/3.27/guides/security-cors"
_QUARKUS_FILTERS = "https://quarkus.io/version/3.27/guides/http-reference#filters"

CONTRACTS: dict[str, dict[str, Any]] = {
    CORS: {
        "contract": "source-cors-response-adapter/v1",
        "simple": "SourceCorsResponseAdapter",
        "prefix": "rhoai3.source-cors.",
        "families": ("quarkus.http.cors", "rhoai3.source-cors."),
        "block": "rhoai3:source-cors",
        "rule_id": "PARITY_CORS",
        "source": "%s (the platform answers a preflight in its CORS route filter before any endpoint: %s)"
                  % (_QUARKUS_FILTERS, _QUARKUS_CORS),
    },
    MEDIA_TYPE: {
        "contract": "source-media-type-parameter-adapter/v1",
        "simple": "SourceMediaTypeParameterAdapter",
        "prefix": "rhoai3.source-media-type.",
        "families": ("rhoai3.source-media-type.",),
        "block": "rhoai3:source-media-type",
        "rule_id": "PARITY_CONTENT_TYPE",
        "source": _QUARKUS_FILTERS,
    },
}


# Earlier bytes of a harness template, by digest. An installed file carrying
# one of these is the harness's own earlier release and may be upgraded in
# place (recorded in the receipt); any other content is still a conflict.
PRIOR_TEMPLATES: dict[str, dict[str, str]] = {
    CORS: {"4d381666e6f3f87a892ca93c7c6bd8bb85f672db157356c44b4486ff81f3ba05":
           "source-cors-response-adapter/v1 as first installed (before ADR-020 same-origin routing)"},
    MEDIA_TYPE: {},
}


class Refuse(Exception):
    """A typed reason the capability will not render or install."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__("%s: %s" % (code, message))
        self.code = code


# ---------------------------------------------------------------------------
# the naming contract
# ---------------------------------------------------------------------------

def adapter_type(kind: str) -> str:
    return "%s.%s" % (ADAPTER_PACKAGE, CONTRACTS[kind]["simple"])


def adapter_path(kind: str) -> str:
    return "src/main/java/%s/%s.java" % (ADAPTER_PACKAGE.replace(".", "/"), CONTRACTS[kind]["simple"])


def template_file(kind: str) -> Path:
    return TEMPLATE_DIR / ("%s.java.template" % CONTRACTS[kind]["simple"])


def template_bytes(kind: str) -> bytes:
    return template_file(kind).read_bytes()


def template_sha256(kind: str) -> str:
    return hashlib.sha256(template_bytes(kind)).hexdigest()


def contract(kind: str) -> dict[str, Any]:
    """The row an obligation carries: WHICH file, WHICH type, under WHICH
    contract, with WHICH bytes. The worker chooses none of them."""
    c = CONTRACTS[kind]
    return {"kind": kind, "contract": c["contract"], "type": adapter_type(kind), "path": adapter_path(kind),
            "template": template_file(kind).relative_to(HERE.parent).as_posix(),
            "template_sha256": template_sha256(kind), "config": APP_PROPERTIES,
            "families": list(c["families"]), "source": c["source"],
            "install": "python3 .hermes/skills/migration/restore-source-response-shape/scripts/"
                       "install-response-adapter.py --root . --adapter %s" % kind}


# The responses the CORS repair PRODUCES for CORS reasons, and nothing else
# (H6a). A cross-origin ACTUAL request's status is the adapter's obligation
# only when it is one of these -- the adapter's own refusal (the template's
# reject(): 403 with REJECTED_BODY, the source's shape) or the platform CORS
# filter's refusal (403, the security-cors guide). Any other status on an
# actual request is the operation's answer and routes as it would without an
# Origin header. Listed here, beside the template, so the planner carries no
# status literal of its own; install-response-adapter.test.py proves the
# template still writes exactly these.
CORS_REJECTIONS: tuple[dict[str, Any], ...] = (
    {"status": 403, "body": "Invalid CORS request", "by": "the adapter's reject(): an origin, method or header the SOURCE policy refuses"},
    {"status": 403, "body": "", "by": "the platform's CORS filter (quarkus.http.cors): an origin or method its configuration refuses (%s)" % _QUARKUS_CORS},
)


def cors_rejection(status: Any, body_sample: str = "") -> str:
    """Why an observed (status, body) is a CORS-typed refusal -- the ``by`` of
    the matching known response -- or "" when it is none of them. A row with
    a body matches only that body; a row without one matches its status."""
    try:
        code = int(str(status).strip())
    except (TypeError, ValueError):
        return ""
    sample = str(body_sample or "").strip()
    for row in CORS_REJECTIONS:
        if row["status"] != code:
            continue
        if row["body"] and sample != row["body"]:
            continue
        return str(row["by"])
    return ""


def kind_of_path(rel: str) -> str:
    for k in KINDS:
        if adapter_path(k) == rel:
            return k
    return ""


# ---------------------------------------------------------------------------
# the SOURCE CORS policy, from M1's structural model
# ---------------------------------------------------------------------------

_CROSS_ORIGIN = "org.springframework.web.bind.annotation.CrossOrigin"
_MAPPINGS = {
    "org.springframework.web.bind.annotation.RequestMapping": "",
    "org.springframework.web.bind.annotation.GetMapping": "GET",
    "org.springframework.web.bind.annotation.PostMapping": "POST",
    "org.springframework.web.bind.annotation.PutMapping": "PUT",
    "org.springframework.web.bind.annotation.DeleteMapping": "DELETE",
    "org.springframework.web.bind.annotation.PatchMapping": "PATCH",
}
_CORS_CONFIG_API = ("org.springframework.web.cors.", "org.springframework.web.servlet.config.annotation.CorsRegistry",
                    "org.springframework.web.servlet.config.annotation.CorsRegistration")
_WEB_SECURITY = ("org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter",)
_HTTP_SECURITY = "org.springframework.security.config.annotation.web.builders.HttpSecurity"
_REJECTS_ANONYMOUS = ("authenticated", "fullyAuthenticated", "hasRole", "hasAnyRole", "hasAuthority",
                      "hasAnyAuthority", "denyAll", "hasIpAddress", "access")
_CONDITIONAL = "org.springframework.boot.autoconfigure.condition.ConditionalOnProperty"
# @CrossOrigin's documented defaults (Spring Framework 5.3): any origin, any
# header, the handler's own methods, 1800 seconds, and no credentials header.
DEFAULT_MAX_AGE = "1800"


def _ann(anns: Any, fqn: str) -> dict[str, Any] | None:
    for a in anns or []:
        if isinstance(a, dict) and str(a.get("fqn") or a.get("name") or "") == fqn:
            return a
    return None


def _values(ann: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ann, dict):
        return {}
    v = ann.get("values") if ann.get("values") is not None else ann.get("attributes")
    return v if isinstance(v, dict) else {}


def _strings(values: dict[str, Any], *keys: str) -> list[str]:
    out: list[str] = []
    for k in keys:
        raw = values.get(k)
        for item in (raw if isinstance(raw, list) else [raw] if raw not in (None, "") else []):
            out.append(str(item))
    return out


def _tokens(values: list[str]) -> list[str]:
    out: list[str] = []
    for v in values:
        for t in str(v).split(","):
            t = t.strip()
            if t and t not in out:
                out.append(t)
    return out


def _method_name(raw: str) -> str:
    return str(raw).rsplit(".", 1)[-1].strip().upper()


def _join(prefix: str, path: str) -> str:
    """Spring's pattern combination for the plain cases a mapping uses."""
    a, b = str(prefix or ""), str(path or "")
    if not a:
        joined = b
    elif not b:
        joined = a
    else:
        joined = a.rstrip("/") + "/" + b.lstrip("/")
    joined = "/" + joined.lstrip("/") if joined else "/"
    while "//" in joined:
        joined = joined.replace("//", "/")
    return joined


def _combine(base: list[str] | None, other: list[str] | None) -> list[str] | None:
    if not other:
        return base
    if not base:
        return other
    return list(dict.fromkeys(list(base) + list(other)))


def _effective(class_values: dict[str, Any] | None, method_values: dict[str, Any] | None) -> dict[str, Any]:
    """One handler's CORS configuration: class-level combined with method-level
    (lists united, scalars overridden by the method), then the defaults."""
    def lists(v: dict[str, Any] | None) -> dict[str, list[str] | None]:
        if v is None:
            return {"origins": None, "patterns": None, "headers": None, "exposed": None, "methods": None}
        return {"origins": _tokens(_strings(v, "origins", "value")) or None,
                "patterns": _tokens(_strings(v, "originPatterns")) or None,
                "headers": _tokens(_strings(v, "allowedHeaders")) or None,
                "exposed": _strings(v, "exposedHeaders") or None,
                "methods": [_method_name(m) for m in _strings(v, "methods")] or None}
    c, m = lists(class_values), lists(method_values)
    eff = {k: _combine(c[k], m[k]) for k in c}
    creds = ""
    age = ""
    for v in (class_values, method_values):
        if v is None:
            continue
        s = _strings(v, "allowCredentials")
        if s and str(s[0]).strip():
            creds = str(s[0]).strip().lower()
        a = _strings(v, "maxAge")
        if a and str(a[0]).strip() and not str(a[0]).strip().startswith("-"):
            age = str(a[0]).strip()
    origins = eff["origins"] or ([] if eff["patterns"] else ["*"])
    return {
        "origins": list(origins),
        "origin_patterns": list(eff["patterns"] or []),
        "headers": list(eff["headers"] or ["*"]),
        "exposed_headers": ", ".join(eff["exposed"]) if eff["exposed"] else "",
        "methods": list(eff["methods"]) if eff["methods"] else None,
        "max_age": age or DEFAULT_MAX_AGE,
        "allow_credentials": creds == "true",
    }


def _policy_id(values: dict[str, Any]) -> str:
    # the id capture-source-oracles gives the same annotation (source_cors_policy_map)
    from planner.canonical import canonical_bytes, sha256_bytes  # noqa: PLC0415

    return "crossorigin:%s" % sha256_bytes(canonical_bytes(values))[:12]


def _mappings_of(t: dict[str, Any]) -> list[tuple[dict[str, Any], list[str], list[str]]]:
    """(method row, HTTP methods, full path patterns) for each handler of a type."""
    class_map = None
    for fqn in _MAPPINGS:
        class_map = class_map or _ann(t.get("annotations"), fqn)
    prefixes = _strings(_values(class_map), "value", "path") or [""]
    out = []
    for m in t.get("methods") or []:
        if not isinstance(m, dict):
            continue
        for fqn, verb in _MAPPINGS.items():
            ann = _ann(m.get("annotations"), fqn)
            if ann is None:
                continue
            vals = _values(ann)
            verbs = [verb] if verb else [_method_name(x) for x in _strings(vals, "method")]
            paths = _strings(vals, "value", "path") or [""]
            patterns = sorted({_join(p, q) for p in prefixes for q in paths})
            out.append((m, sorted(set(verbs)), patterns))
            break
    return out


def _security(types: list[dict[str, Any]]) -> dict[str, Any]:
    """What the source's security configuration says about CORS ordering.

    A Spring Security configuration that does not call ``cors()`` runs BEFORE
    Spring MVC's CORS processing: its 401 carries no CORS header, and a
    preflight is authenticated like any request. When the configuration that
    rejects anonymous requests is conditional on a property, a preflight is
    authenticated only while that property has that value."""
    configs = []
    for t in types:
        sup = [str(s) for s in (t.get("supertypes") or [])]
        calls = [c for m in (t.get("methods") or []) if isinstance(m, dict) for c in (m.get("calls") or []) if isinstance(c, dict)]
        http = [c for c in calls if str(c.get("owner") or "") == _HTTP_SECURITY]
        if not (any(s in _WEB_SECURITY for s in sup) or http):
            continue
        names = {str(c.get("name") or "") for c in calls if str(c.get("owner") or "").startswith("org.springframework.security.")}
        cond = _values(_ann(t.get("annotations"), _CONDITIONAL))
        key = (_strings(cond, "name", "value") or [""])[0]
        prefix = (_strings(cond, "prefix") or [""])[0]
        if key and prefix:
            key = prefix.rstrip(".") + "." + key
        value = (_strings(cond, "havingValue") or [""])[0]
        configs.append({"type": str(t.get("fqn") or ""), "cors": "cors" in {str(c.get("name")) for c in http},
                        "rejects_anonymous": bool(names & set(_REJECTS_ANONYMOUS)),
                        "condition": ("%s=%s" % (key, value or "true")) if key else ""})
    precedes = any(not c["cors"] for c in configs)
    gating = sorted({c["condition"] or "always" for c in configs if c["rejects_anonymous"] and not c["cors"]})
    if len(gating) > 1 and "always" in gating:
        gating = ["always"]
    return {"configs": sorted(configs, key=lambda c: c["type"]), "precedes_cors": precedes,
            "preflight_authenticated_when": gating}


def cors_policy(root: Path) -> dict[str, Any]:
    """The source CORS policy, rendered from M1's structural model.

    Refuses (typed) rather than guesses: a model that is not there, a source
    that configures CORS through Spring's configuration API (its routes and
    values are not annotations), a policy that covers no handler, or security
    configurations gating anonymous access on more than one condition."""
    p = Path(root) / STRUCTURE
    if not p.is_file():
        raise Refuse("CORS_POLICY_UNKNOWN", "M1's structural model %s is not in this tree" % STRUCTURE)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refuse("CORS_POLICY_UNKNOWN", "%s could not be read: %s" % (STRUCTURE, exc))
    types = [t for t in (doc.get("types") or []) if isinstance(t, dict)]
    globals_ = sorted(str(t.get("fqn") or "") for t in types
                      if any(str(r).startswith(_CORS_CONFIG_API) for r in list(t.get("type_refs") or []) + list(t.get("supertypes") or [])))
    if globals_:
        raise Refuse("CORS_POLICY_UNRENDERABLE",
                     "the source configures CORS through Spring's configuration API in %s; its routes and values are "
                     "not annotations in the structural model, and this capability does not guess them" % ", ".join(globals_))
    groups: dict[str, dict[str, Any]] = {}
    policies: set[str] = set()
    for t in types:
        class_co = _ann(t.get("annotations"), _CROSS_ORIGIN)
        if class_co is not None:
            policies.add(_policy_id(_values(class_co)))
        for m, verbs, patterns in _mappings_of(t):
            method_co = _ann(m.get("annotations"), _CROSS_ORIGIN)
            if method_co is not None:
                policies.add(_policy_id(_values(method_co)))
            if class_co is None and method_co is None:
                continue
            eff = _effective(_values(class_co) if class_co is not None else None,
                             _values(method_co) if method_co is not None else None)
            if method_co is None:
                pid = _policy_id(_values(class_co))
            elif class_co is None:
                pid = _policy_id(_values(method_co))
            else:
                pid = "combined:%s" % hashlib.sha256(json.dumps(eff, sort_keys=True).encode("utf-8")).hexdigest()[:12]
            key = json.dumps(eff, sort_keys=True)
            g = groups.setdefault(key, dict(eff, policies=set(), mappings=set(), types=set()))
            g["policies"].add(pid)
            g["types"].add(str(t.get("fqn") or ""))
            for pat in patterns:
                g["mappings"].add(("|".join(verbs) if verbs else "*", pat))
    if not groups:
        raise Refuse("CORS_POLICY_EMPTY", "the structural model carries no @CrossOrigin that covers a request mapping")
    sec = _security(types)
    if len(sec["preflight_authenticated_when"]) > 1:
        raise Refuse("CORS_POLICY_UNRENDERABLE", "anonymous access is refused under more than one condition (%s)"
                     % ", ".join(sec["preflight_authenticated_when"]))
    rules = []
    for key in sorted(groups, key=lambda k: (sorted(groups[k]["policies"]), k)):
        g = groups[key]
        rules.append({"policies": sorted(g["policies"]), "types": sorted(g["types"]),
                      "origins": g["origins"], "origin_patterns": g["origin_patterns"], "methods": g["methods"],
                      "headers": g["headers"], "exposed_headers": g["exposed_headers"], "max_age": g["max_age"],
                      "allow_credentials": g["allow_credentials"],
                      "mappings": ["%s %s" % (v, pat) for v, pat in sorted(g["mappings"], key=lambda x: (x[1], x[0]))]})
    return {"schema": "rhoai3.source-cors-policy/v1", "structure": STRUCTURE.as_posix(),
            "source_policies": sorted(policies), "rules": rules, "security": sec,
            "links": [_SPRING_DOCS, _QUARKUS_CORS]}


def _allowed_methods(rule: dict[str, Any]) -> list[str]:
    if rule.get("methods"):
        return list(rule["methods"])
    out: list[str] = []
    for m in rule.get("mappings") or []:
        verbs = str(m).split(" ", 1)[0]
        out.extend(["GET", "HEAD", "POST"] if verbs == "*" else verbs.split("|"))
    return out


def cors_properties(policy: dict[str, Any]) -> list[tuple[str, str]]:
    """The explicit rows: the platform's enforcement (origins it may grant,
    methods, headers, exposure), then the adapter's per-handler policy. The
    platform rows are the UNION of what the source policies grant, so the
    platform never grants more than the source did anywhere; the adapter
    narrows each response to its own handler's policy."""
    rules = policy["rules"]
    rows: list[tuple[str, str]] = [("quarkus.http.cors.enabled", "true")]
    if any("*" in r["origins"] for r in rules):
        origins = ["*"]
    else:
        origins = sorted({o for r in rules for o in r["origins"]})
        for r in rules:
            for pat in r["origin_patterns"]:
                rx = "/" + ".*".join(_re_escape(part) for part in pat.split("*")) + "/"
                if rx not in origins:
                    origins.append(rx)
    rows.append(("quarkus.http.cors.origins", ",".join(origins)))
    methods = sorted({m for r in rules for m in _allowed_methods(r)} - {"*"})
    if any("*" in (r.get("methods") or []) for r in rules):
        methods = []
    if methods:
        rows.append(("quarkus.http.cors.methods", ",".join(methods)))
    headers = ["*"] if any("*" in r["headers"] for r in rules) else sorted({h for r in rules for h in r["headers"]}, key=str.lower)
    rows.append(("quarkus.http.cors.headers", ",".join(headers)))
    exposed = sorted({t for r in rules for t in _tokens([r["exposed_headers"]])}, key=str.lower)
    if exposed:
        rows.append(("quarkus.http.cors.exposed-headers", ",".join(exposed)))
    ages = {r["max_age"] for r in rules}
    if len(ages) == 1:
        rows.append(("quarkus.http.cors.access-control-max-age", ages.pop()))
    creds = all(r["allow_credentials"] for r in rules)
    rows.append(("quarkus.http.cors.access-control-allow-credentials", "true" if creds else "false"))
    pre = CONTRACTS[CORS]["prefix"]
    sec = policy.get("security") or {}
    if sec.get("precedes_cors"):
        rows.append((pre + "security-precedes-cors", "true"))
        rows.append((pre + "security-rejections-bare", "true"))
    when = list(sec.get("preflight_authenticated_when") or [])
    if when:
        rows.append((pre + "preflight-authenticated-when", when[0]))
    rows.append((pre + "rule-count", str(len(rules))))
    for i, r in enumerate(rules):
        rp = "%srule.%d." % (pre, i)
        if r["origins"]:
            rows.append((rp + "origins", ",".join(r["origins"])))
        if r["origin_patterns"]:
            rows.append((rp + "origin-patterns", ",".join(r["origin_patterns"])))
        if r["methods"]:
            rows.append((rp + "methods", ",".join(r["methods"])))
        rows.append((rp + "headers", ",".join(r["headers"])))
        if r["exposed_headers"]:
            rows.append((rp + "exposed-headers", r["exposed_headers"]))
        rows.append((rp + "max-age", r["max_age"]))
        if r["allow_credentials"]:
            rows.append((rp + "allow-credentials", "true"))
        rows.append((rp + "mapping-count", str(len(r["mappings"]))))
        for j, m in enumerate(r["mappings"]):
            rows.append(("%smapping.%d" % (rp, j), m))
    return rows


def _re_escape(s: str) -> str:
    out = []
    for ch in s:
        out.append("\\" + ch if ch in ".^$+?()[]{}|\\" else ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# the Content-Type representation decision, from the recorded difference
# ---------------------------------------------------------------------------

def _media(value: str) -> tuple[str, list[tuple[str, str]]]:
    parts = [p.strip() for p in str(value or "").split(";")]
    base = parts[0].lower() if parts else ""
    params = []
    for p in parts[1:]:
        if not p:
            continue
        name, _, v = p.partition("=")
        params.append((name.strip().lower(), v.strip().strip('"')))
    return base, params


def media_type_difference(have: str, want: str) -> dict[str, Any] | None:
    """A Content-Type difference that is a PARAMETER difference on the same
    media type, or None. ``extra`` is what the destination adds and the
    source never sent -- the only thing the adapter may remove."""
    hb, hp = _media(have)
    wb, wp = _media(want)
    if not hb or not wb or hb != wb or hp == wp:
        return None
    extra = [p for p in hp if p not in wp]
    missing = [p for p in wp if p not in hp]
    return {"media_type": hb, "extra": extra, "missing": missing}


def media_type_decision(differences: list[dict[str, Any]]) -> dict[str, Any]:
    """The ONE parameter to remove, decided from the recorded differences:
    every difference must add the same (name, value) and remove nothing.
    Anything else is not decidable here and is refused by name."""
    if not differences:
        raise Refuse("MEDIA_TYPE_UNDECIDED", "no recorded Content-Type difference")
    params = {tuple(p) for d in differences for p in d.get("extra") or []}
    missing = [d for d in differences if d.get("missing")]
    if missing:
        raise Refuse("MEDIA_TYPE_UNDECIDED", "the source sent a parameter the destination does not (%s); removing a "
                     "parameter cannot restore one" % missing[0]["missing"])
    if len(params) != 1 or any(len(d.get("extra") or []) != 1 for d in differences):
        raise Refuse("MEDIA_TYPE_UNDECIDED", "the differences do not add exactly one common parameter: %s"
                     % sorted(params))
    name, value = next(iter(params))
    if not value:
        raise Refuse("MEDIA_TYPE_UNDECIDED", "the added parameter %r carries no value to match" % name)
    return {"parameter": name, "value": value, "media_types": sorted({d["media_type"] for d in differences})}


def media_type_properties(decision: dict[str, Any]) -> list[tuple[str, str]]:
    pre = CONTRACTS[MEDIA_TYPE]["prefix"]
    return [(pre + "parameter", decision["parameter"]), (pre + "parameter-value", decision["value"]),
            (pre + "media-types", ",".join(decision["media_types"]))]


# ---------------------------------------------------------------------------
# properties, as properties
# ---------------------------------------------------------------------------

def _escape(value: str) -> str:
    v = str(value).replace("\\", "\\\\")
    return ("\\" + v) if v.startswith(" ") else v


def _logical_lines(text: str) -> list[tuple[int, int, str]]:
    """(first line index, last line index, logical line) with continuations joined."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        start = i
        buf = lines[i]
        while _continues(buf) and i + 1 < len(lines):
            buf = buf[:-1] + lines[i + 1].lstrip()
            i += 1
        out.append((start, i, buf))
        i += 1
    return out


def _continues(line: str) -> bool:
    n = len(line) - len(line.rstrip("\\"))
    return n % 2 == 1


def _split_row(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s[0] in "#!":
        return None
    key = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            key.append(s[i + 1])
            i += 2
            continue
        if ch in "=: \t":
            break
        key.append(ch)
        i += 1
    rest = s[i:].lstrip(" \t")
    if rest[:1] in ("=", ":"):
        rest = rest[1:].lstrip(" \t")
    value = []
    j = 0
    while j < len(rest):
        if rest[j] == "\\" and j + 1 < len(rest):
            value.append(rest[j + 1])
            j += 2
            continue
        value.append(rest[j])
        j += 1
    return "".join(key), "".join(value)


def read_properties(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for _a, _b, line in _logical_lines(text):
        row = _split_row(line)
        if row:
            out[row[0]] = row[1]
    return out


def _owned(key: str, families: tuple[str, ...] | list[str]) -> bool:
    return any(key == f.rstrip(".") or key.startswith(f if f.endswith(".") else f + ".") or key == f for f in families)


def render_block(kind: str, rows: list[tuple[str, str]]) -> str:
    c = CONTRACTS[kind]
    lines = ["# %s:begin -- harness capability %s (ADR-019), installed by restore-source-response-shape."
             % (c["block"], c["contract"]),
             "# Every value below is rendered from the evidence; do not edit by hand, re-run the installer."]
    lines += ["%s=%s" % (k, _escape(v)) for k, v in rows]
    lines.append("# %s:end" % c["block"])
    return "\n".join(lines) + "\n"


def plan_properties(text: str, kind: str, rows: list[tuple[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """(the new file text, the rows it replaced). Refuses a profile-scoped row
    of the capability's own family: it would override the rendered value in
    that profile, silently."""
    c = CONTRACTS[kind]
    fams = c["families"]
    begin, end = "# %s:begin" % c["block"], "# %s:end" % c["block"]
    lines = text.split("\n")
    kept: list[str] = []
    inside = False
    anchor = -1
    for ln in lines:
        s = ln.strip()
        if s.startswith(begin):
            inside = True
            if anchor < 0:
                anchor = len(kept)
                kept.append(_ANCHOR)
            continue
        if inside:
            if s.startswith(end):
                inside = False
            continue
        kept.append(ln)
    if inside:
        raise Refuse("CONFIG_BLOCK_UNBALANCED", "%s has a %s marker without its end marker" % (APP_PROPERTIES, begin))
    replaced: list[dict[str, str]] = []
    profiled: list[str] = []
    drop: set[int] = set()
    for a, b, line in _logical_lines("\n".join(kept)):
        row = _split_row(line)
        if not row:
            continue
        key, value = row
        bare = key.split(".", 1)[1] if key.startswith("%") and "." in key else key
        if not _owned(bare, fams):
            continue
        if key.startswith("%"):
            profiled.append(key)
            continue
        replaced.append({"key": key, "value": value})
        drop.update(range(a, b + 1))
    if profiled:
        raise Refuse("CONFIG_PROFILE_CONFLICT", "%s carries profile-scoped row(s) of this capability's own family (%s); "
                     "each would override the rendered value in its profile" % (APP_PROPERTIES, ", ".join(sorted(profiled))))
    block = render_block(kind, rows)
    body = "\n".join(ln for i, ln in enumerate(kept) if i not in drop)
    if anchor >= 0:
        # an installed block is replaced where it stands, so re-running one
        # capability never reorders the file around another's block
        return body.replace(_ANCHOR + "\n", block, 1).replace(_ANCHOR, block.rstrip("\n"), 1), replaced
    body = body.rstrip("\n")
    new = (body + "\n\n" if body else "") + block
    return new, replaced


_ANCHOR = "\x00rhoai3-block-anchor\x00"


def missing_properties(text: str, rows: list[tuple[str, str]], kind: str) -> list[str]:
    """What the file does not say that the rendering requires, including an
    owned row the rendering does not carry (a stale or hand-added permission)."""
    have = read_properties(text)
    out = ["%s=%s (have %s)" % (k, v, have.get(k, "<absent>")) for k, v in rows if have.get(k) != v]
    want = {k for k, _v in rows}
    fams = CONTRACTS[kind]["families"]
    for k in sorted(have):
        bare = k.split(".", 1)[1] if k.startswith("%") and "." in k else k
        if _owned(bare, fams) and k not in want:
            out.append("%s is set and the rendering does not carry it" % k)
    return out


# ---------------------------------------------------------------------------
# install / verify
# ---------------------------------------------------------------------------

def rows_for(root: Path, kind: str, decision: dict[str, Any] | None = None) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    if kind == CORS:
        policy = cors_policy(root)
        return cors_properties(policy), policy
    if not decision:
        raise Refuse("MEDIA_TYPE_UNDECIDED", "no decided parameter was supplied")
    return media_type_properties(decision), decision


def install(root: Path, kind: str, rows: list[tuple[str, str]], *, basis: dict[str, Any], authority: dict[str, Any],
            write: bool = True) -> dict[str, Any]:
    """Install the adapter file and its rows. Only absent-or-identical adapter
    bytes are accepted; the rows replace only the capability's own family."""
    root = Path(root)
    target = root / adapter_path(kind)
    want = template_bytes(kind)
    before_file = target.read_bytes() if target.is_file() else None
    upgraded_from = ""
    if before_file is not None and before_file != want:
        prior = hashlib.sha256(before_file).hexdigest()
        if prior in PRIOR_TEMPLATES.get(kind, {}):
            upgraded_from = prior
            before_file = None  # the harness's own earlier bytes: replaced, on the record
    if before_file is not None and before_file != want:
        raise Refuse("ADAPTER_CONFLICT", "%s exists with other content (sha256 %s, template %s); the naming contract "
                     "reserves this path for the harness template" % (adapter_path(kind),
                                                                       hashlib.sha256(before_file).hexdigest()[:12],
                                                                       template_sha256(kind)[:12]))
    props = root / APP_PROPERTIES
    if not props.is_file():
        raise Refuse("CONFIG_MISSING", "%s is not in this tree" % APP_PROPERTIES)
    text = props.read_text(encoding="utf-8")
    new, replaced = plan_properties(text, kind, rows)
    changed = []
    if before_file is None:
        changed.append(adapter_path(kind))
    if new != text:
        changed.append(APP_PROPERTIES)
    receipt = {
        "schema": "rhoai3.response-adapter-receipt/v1",
        "adapter": contract(kind),
        "authority": authority,
        "basis": basis,
        "properties": [{"key": k, "value": v} for k, v in rows],
        "replaced": replaced,
        "changed": changed,
        "config_sha256_before": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "config_sha256_after": hashlib.sha256(new.encode("utf-8")).hexdigest(),
        "adapter_sha256": hashlib.sha256(want).hexdigest(),
    }
    if upgraded_from:
        receipt["upgraded_from"] = {"sha256": upgraded_from, "release": PRIOR_TEMPLATES[kind][upgraded_from]}
    if write:
        if before_file is None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(want)
        if new != text:
            props.write_text(new, encoding="utf-8")
        out = root / RECEIPT_DIR / ("%s.json" % kind)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def verify(root: Path, kind: str, rows: list[tuple[str, str]]) -> list[str]:
    """Problems with an installation, [] when it is exactly the rendering."""
    root = Path(root)
    problems = []
    target = root / adapter_path(kind)
    if not target.is_file():
        problems.append("%s does not exist" % adapter_path(kind))
    elif target.read_bytes() != template_bytes(kind):
        problems.append("%s is not the %s template (sha256 %s)" % (adapter_path(kind), CONTRACTS[kind]["contract"],
                                                                   hashlib.sha256(target.read_bytes()).hexdigest()[:12]))
    props = root / APP_PROPERTIES
    if not props.is_file():
        problems.append("%s does not exist" % APP_PROPERTIES)
    else:
        problems.extend(missing_properties(props.read_text(encoding="utf-8"), rows, kind))
    return problems
