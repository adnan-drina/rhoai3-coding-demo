#!/usr/bin/env python3
"""M1 producer: derive the scenario corpus from the frozen source's own evidence.

The corpus used to be hand-written and called "Operator-approved intent", with
a signature (``approved_by``) standing in for provenance. A signature is a
human sign-off by another name, and the project rule is autonomous by design:
verification gates and an audit trail, never a person vouching. The review of
the v8/v9 five-scenario packet (2026-09-14) showed that nothing in it was
invented: every request was readable off evidence the harness already holds.
The concrete URLs come from the evidence bundle's entry points, the bodies
from the OpenAPI document's own ``example`` values, the identifiers from the
seed data the source loads, and the cross-origin exchanges from the
``@CrossOrigin`` policies in M1's structure model. So the corpus is a PRODUCER
OUTPUT: derived here, bound by digest to the evidence bundle in the receipt
beside it (``verification/scenarios/_derive.json``), and refused by the loader
the moment it is edited by hand. The human review of what was captured becomes
a fail-closed gate (qualify-source-captures.py).

What cannot be derived is recorded as a gap, never invented: a required
property with no example, a path variable that no seed row supplies, an entry
point with no HTTP method. A gap is a scenario that does not exist, and the
parity receipt says so for its entry point.

Every scenario names which inputs produced it (``derived_from``) and what a
capture of it has to show (``qualify``). Nothing here records an expected
value: those come only from capturing the source.

``--security-mode enabled`` derives the OTHER corpus ADR-014 requires
(``verification/scenarios-enabled/corpus.json``): per authorization policy the
frozen source states, the same request answered for an identity the policy
accepts, for nobody, for an invalid credential and for an authenticated
identity that lacks the role. The requests are not derived again -- they are
REUSED from the disabled corpus, bound by scenario id and body digest, so the
two modes send the same bytes and any difference in the answer is the security
switch. The one exception is a policy on a plain READ, which that corpus
carries no scenario for at all: there the read is derived here, from the entry
point's own method and route and the path values the disabled corpus already
resolved, and a route no value resolves keeps its gap. Identities come from
``decisions.yaml``'s ``security`` section by credential REFERENCE
(``--from-decisions``, the default for this mode; ``--identity NAME=REF``
states them on the command line instead); the harness never reads a password.
A role the seed settles is read from the seed, and a policy expression outside
the supported grammar, like an identity nobody declared, is a typed gap with
no scenarios. With no declared section nothing is derived and the receipt
records the reason (``status: idle``), which is ADR-014's blocker rather than
a corpus derived as though the source had no security.

Exit 0 when a corpus was derived (gaps allowed and recorded), 1 when it refuses
(no bundle, no frozen source, no OpenAPI document, or a hand-authored corpus
already at the output path), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _oracle_common import ensure_hermes_lib  # noqa: E402
import _variant_revert  # noqa: E402
from _scenarios import (CHALLENGE_HEADER, CORPUS, DEFAULT_SECURITY_MODE, DERIVATION_SCHEMA, DERIVE_RECEIPT,  # noqa: E402
                        EFFECT_ROLE_UNCHANGED, FROZEN_SOURCE_MODEL, SCENARIO_BROWSER_PREFLIGHT,
                        SCENARIO_CORS_ACTUAL, SCENARIO_DIAGNOSTIC_PROBE, VARIANT_DERIVATION, normalized_identity, ROLE_PREFIX, SCHEMA, SECURITY_MODES, CorpusError, authorization_roles,
                        corpus_digest, corpus_path, derive_receipt_path, load_corpus, merge_role_constants,
                        normalize_security_mode, normalize_variant, parse_assignments, request_of,
                        resolve_role_constant,
                        role_constants_from_model, role_matches, role_reference_tokens,
                        source_authorization_policy_map, source_cors_policy_map, source_role_constants)

ensure_hermes_lib()
from planner import yamlite  # noqa: E402
from planner.canonical import digest, load_json, sha256_file, write_canonical  # noqa: E402
from planner.decisions import (DecisionsError, REQUEST_POLICY_AUTHENTICATED, SECURITY_SECTION,  # noqa: E402
                               load_decisions, security, security_gaps)
from planner.dest_model import DestModelUnavailable, tree_model  # noqa: E402
from planner.paths import DECISIONS, EVIDENCE_BUNDLE, STRUCTURE, producer_receipt  # noqa: E402

PRODUCER = "derive-source-scenarios.py"
BODIES = Path("verification") / "scenarios" / "bodies"
RESOURCES = Path("src") / "main" / "resources"
DEFAULT_ENGINE = "hsqldb"
RESET_TEXT = (".hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root . restores the destination "
              "instance; the frozen source restores the same dataset by restarting when its baseline engine is in-memory")
# characters tried, in order, to build a value a ``pattern`` forbids
FORBIDDEN_CANDIDATES = ("!", "#", "-", " ", "a", "1", "~", "%", "@")
# how many of a cascading delete's referencing rows are read back afterwards:
# the effect proves the children went with the parent, and proving it over
# three rows is the same proof as over thirty at a fraction of the capture
_CASCADE_CHILD_CAP = 3


class Refusal(Exception):
    pass


# --------------------------------------------------------------------------
# A YAML subset loader for OpenAPI documents. PyYAML is not on the workspace
# (python 3.9) and planner.yamlite refuses what every OpenAPI document has:
# ``$ref`` keys, ``{var}`` path keys and block scalars. This parses block
# mappings and sequences, quoted/plain scalars with continuation lines, block
# scalars (``|``/``>``), empty flow collections and flow sequences of scalars.
# Anything else raises, so the document is refused rather than misread.
# --------------------------------------------------------------------------
class YamlError(ValueError):
    pass


_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+(?:[eE][-+]?\d+)?$")
_BLOCK_INDICATOR_RE = re.compile(r"^[|>][-+]?\d?$")


def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote = ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'" and (not out or not out[-1].strip() or out[-1] in "[,{:"):
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1].isspace()):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_key(text: str) -> tuple[str, str] | None:
    """('key', 'rest') when ``text`` is a mapping entry, else None. The key is
    everything before the first ``:`` that ends the line or is followed by a
    space and is not inside quotes; ``http://`` in a value is not a key."""
    if not text or text[0] in "[{":
        return None
    if text[0] in "\"'":
        q = text[0]
        j = text.find(q, 1)
        while j != -1 and q == "'" and text[j + 1:j + 2] == "'":
            j = text.find(q, j + 2)
        if j == -1:
            return None
        rest = text[j + 1:].lstrip()
        if not rest.startswith(":") or (len(rest) > 1 and not rest[1].isspace()):
            return None
        key = text[1:j].replace("''", "'") if q == "'" else text[1:j]
        return key, rest[1:].strip()
    for i, ch in enumerate(text):
        if ch == ":" and (i + 1 == len(text) or text[i + 1].isspace()):
            return text[:i].strip(), text[i + 1:].strip()
    return None


def _unquote_double(body: str) -> str:
    return (body.replace("\\\\", "\x00").replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
            .replace("\\/", "/").replace("\x00", "\\"))


def _scalar(s: str, line_no: int) -> Any:
    s = s.strip()
    if s in ("", "~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if "{" in inner or "[" in inner:
            raise YamlError("line %d: unsupported flow construct %r" % (line_no, s))
        parts = [p.strip() for p in inner.split(",")] if inner else []
        if any(not p for p in parts):
            raise YamlError("line %d: unsupported flow construct %r" % (line_no, s))
        return [_scalar(p, line_no) for p in parts]
    if s[0] in "[{&*!%@`":
        raise YamlError("line %d: unsupported YAML construct %r" % (line_no, s))
    if len(s) >= 2 and s[0] == s[-1] and s[0] == "'":
        return s[1:-1].replace("''", "'")
    if len(s) >= 2 and s[0] == s[-1] and s[0] == '"':
        return _unquote_double(s[1:-1])
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


class _Yaml:
    def __init__(self, lines: list[str], offset: int = 0) -> None:
        self.lines = lines
        self.offset = offset

    def _no(self, i: int) -> int:
        return i + 1 + self.offset

    def _row(self, i: int) -> tuple[int, str]:
        raw = self.lines[i]
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YamlError("line %d: tabs in indentation" % self._no(i))
        s = _strip_comment(raw)
        return len(s) - len(s.lstrip(" ")), s.strip()

    def _blank(self, i: int) -> bool:
        return not _strip_comment(self.lines[i]).strip()

    def _skip(self, i: int) -> int:
        while i < len(self.lines) and self._blank(i):
            i += 1
        return i

    def parse_block(self, i: int, indent: int) -> tuple[Any, int]:
        i = self._skip(i)
        if i >= len(self.lines):
            return None, i
        ind, text = self._row(i)
        if ind != indent:
            raise YamlError("line %d: unexpected indentation" % self._no(i))
        if text.startswith("- ") or text == "-":
            return self.parse_seq(i, indent)
        return self.parse_map(i, indent)

    def _continuation(self, first: str, i: int, indent: int) -> tuple[str, int]:
        """A plain or quoted scalar may continue on more-indented lines."""
        parts = [first]
        while True:
            j = self._skip(i)
            if j >= len(self.lines):
                break
            ind, text = self._row(j)
            if ind <= indent:
                break
            parts.append(text)
            i = j + 1
        return " ".join(parts), i

    def _block_scalar(self, indicator: str, i: int, indent: int) -> tuple[str, int]:
        keep = indicator.startswith("|")
        chomp = indicator[1:2] if len(indicator) > 1 and indicator[1] in "-+" else ""
        body: list[str] = []
        base: int | None = None
        while i < len(self.lines):
            raw = self.lines[i]
            if not raw.strip():
                body.append("")
                i += 1
                continue
            ind = len(raw) - len(raw.lstrip(" "))
            if ind <= indent:
                break
            if base is None:
                base = ind
            body.append(raw[base:] if ind >= base else raw.lstrip(" "))
            i += 1
        while body and body[-1] == "":
            body.pop()
        text = "\n".join(body) if keep else re.sub(r"(?<!\n)\n(?!\n)", " ", "\n".join(body))
        if chomp != "-":
            text += "\n"
        return text, i

    def parse_map(self, i: int, indent: int) -> tuple[dict[str, Any], int]:
        out: dict[str, Any] = {}
        while True:
            i = self._skip(i)
            if i >= len(self.lines):
                break
            ind, text = self._row(i)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError("line %d: unexpected indentation" % self._no(i))
            if text.startswith("- ") or text == "-":
                raise YamlError("line %d: sequence item inside a mapping" % self._no(i))
            kv = _split_key(text)
            if kv is None:
                raise YamlError("line %d: expected 'key: value'" % self._no(i))
            key, rest = kv
            if key in out:
                raise YamlError("line %d: duplicate key %r" % (self._no(i), key))
            line_no = self._no(i)
            i += 1
            if rest == "":
                j = self._skip(i)
                if j < len(self.lines):
                    ind2, text2 = self._row(j)
                    if ind2 > indent:
                        out[key], i = self.parse_block(j, ind2)
                        continue
                    if ind2 == indent and (text2.startswith("- ") or text2 == "-"):
                        out[key], i = self.parse_seq(j, indent)
                        continue
                out[key] = None
                continue
            if _BLOCK_INDICATOR_RE.match(rest):
                out[key], i = self._block_scalar(rest, i, indent)
                continue
            joined, i = self._continuation(rest, i, indent)
            out[key] = _scalar(joined, line_no)
        return out, i

    def parse_seq(self, i: int, indent: int) -> tuple[list[Any], int]:
        out: list[Any] = []
        while True:
            i = self._skip(i)
            if i >= len(self.lines):
                break
            ind, text = self._row(i)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError("line %d: unexpected indentation" % self._no(i))
            if not (text.startswith("- ") or text == "-"):
                break
            item = text[2:].strip() if text != "-" else ""
            line_no = self._no(i)
            i += 1
            if item == "":
                j = self._skip(i)
                if j < len(self.lines) and self._row(j)[0] > indent:
                    value, i = self.parse_block(j, self._row(j)[0])
                    out.append(value)
                else:
                    out.append(None)
                continue
            kv = _split_key(item)
            if kv is not None:
                # a mapping whose first pair is on the dash line: parse the
                # item as a map whose column is the item's own column
                child_indent = indent + 2
                sub = [" " * child_indent + item]
                k = i
                while k < len(self.lines):
                    if self._blank(k):
                        sub.append(self.lines[k])
                        k += 1
                        continue
                    if self._row(k)[0] >= child_indent:
                        sub.append(self.lines[k])
                        k += 1
                        continue
                    break
                value, _ = _Yaml(sub, line_no - 1).parse_map(0, child_indent)
                out.append(value)
                i = k
                continue
            if _BLOCK_INDICATOR_RE.match(item):
                value, i = self._block_scalar(item, i, indent)
                out.append(value)
                continue
            joined, i = self._continuation(item, i, indent)
            out.append(_scalar(joined, line_no))
        return out, i


def yaml_loads(text: str) -> Any:
    lines = text.splitlines()
    for n, raw in enumerate(lines):
        if raw.strip() == "---":
            if any(_strip_comment(x).strip() for x in lines[:n]):
                raise YamlError("line %d: multi-document streams unsupported" % (n + 1))
            lines[n] = ""
    p = _Yaml(lines)
    i = p._skip(0)
    if i >= len(lines):
        return {}
    value, j = p.parse_block(i, p._row(i)[0])
    j = p._skip(j)
    if j < len(lines):
        raise YamlError("line %d: trailing content" % (j + 1))
    return value


def load_structured(path: Path) -> Any:
    """JSON as JSON; YAML through planner.yamlite when it can, else the
    subset loader above."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        return yamlite.loads(text)
    except (yamlite.YamlLiteError, ValueError):
        return yaml_loads(text)


# --------------------------------------------------------------------------
# OpenAPI: schemas, examples, path parameters
# --------------------------------------------------------------------------
def _deref(doc: dict[str, Any], node: Any, seen: tuple[str, ...] = ()) -> tuple[Any, str]:
    """(node, name) with ``$ref`` followed; name is the last referenced schema."""
    name = ""
    while isinstance(node, dict) and node.get("$ref"):
        ref = str(node["$ref"])
        if ref in seen:
            raise Refusal("OpenAPI $ref cycle at %s" % ref)
        seen = seen + (ref,)
        if not ref.startswith("#/"):
            raise Refusal("OpenAPI $ref %s is not local; the derivation reads one document" % ref)
        cur: Any = doc
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(cur, dict) or part not in cur:
                raise Refusal("OpenAPI $ref %s does not resolve" % ref)
            cur = cur[part]
        name = ref.rsplit("/", 1)[-1]
        node = cur
    return node, name


def merged_schema(doc: dict[str, Any], node: Any, label: str = "") -> dict[str, Any]:
    """The effective schema: ``$ref`` and ``allOf`` folded into one object
    whose ``properties`` keep declaration order and remember which named
    schema declared each one (``origins``)."""
    node, name = _deref(doc, node)
    label = name or label
    if not isinstance(node, dict):
        return {"label": label, "properties": {}, "required": [], "origins": {}}
    out: dict[str, Any] = {"label": label, "properties": {}, "required": [], "origins": {}}
    for part in node.get("allOf") or []:
        sub = merged_schema(doc, part, label)
        for k, v in sub.items():
            if k == "properties":
                out["properties"].update(v)
            elif k == "required":
                out["required"] = list(dict.fromkeys(out["required"] + list(v)))
            elif k == "origins":
                out["origins"].update(v)
            elif k != "label":
                out[k] = v
    for k, v in node.items():
        if k in ("allOf", "$ref"):
            continue
        if k == "properties" and isinstance(v, dict):
            for pname, pschema in v.items():
                out["properties"][str(pname)] = pschema
                out["origins"][str(pname)] = label
        elif k == "required" and isinstance(v, list):
            out["required"] = list(dict.fromkeys(out["required"] + [str(x) for x in v]))
        else:
            out[k] = v
    return out


def example_of(doc: dict[str, Any], node: Any, label: str, gaps: list[str], *, skip: tuple[str, ...] = (),
               depth: int = 0) -> tuple[Any, bool]:
    """(value, present). An example is only ever the document's own: a
    required property without one is a gap and the whole value is absent."""
    if depth > 12:
        raise Refusal("OpenAPI schema nesting deeper than 12 at %s" % label)
    sch = merged_schema(doc, node, label)
    if "example" in sch:
        return sch["example"], True
    if sch.get("properties") or sch.get("type") == "object":
        out: dict[str, Any] = {}
        required = set(sch.get("required") or [])
        for pname, pnode in (sch.get("properties") or {}).items():
            if pname in skip:
                continue
            psch = merged_schema(doc, pnode, pname)
            if psch.get("readOnly") is True:
                continue  # never sent in a request (OpenAPI 3 semantics)
            plabel = "%s.%s" % (sch.get("origins", {}).get(pname) or sch["label"] or label, pname)
            val, ok = example_of(doc, pnode, plabel, gaps, depth=depth + 1)
            if ok:
                out[pname] = val
            elif pname in required:
                gaps.append("no example for %s" % plabel)
                return None, False
        return out, True
    if sch.get("type") == "array":
        items = sch.get("items")
        if items is None:
            return None, False
        val, ok = example_of(doc, items, label + "[]", gaps, depth=depth + 1)
        return ([val], True) if ok else (None, False)
    return None, False


def body_schema(doc: dict[str, Any], op: dict[str, Any]) -> Any:
    rb, _ = _deref(doc, op.get("requestBody"))
    if not isinstance(rb, dict):
        return None
    content = rb.get("content") or {}
    for ctype, media in content.items():
        if "json" in str(ctype).lower() and isinstance(media, dict) and media.get("schema") is not None:
            return media["schema"]
    return None


def path_param_examples(doc: dict[str, Any], item: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for params in (item.get("parameters") or [], op.get("parameters") or []):
        for p in params:
            p, _ = _deref(doc, p)
            if not isinstance(p, dict) or str(p.get("in")) != "path":
                continue
            if "example" in p:
                out[str(p.get("name"))] = p["example"]
            else:
                sch = merged_schema(doc, p.get("schema"))
                if "example" in sch:
                    out[str(p.get("name"))] = sch["example"]
    return out


def _norm_path(p: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", str(p or "")).rstrip("/") or "/"


_CONTROLLER_SUFFIXES = ("restcontroller", "controller", "resource", "endpoint", "api")


def _stem(type_fqn: str) -> str:
    """``a.OwnerRestController`` -> ``owner``: the resource a controller is
    named for, compared against an operation's tags and body schema name."""
    s = str(type_fqn or "").rsplit(".", 1)[-1].lower()
    for suf in _CONTROLLER_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


def member_name(member: Any) -> str:
    return str(member or "").split("(", 1)[0].strip()


_TYPE_SUFFIXES = ("dto", "fields", "request", "input", "payload")


def type_stem(name: str) -> str:
    """``OwnerDto`` / ``OwnerFields`` -> ``owner``: the entity a request type
    is named for, after the conventional suffixes."""
    s = str(name or "").rsplit(".", 1)[-1].lower()
    for suf in _TYPE_SUFFIXES:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


def member_param_stems(member: Any) -> list[str]:
    """The stems of a controller member's parameter types
    (``addOwner(a.OwnerDto,org.springframework.validation.BindingResult)`` ->
    ``[owner, bindingresult]``)."""
    inner = str(member or "").partition("(")[2].rpartition(")")[0]
    return [type_stem(p.strip()) for p in inner.split(",") if p.strip()]


def operation_tag_stems(op: dict[str, Any]) -> list[str]:
    return [str(t).lower() for t in (op.get("tags") or []) if str(t).strip()]


def request_schema_name(doc: dict[str, Any], op: dict[str, Any]) -> str:
    schema = body_schema(doc, op)
    if schema is None:
        return ""
    _, name = _deref(doc, schema)
    return name


def find_operation(doc: dict[str, Any], http_path: str, method: str) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """The OpenAPI path item and operation for a bundle route BY PATH: exact
    match first, else the longest OpenAPI path the route ends with (the
    document's ``servers`` carry the ``/api`` prefix Spring puts on the
    controller). Measured on v9 (2026-09-14): petclinic's document names its
    paths ``/owner``, ``/pet-type``, ``/vet`` while the controllers map
    ``/api/owners``, ``/api/pettypes``, ``/api/vets``, so no path match binds
    a single write there; Derivation._lookup then binds by operationId."""
    want = _norm_path(http_path)
    best: tuple[int, str] | None = None
    for p in (doc.get("paths") or {}):
        cand = _norm_path(str(p))
        if want == cand:
            best = (10 ** 6, str(p))
            break
        if want.endswith(cand) and len(cand) > 1 and (best is None or len(cand) > best[0]):
            best = (len(cand), str(p))
    if best is None:
        return None
    item, _ = _deref(doc, doc["paths"][best[1]])
    op = item.get(method.lower()) if isinstance(item, dict) else None
    if not isinstance(op, dict):
        return None
    return best[1], item, op


# --------------------------------------------------------------------------
# seed data and schema columns
# --------------------------------------------------------------------------
_INSERT_RE = re.compile(r"INSERT\s+(?:IGNORE\s+)?INTO\s+[`\"]?([A-Za-z_][\w]*)[`\"]?\s*(\(([^)]*)\))?\s*VALUES\s*\(", re.IGNORECASE)
_CREATE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?([A-Za-z_][\w]*)[`\"]?\s*\((.*?)\)\s*;", re.IGNORECASE | re.DOTALL)
_CONSTRAINT_WORDS = ("PRIMARY", "CONSTRAINT", "FOREIGN", "UNIQUE", "KEY", "INDEX", "CHECK")


def _tuple_values(text: str, start: int) -> list[str]:
    """The comma-separated values from ``start`` to the matching ``)``,
    quotes respected."""
    out: list[str] = []
    cur: list[str] = []
    quote = ""
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                if text[i + 1:i + 2] == quote:
                    cur.append(ch)
                    i += 2
                    continue
                quote = ""
            else:
                cur.append(ch)
            i += 1
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            if depth == 0:
                out.append("".join(cur).strip())
                return out
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    return out


def parse_seed(text: str) -> dict[str, dict[str, Any]]:
    """{table: {"columns": [...] or [], "values": [first row], "rows": [every row]}}.

    The first INSERT row per table names an existing identifier; EVERY row is
    kept too, because a delete cannot be derived from the first row alone: it
    has to know which rows another table's foreign key already references
    (petclinic seeds ``vet_specialties`` against every ``specialties`` row, so
    deleting row 1 answers 400, not 204)."""
    out: dict[str, dict[str, Any]] = {}
    for m in _INSERT_RE.finditer(text):
        table = m.group(1).lower()
        cols = [c.strip().strip('`"').lower() for c in (m.group(3) or "").split(",") if c.strip()] if m.group(2) else []
        values = _tuple_values(text, m.end())
        row = out.get(table)
        if row is None:
            out[table] = {"columns": cols, "values": values, "rows": [values]}
        elif cols == row["columns"]:
            # a second statement shaped like the first: another row of the same
            # table. A differently shaped one is not merged (its positions do
            # not line up), and saying so is better than misreading it
            row["rows"].append(values)
    return out


def table_rows(seed: dict[str, dict[str, Any]], columns: dict[str, list[str]], table: str) -> list[dict[str, str]]:
    """The seed rows of ``table`` as column->value maps; the column names come
    from the INSERT when it lists them, else from the schema."""
    row = seed.get(table)
    if not row:
        return []
    cols = row.get("columns") or columns.get(table) or []
    out: list[dict[str, str]] = []
    for vals in (row.get("rows") or []):
        out.append({c: str(vals[i]).strip("'\"") for i, c in enumerate(cols) if i < len(vals)})
    return out


def column_values(seed: dict[str, dict[str, Any]], columns: dict[str, list[str]], table: str, column: str) -> list[str]:
    """Every seeded value of one column, in insertion order."""
    row = seed.get(table)
    if not row or not column:
        return []
    cols = row.get("columns") or columns.get(table) or []
    if column not in cols:
        return []
    i = cols.index(column)
    return [str(vals[i]).strip("'\"") for vals in (row.get("rows") or []) if i < len(vals)]


def parse_schema_columns(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in _CREATE_RE.finditer(text):
        cols: list[str] = []
        for part in _tuple_values(m.group(2) + ")", 0):
            tok = part.strip().split()
            if tok and tok[0].upper() not in _CONSTRAINT_WORDS:
                cols.append(tok[0].strip('`"').lower())
        out[m.group(1).lower()] = cols
    return out


_FK_RE = re.compile(r"FOREIGN\s+KEY\s*\(([^)]*)\)\s*REFERENCES\s+[`\"]?([A-Za-z_]\w*)[`\"]?\s*\(([^)]*)\)", re.IGNORECASE)
_INLINE_REF_RE = re.compile(r"REFERENCES\s+[`\"]?([A-Za-z_]\w*)[`\"]?\s*\(([^)]*)\)", re.IGNORECASE)
_ON_DELETE_RE = re.compile(r"ON\s+DELETE\s+(CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION)", re.IGNORECASE)
_CONSTRAINT_NAME_RE = re.compile(r"CONSTRAINT\s+[`\"]?([A-Za-z_]\w*)[`\"]?", re.IGNORECASE)
_ALTER_ADD_RE = re.compile(r"ALTER\s+TABLE\s+[`\"]?([A-Za-z_]\w*)[`\"]?\s+ADD\s+(.*?);", re.IGNORECASE | re.DOTALL)
# an ON DELETE rule that makes the parent row deletable anyway: the child rows
# go with it (CASCADE) or stop pointing at it (SET NULL / SET DEFAULT)
_PERMISSIVE_ON_DELETE = ("cascade", "set null", "set default")


def _cols(text: str) -> list[str]:
    return [c.strip().strip('`"').lower() for c in str(text).split(",") if c.strip()]


def _fk_row(table: str, columns: list[str], ref_table: str, ref_columns: list[str], clause: str) -> dict[str, Any]:
    on_delete = _ON_DELETE_RE.search(clause)
    name = _CONSTRAINT_NAME_RE.search(clause)
    return {
        "table": table, "column": columns[0] if columns else "", "columns": columns,
        "ref_table": ref_table.lower(), "ref_column": ref_columns[0] if ref_columns else "", "ref_columns": ref_columns,
        "on_delete": re.sub(r"\s+", " ", on_delete.group(1)).lower() if on_delete else "",
        "constraint": name.group(1) if name else "",
    }


def parse_foreign_keys(text: str) -> list[dict[str, Any]]:
    """Every ``FOREIGN KEY (col) REFERENCES table (col)`` the schema declares,
    table-level, inline on a column, or added by ``ALTER TABLE``.

    A delete scenario that ignores these picks a row the database will not let
    go: v9's ``DELETE /api/specialties/1`` answered 400
    ``DataIntegrityViolationException ... FK_VET_SPECIALTIES_SPECIALTIES``
    because ``vet_specialties`` references every seeded specialty."""
    out: list[dict[str, Any]] = []
    for m in _CREATE_RE.finditer(text):
        table = m.group(1).lower()
        for part in _tuple_values(m.group(2) + ")", 0):
            s = part.strip()
            fk = _FK_RE.search(s)
            if fk is not None:
                out.append(_fk_row(table, _cols(fk.group(1)), fk.group(2), _cols(fk.group(3)), s))
                continue
            ref = _INLINE_REF_RE.search(s)
            tok = s.split()
            if ref is None or not tok or tok[0].upper() in _CONSTRAINT_WORDS:
                continue
            out.append(_fk_row(table, [tok[0].strip('`"').lower()], ref.group(1), _cols(ref.group(2)), s))
    for m in _ALTER_ADD_RE.finditer(text):
        fk = _FK_RE.search(m.group(2))
        if fk is not None:
            out.append(_fk_row(m.group(1).lower(), _cols(fk.group(1)), fk.group(2), _cols(fk.group(3)), m.group(2)))
    return out


def fk_label(fk: dict[str, Any]) -> str:
    """How a constraint is named in a gap: its own name when the schema gives
    one, and always the column that points at the parent."""
    where = "%s.%s" % (fk["table"], fk["column"])
    return "%s/%s" % (fk["constraint"], where) if fk["constraint"] else where


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _plural(word: str) -> str:
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def id_table_candidates(name: str) -> list[str]:
    """The seed tables an ``<entity>Id`` path variable can name, in order --
    the mapping ``resolve_path_var`` already uses (``petTypeId`` ->
    ``pettypes``, ``pet_types``, ``types``)."""
    if not (name.endswith("Id") and len(name) > 2):
        return []
    base = name[:-2]
    words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", base) or [base]
    return list(dict.fromkeys([_plural(base.lower()), _plural(_snake(base)), _plural(words[-1].lower())]))


def table_candidates(name: str, route: str) -> list[str]:
    """The seed tables a route's item segment can name: the path variable's own
    candidates first (the existing mapping), then the route's own segments with
    the same singular/plural tolerance."""
    out = id_table_candidates(name)
    for seg in reversed([s for s in route.split("/") if s and "{" not in s and "*" not in s]):
        out.extend([seg.lower(), _snake(seg), _plural(seg.lower()), _singular(seg.lower())])
    return list(dict.fromkeys(x for x in out if x))


def _row_value(row: dict[str, Any], column: str, default_index: int | None) -> str | None:
    cols = row.get("columns") or []
    vals = row.get("values") or []
    idx = cols.index(column) if column in cols else (default_index if not cols else None)
    if idx is None or idx >= len(vals):
        return None
    return str(vals[idx]).strip("'\"")


def resolve_path_var(name: str, seed: dict[str, dict[str, Any]], columns: dict[str, list[str]],
                     examples: dict[str, Any], route: str) -> tuple[str | None, str]:
    """(value, evidence) for a ``{name}`` path variable, from the seed data
    first (``ownerId`` -> the first ``owners`` row's id; ``lastName`` -> the
    first row of the table the route names, column ``last_name``), else the
    OpenAPI path parameter's example. None when nothing supplies it."""
    if name.endswith("Id") and len(name) > 2:
        for table in id_table_candidates(name):
            if table in seed:
                val = _row_value(seed[table], "id", 0)
                if val is not None:
                    return val, "seed:%s#%s" % (table, val)
    else:
        column = _snake(name)
        tables = [seg.lower() for seg in route.split("/") if seg and "{" not in seg and "*" not in seg]
        for table in reversed(tables):
            if table in seed:
                cols = seed[table].get("columns") or columns.get(table) or []
                if column in cols:
                    val = _row_value({"columns": cols, "values": seed[table]["values"]}, column, None)
                    if val is not None:
                        return val, "seed:%s.%s" % (table, column)
    if name in examples and examples[name] is not None:
        return str(examples[name]), "openapi:parameter %s example" % name
    return None, ""


# --------------------------------------------------------------------------
# the persistence model: which references the APPLICATION removes itself
# --------------------------------------------------------------------------
# Measured on v9 (2026-09-14): a schema foreign key with no ON DELETE CASCADE
# does NOT mean the source refuses the delete. ``DELETE /api/owners/1``
# answered 204 although ``pets.owner_id`` points at owner 1, because
# ``Owner.pets`` is a ``@OneToMany(cascade = ALL)`` and the application removes
# the children before the database ever sees the parent's delete. Only
# ``specialties`` refused, because ``Specialty`` declares nothing and the
# ``vet_specialties`` rows stay. So a refusal expectation derived from the
# schema alone is not evidence-derived: the relationship annotations in M1's
# structure model are the other half of the evidence, and they are read here.
_RELATION_ANNS = ("OneToMany", "ManyToMany", "OneToOne", "ManyToOne")
_CASCADE_REMOVING = ("ALL", "REMOVE")
_CASCADE_TOKENS = ("ALL", "PERSIST", "MERGE", "REMOVE", "REFRESH", "DETACH")


def _simple(fqn: str) -> str:
    return str(fqn).rsplit(".", 1)[-1].strip()


def _ann_values(ann: Any) -> dict[str, Any]:
    if not isinstance(ann, dict):
        return {}
    vals = ann.get("values")
    if vals is None:
        vals = ann.get("attributes")
    return vals if isinstance(vals, dict) else {}


def _find_ann(anns: Any, simple: str) -> dict[str, Any] | None:
    for a in (anns or []):
        if isinstance(a, dict) and _simple(a.get("fqn") or a.get("name") or "") == simple:
            return a
    return None


def _ann_strings(values: dict[str, Any], key: str) -> list[str]:
    raw = values.get(key)
    items = raw if isinstance(raw, list) else [raw] if raw is not None else []
    return [str(x).strip() for x in items if str(x).strip()]


def _ann_first(values: dict[str, Any], key: str) -> str:
    got = _ann_strings(values, key)
    return got[0] if got else ""


def cascade_tokens(values: dict[str, Any]) -> tuple[list[str], str]:
    """(the CascadeType tokens a relationship declares, the unrecognised one).

    ``cascade = CascadeType.ALL``, ``{CascadeType.PERSIST, CascadeType.MERGE}``
    and a bare ``ALL`` all reach the model as strings; a token this list does
    not know is not guessed at -- it makes the decision underivable."""
    out: list[str] = []
    for item in _ann_strings(values, "cascade"):
        for tok in re.split(r"[,{}]", item):
            tok = tok.strip()
            if not tok:
                continue
            tok = _simple(tok).upper()
            if tok not in _CASCADE_TOKENS:
                return out, tok
            out.append(tok)
    return list(dict.fromkeys(out)), ""


def entity_table_candidates(simple: str) -> list[str]:
    """The tables an entity's simple name can map to when it declares no
    ``@Table(name)``: the same singular/plural tolerance the path variables
    already use (``PetType`` -> ``pettypes``, ``pet_types``, ``types`` is NOT
    derivable from the name, which is exactly why ``@Table`` is read first)."""
    lo = simple.lower()
    sn = _snake(simple)
    return list(dict.fromkeys([lo, sn, _plural(lo), _plural(sn), _singular(lo), _singular(sn)]))


class PersistenceModel:
    """The JPA relationships M1's structure model records, indexed by table.

    ``available`` is False when no structure model could be read: "the source
    removes nothing" and "nobody looked" must not be the same answer."""

    def __init__(self, types: Any, tables: set[str]) -> None:
        self.available = bool(types)
        self.by_fqn: dict[str, dict[str, Any]] = {}
        self.entities: dict[str, dict[str, Any]] = {}
        self.by_table: dict[str, list[str]] = {}
        self.by_simple: dict[str, list[str]] = {}
        for t in (types or []):
            if isinstance(t, dict) and t.get("fqn"):
                self.by_fqn[str(t["fqn"])] = t
        for fqn, t in sorted(self.by_fqn.items()):
            if _find_ann(t.get("annotations"), "Entity") is None:
                continue
            simple = _simple(fqn)
            table, evidence = self._table_of(t, simple, tables)
            self.entities[fqn] = {"fqn": fqn, "simple": simple, "table": table, "table_evidence": evidence,
                                  "fields": self._fields_of(fqn)}
            self.by_simple.setdefault(simple, []).append(fqn)
            if table:
                self.by_table.setdefault(table, []).append(fqn)

    @staticmethod
    def _table_of(t: dict[str, Any], simple: str, tables: set[str]) -> tuple[str, str]:
        ann = _find_ann(t.get("annotations"), "Table")
        named = _ann_first(_ann_values(ann), "name") if ann is not None else ""
        if named:
            return named.lower(), "structure:%s @Table(name=%s)" % (simple, named.lower())
        for cand in entity_table_candidates(simple):
            if cand in tables:
                return cand, "structure:%s → %s (entity name; no @Table)" % (simple, cand)
        return "", "structure:%s declares no @Table and no schema table is named by %s" % (simple, simple)

    def _fields_of(self, fqn: str) -> list[dict[str, Any]]:
        """The entity's own fields plus every field it inherits from a
        supertype the bundle records (petclinic keeps ``id`` on a
        ``@MappedSuperclass``; a relationship can live there too)."""
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        queue = [fqn]
        while queue:
            cur = queue.pop(0)
            if cur in seen or cur not in self.by_fqn:
                continue
            seen.add(cur)
            t = self.by_fqn[cur]
            for f in (t.get("fields") or []):
                if isinstance(f, dict) and f.get("name"):
                    out.append({"name": str(f["name"]), "type": str(f.get("type") or ""),
                                "annotations": list(f.get("annotations") or []), "declared_by": _simple(cur)})
            queue.extend(str(s) for s in (t.get("supertypes") or []))
        return out

    def relationship_fields(self, ent: dict[str, Any]) -> list[tuple[dict[str, Any], str, dict[str, Any]]]:
        """(field, relationship kind, its annotation values) for every field
        carrying a JPA relationship annotation."""
        out = []
        for f in ent["fields"]:
            for kind in _RELATION_ANNS:
                ann = _find_ann(f["annotations"], kind)
                if ann is not None:
                    out.append((f, kind, _ann_values(ann)))
                    break
        return out

    def _entity_named(self, name: str) -> str:
        name = _simple(re.sub(r"\.class$", "", str(name).strip()))
        if not name:
            return ""
        hits = self.by_simple.get(name) or []
        return hits[0] if len(hits) == 1 else ""

    def target_entity(self, ent: dict[str, Any], field: dict[str, Any], values: dict[str, Any]) -> tuple[str, str]:
        """(the fqn of the entity on the other end of ``field``, why not).

        The structure model records the erased field type (``java.util.Set``),
        so a collection's element type is never read off the field. It is
        derived, in order, from ``targetEntity``, from the field type when that
        IS an entity, from ``mappedBy`` (the entity declaring a field of that
        name whose type is this entity), and last from the field name against
        the entity names. An ambiguity is not resolved by guessing."""
        named = _ann_first(values, "targetEntity")
        if named:
            got = self._entity_named(named)
            return (got, "") if got else ("", "targetEntity %s names no single entity in the structure model" % named)
        if field["type"] in self.entities:
            return field["type"], ""
        mapped = _ann_first(values, "mappedBy")
        if mapped:
            hits = sorted(fqn for fqn, other in self.entities.items()
                          if any(f["name"] == mapped and f["type"] == ent["fqn"] for f in other["fields"]))
            if len(hits) == 1:
                return hits[0], ""
            if len(hits) > 1:
                return "", ("mappedBy=%s names %d entities with a field of that name typed %s"
                            % (mapped, len(hits), ent["simple"]))
            # the inverse end of a collection is itself erased in the model, so
            # mappedBy names nothing to walk back to; the name is tried next
        for cand in (_singular(field["name"]), field["name"]):
            hits = [fqn for fqn in self.entities if _simple(fqn).lower() == cand.lower()]
            if len(hits) == 1:
                return hits[0], ""
        return "", ("field %s.%s is typed %s, declares neither targetEntity nor mappedBy, and its name names no single entity"
                    % (ent["simple"], field["name"], field["type"] or "?"))


def _join_table_of(values: dict[str, Any], field: dict[str, Any]) -> str:
    ann = _find_ann(field["annotations"], "JoinTable")
    if ann is None:
        return ""
    return _ann_first(_ann_values(ann), "name").lower()


def application_removes(model: PersistenceModel, table: str, fk: dict[str, Any],
                        foreign_keys: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    """Does deleting a row of ``table`` remove the rows of ``fk['table']`` that
    point at it, without the database refusing?

    Returns (verdict, evidence, the entity-to-table mappings it relied on).
    ``verdict`` is ``schema`` (the constraint carries the children away),
    ``application`` (a cascading/orphan-removing relationship, or ownership of
    a ``@ManyToMany`` join table), ``none`` (nothing removes them: the source
    refuses) or ``unknown`` (the evidence does not decide, so NEITHER scenario
    is derived)."""
    if fk["on_delete"] in _PERMISSIVE_ON_DELETE:
        return "schema", "schema:FOREIGN KEY %s declares ON DELETE %s" % (fk_label(fk), fk["on_delete"].upper()), []
    ref = "%s.%s" % (fk["table"], fk["column"])
    if not model.available:
        return "unknown", "no structure model at %s, so the application's own relationships are unknown" % STRUCTURE.as_posix(), []
    owners = model.by_table.get(table) or []
    if not owners:
        return "unknown", "no @Entity in the structure model maps to table %s" % table, []
    if len(owners) > 1:
        return "unknown", "%d entities map to table %s (%s)" % (len(owners), table, ", ".join(_simple(f) for f in owners)), []
    ent = model.entities[owners[0]]
    mine = [ent["table_evidence"]]
    undecided = ""
    for field, kind, values in model.relationship_fields(ent):
        toks, bad = cascade_tokens(values)
        if bad:
            return "unknown", "%s.%s declares cascade token %s, which is not a CascadeType this derivation knows" % (ent["simple"], field["name"], bad), mine
        join = _join_table_of(values, field)
        target, why = model.target_entity(ent, field, values)
        if not target and not join:
            undecided = undecided or why
            continue
        target_table = model.entities[target]["table"] if target in model.entities else ""
        if target and not target_table:
            undecided = undecided or ("%s.%s targets %s, which maps to no schema table" % (ent["simple"], field["name"], _simple(target)))
            continue
        mapping = mine + ([model.entities[target]["table_evidence"]] if target in model.entities else [])
        # (b) the join table of a @ManyToMany this entity OWNS: JPA deletes the
        # join rows with the owning entity, so nothing is left pointing at it
        if kind == "ManyToMany":
            owned = join == fk["table"] if join else _owns_implicit_join(model, ent, field, target, fk["table"], foreign_keys)
            if owned:
                return "application", ("structure:%s.%s @ManyToMany %s: %s owns the %s join table, whose rows JPA removes with the owning entity"
                                       % (ent["simple"], field["name"],
                                          "@JoinTable(name=%s)" % join if join else "(no @JoinTable; the join table carries both foreign keys)",
                                          ent["simple"], fk["table"])), mapping
        # (a) a relationship at the referencing table that cascades the remove
        if target_table == fk["table"]:
            orphan = _ann_first(values, "orphanRemoval").lower() == "true"
            removing = [t for t in toks if t in _CASCADE_REMOVING]
            if removing or orphan:
                detail = ", ".join(([("cascade=%s" % "+".join(removing))] if removing else []) + (["orphanRemoval=true"] if orphan else []))
                return "application", ("structure:%s.%s @%s(%s) → %s (table %s): the application removes %s itself"
                                       % (ent["simple"], field["name"], kind, detail, _simple(target), target_table, ref)), mapping
    if undecided:
        return "unknown", undecided, mine
    return "none", ("structure:%s (table %s) declares no relationship to %s with cascade ALL/REMOVE or orphanRemoval and owns no join table there: none declared"
                    % (ent["simple"], table, fk["table"])), mine


def _owns_implicit_join(model: PersistenceModel, ent: dict[str, Any], field: dict[str, Any], target: str,
                        join_table: str, foreign_keys: list[dict[str, Any]]) -> bool:
    """``ent`` is the owning side of a ``@ManyToMany`` whose join table JPA
    names by default: the OTHER side declares ``mappedBy`` pointing at this
    field, and ``join_table`` carries a foreign key to each side's table."""
    other = model.entities.get(target)
    if other is None:
        return False
    points_back = False
    for f, kind, values in model.relationship_fields(other):
        if kind == "ManyToMany" and _ann_first(values, "mappedBy") == field["name"]:
            back, _ = model.target_entity(other, f, values)
            if back == ent["fqn"]:
                points_back = True
    if not points_back:
        return False
    refs = {fk["ref_table"] for fk in foreign_keys if fk["table"] == join_table}
    return ent["table"] in refs and other["table"] in refs


def load_persistence_model(root: Path, tables: set[str]) -> PersistenceModel:
    p = Path(root) / STRUCTURE
    if not p.is_file():
        return PersistenceModel([], tables)
    try:
        doc = load_json(p)
    except (OSError, ValueError):
        return PersistenceModel([], tables)
    return PersistenceModel((doc.get("types") or []) if isinstance(doc, dict) else [], tables)


# --------------------------------------------------------------------------
# the HTTP method a mapping that declares none still answers
# --------------------------------------------------------------------------
# Spring MVC: ``@RequestMapping`` WITHOUT ``method`` matches EVERY method, so
# such an entry point answers a GET -- and a GET is a request this corpus can
# derive. Measured on v9 (2026-09-14): ``RootRestController#redirectToSwagger``
# declares ``@RequestMapping(value = "/")`` and answers ``GET /`` with a 302 to
# ``servletContextPath + "/swagger-ui/index.html"``. The derivation recorded a
# gap and derived nothing, so no scenario observed it -- and a worker then
# replaced the SpEL ``@Value("#{servletContext.contextPath}")`` with
# ``@Value("")`` on the destination, sending the redirect outside the
# destination's own root path. A behavioural withdrawal nothing could see.
#
# The shortcut annotations (``@GetMapping`` and its siblings) each imply their
# own method, so only ``@RequestMapping`` can be method-less; a handler with no
# mapping annotation in M1's structure model is not a Spring request mapping at
# all (a servlet mapping is the case the previous gap named) and stays a gap.
# Read from the model, never from text.
_MAPPING_PKG = "org.springframework.web.bind.annotation"
_ANY_METHOD_ANN = "RequestMapping"
_REQUEST_BODY_ANN = "RequestBody"


def mapping_annotation(anns: Any) -> dict[str, Any] | None:
    """The Spring request-mapping annotation among ``anns``, if any."""
    for a in (anns or []):
        if not isinstance(a, dict):
            continue
        fqn = str(a.get("fqn") or a.get("name") or "")
        simple = _simple(fqn)
        if simple.endswith("Mapping") and (fqn == simple or fqn.startswith(_MAPPING_PKG)):
            return a
    return None


def methodless_mapping(type_row: Any, method_row: Any) -> tuple[str, str]:
    """(the mapping that makes this handler answer every HTTP method, why not).

    The handler's own mapping decides; a type-level one answers only when the
    member declares none. A mapping that names its method, or no mapping at
    all, derives nothing and says which."""
    for where, anns in (("handler", (method_row or {}).get("annotations")), ("type", (type_row or {}).get("annotations"))):
        ann = mapping_annotation(anns)
        if ann is None:
            continue
        simple = _simple(ann.get("fqn") or ann.get("name") or "")
        if simple != _ANY_METHOD_ANN:
            return "", "the %s declares @%s, which carries its own HTTP method" % (where, simple)
        declared = _ann_strings(_ann_values(ann), "method")
        if declared:
            return "", "@%s on the %s declares method=%s" % (simple, where, ", ".join(declared))
        return "@%s on the %s" % (simple, where), ""
    return "", "neither the handler nor its type declares a Spring request mapping"


def request_body_param(method_row: Any) -> str:
    """The handler parameter annotated ``@RequestBody``; "" when it has none.

    A mapping that declares no method still matches every method, but a
    handler that CONSUMES a body does not answer a GET the corpus could send:
    the evidence supports no request, so it derives none."""
    for p in ((method_row or {}).get("params") or []):
        if isinstance(p, dict) and _find_ann(p.get("annotations"), _REQUEST_BODY_ANN) is not None:
            return "%s %s" % (str(p.get("type") or "?"), str(p.get("name") or "?"))
    return ""


# --------------------------------------------------------------------------
# the derivation
# --------------------------------------------------------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _input(path: Path, base: Path) -> dict[str, str]:
    return {"path": _rel(path, base), "sha256": sha256_file(path)} if path.is_file() else {"path": "", "sha256": ""}


def find_openapi(copy: Path) -> tuple[Path, dict[str, Any]] | None:
    base = copy / RESOURCES
    if not base.is_dir():
        return None
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".yml", ".yaml", ".json"):
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "openapi" not in head or "paths" not in head:
            continue
        try:
            doc = load_structured(p)
        except (YamlError, ValueError, Refusal):
            continue
        if isinstance(doc, dict) and doc.get("openapi") and isinstance(doc.get("paths"), dict):
            return p, doc
    return None


def find_seed(copy: Path, engine: str) -> tuple[Path | None, str]:
    db = copy / RESOURCES / "db"
    if not db.is_dir():
        return None, ""
    for name in [engine, DEFAULT_ENGINE] + sorted(d.name for d in db.iterdir() if d.is_dir()):
        if name and (db / name / "populateDB.sql").is_file():
            return db / name / "populateDB.sql", name
    return None, ""


def find_schema_sql(seed_p: Path) -> list[Path]:
    """The schema files that stand beside the seed: every other ``*.sql`` in
    the same directory that declares a table.

    The rule used to name one file (``schema.sql``), so petclinic's own
    ``initDB.sql`` -- which is where its FOREIGN KEY constraints are -- was
    never read. Discovery is by the same rule as the seed (the decided
    engine's directory) and by CONTENT (``CREATE TABLE``), never by a
    specimen's filename."""
    out: list[Path] = []
    for p in sorted(seed_p.parent.glob("*.sql")):
        if p.name == seed_p.name or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _CREATE_RE.search(text):
            out.append(p)
    return out


def _decided_engines(root: Path) -> tuple[str, str]:
    """(source engine, destination engine) from decisions.yaml when it is
    readable; a preference for which seed to read, never a gate."""
    try:
        from planner.decisions import load_decisions
        ds = (load_decisions(root).get("datasource") or {})
        return str(ds.get("source_baseline_db_kind") or ""), str(ds.get("db_kind") or "")
    except Exception:  # noqa: BLE001 - decisions may not exist yet at M1; the seed still does
        return "", ""


def _invalid_value(example: Any, pattern: str) -> str | None:
    """A string that violates ``pattern``, built from the example plus one
    forbidden character and VERIFIED against the pattern; None when none of
    the candidates is refused by it."""
    try:
        rx = re.compile(pattern)
    except re.error:
        return None
    base = "" if example is None else str(example)
    for ch in FORBIDDEN_CANDIDATES:
        cand = base + ch
        if rx.fullmatch(cand) is None:
            return cand
    return None


def _resource(collection: str) -> str:
    segs = [s for s in collection.split("/") if s and "{" not in s and "*" not in s]
    return segs[-1] if segs else "root"


_RULE_OF_METHOD = {"POST": "create", "PUT": "update", "DELETE": "delete", "GET": "read", "HEAD": "read"}


def _read_slug(path: str) -> str:
    """The scenario slug of a concrete read path: its segments, joined. The
    root path names no segment, so it is ``root`` (``_resource``'s own
    fallback) -- the id is derived from the request, never from the
    specimen's names."""
    segs = [s for s in re.split(r"[^A-Za-z0-9]+", str(path or "")) if s]
    return "-".join(segs).lower() if segs else _resource(str(path or ""))


def _short(policy_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", policy_id.split(":", 1)[-1]).strip("-")


def _policy_origin(values: Any, default: str) -> str:
    """The cross-origin Origin to send: the first origin a policy declares
    explicitly, else the caller's (only meaningful when the policy allows any
    origin)."""
    if isinstance(values, dict):
        for key in ("origins", "value"):
            raw = values.get(key)
            items = raw if isinstance(raw, list) else [raw] if raw else []
            for it in items:
                s = str(it).strip()
                if s and s != "*" and "://" in s:
                    return s
    return default


def _exposed(values: Any) -> list[str]:
    raw = values.get("exposedHeaders") if isinstance(values, dict) else None
    out: list[str] = []
    for item in (raw if isinstance(raw, list) else [raw] if raw else []):
        for tok in str(item).split(","):
            if tok.strip():
                out.append(tok.strip())
    return sorted(dict.fromkeys(out))


def _write_body(root: Path, scenario_id: str, body: Any) -> str:
    rel = BODIES / ("%s.json" % scenario_id.split(":", 1)[-1])
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return rel.as_posix()


class Derivation:
    def __init__(self, root: Path, bundle: dict[str, Any], openapi: dict[str, Any], seed: dict[str, dict[str, Any]],
                 columns: dict[str, list[str]], policies: dict[str, dict[str, Any]], origin: str,
                 foreign_keys: list[dict[str, Any]] | None = None,
                 persistence: PersistenceModel | None = None) -> None:
        self.root = root
        self.openapi = openapi
        self.seed = seed
        self.persistence = persistence if persistence is not None else PersistenceModel([], set())
        self.columns = columns
        self.foreign_keys = list(foreign_keys or [])
        self.policies = policies
        self.origin = origin
        self.gaps: list[str] = []
        self.unbound: set[str] = set()  # entry points whose binding gap is already recorded
        self.scenarios: list[dict[str, Any]] = []
        self.path_vars: dict[str, str] = {}
        self.path_var_evidence: dict[str, str] = {}
        self.eps = sorted((e for e in (bundle.get("entry_points") or []) if isinstance(e, dict)), key=lambda e: str(e.get("id")))
        self.by_type: dict[str, list[dict[str, Any]]] = {}
        for e in self.eps:
            self.by_type.setdefault(str(e.get("type") or ""), []).append(e)
        # (METHOD, operationId) -> the operations declaring it, for the binding
        # a document whose paths do not name the code's routes still offers
        self.by_opid: dict[tuple[str, str], list[tuple[str, dict[str, Any], dict[str, Any]]]] = {}
        for p, item in (openapi.get("paths") or {}).items():
            item, _ = _deref(openapi, item)
            if not isinstance(item, dict):
                continue
            for meth, op in item.items():
                if isinstance(op, dict) and op.get("operationId"):
                    self.by_opid.setdefault((str(meth).upper(), str(op["operationId"])), []).append((str(p), item, op))

    # -- helpers -----------------------------------------------------------
    def _add(self, sc: dict[str, Any]) -> None:
        if any(s["id"] == sc["id"] for s in self.scenarios):
            self.gaps.append("scenario id %s would be derived twice (entry point %s); the second is not emitted" % (sc["id"], sc["entry_point"]))
            return
        self.scenarios.append(sc)

    def _policy_of(self, type_fqn: str) -> str:
        for pid, pol in self.policies.items():
            if pol.get("kind") == "crossorigin" and type_fqn in (pol.get("types") or []):
                return pid
        return ""

    def _collection_get(self, type_fqn: str) -> dict[str, Any] | None:
        cands = [e for e in self.by_type.get(type_fqn, []) if str(e.get("http_method") or "").upper() == "GET"
                 and "{" not in str(e.get("http_path") or "") and "*" not in str(e.get("http_path") or "")]
        cands.sort(key=lambda e: (len(str(e.get("http_path"))), str(e.get("http_path")), str(e.get("id"))))
        return cands[0] if cands else None

    def _create_post(self, type_fqn: str) -> dict[str, Any] | None:
        cands = [e for e in self.by_type.get(type_fqn, []) if str(e.get("http_method") or "").upper() == "POST"
                 and "{" not in str(e.get("http_path") or "") and "*" not in str(e.get("http_path") or "")]
        cands.sort(key=lambda e: (len(str(e.get("http_path"))), str(e.get("http_path")), str(e.get("id"))))
        return cands[0] if cands else None

    def _resolve_vars(self, ep: dict[str, Any], examples: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
        route = str(ep.get("http_path") or "")
        got: dict[str, str] = {}
        unresolved: list[str] = []
        for name in re.findall(r"\{([^{}]+)\}", route):
            if name in self.path_vars:
                got[name] = self.path_vars[name]
                continue
            val, ev = resolve_path_var(name, self.seed, self.columns, examples, route)
            if val is None:
                unresolved.append(name)
                continue
            self.path_vars[name] = val
            self.path_var_evidence[name] = ev
            got[name] = val
        return got, unresolved

    def _lookup(self, ep: dict[str, Any], strict: bool = True, kind: str = "") -> tuple[str, dict[str, Any], dict[str, Any], str] | None:
        """(path, path item, operation, binding evidence) for an entry point.

        By path when the document names the code's routes; else by
        ``operationId``, which in a spec-first source names the controller
        method the entry point embeds (``addOwner`` -> ``#addOwner(...)``).
        Two controllers can share a method name (petclinic's Owner and User
        controllers both declare ``addOwner``): then only the one whose name
        stem matches the operation's tag or body schema (``owner`` ->
        ``OwnerFields``) binds, and an ambiguity that survives is a gap, not
        a guess.

        A name match is not yet a binding: the operation's contract has to be
        REACHABLE through the route. Measured on v9 (2026-09-14), operationId
        ``addPet`` bound ``POST /owner/{ownerId}/pet`` to the route
        ``POST /api/pets``, which carries no ``ownerId`` at all -- the derived
        ``PetFields`` body went to a route that cannot express the operation's
        identity and the source answered 400. So the operation's path
        variables must be exactly resolvable through the route's: the same set
        of names, compared literally. One variable on each side under a
        different name still binds (``find_operation`` already matches paths
        with the variable names erased, and the adapter is not stricter than
        the binder it stands in for)."""
        method = str(ep.get("http_method") or "").upper()
        route = str(ep.get("http_path") or "")
        name = member_name(ep.get("member"))
        found = find_operation(self.openapi, route, method)
        if found is not None:
            oa_path, item, op = found
            opid = str(op.get("operationId") or "")
            if strict and opid and name and opid != name:
                # the path matches but the document says this operation is
                # another member's: binding it would hand one controller
                # another's body (architect review of 708cfef9: addVet bound
                # to the addOwner controller by path alone)
                self.gaps.append("conflicting binding: path %s ↔ operationId %s ≠ member %s (%s); nothing is derived for it" % (oa_path, opid, name, ep.get("id")))
                self.unbound.add(str(ep.get("id")))
                return None
            return oa_path, item, op, "openapi:%s#%s(path)" % (oa_path, method.lower())
        # the explicit adapter: the document's paths do not name the code's
        # routes, so the operation is the one whose operationId names this
        # controller member -- same method, exactly one member of that name
        # among the bundle's entry points, or one singled out by a COMPATIBLE
        # request schema (OwnerDto <-> OwnerFields); tags and name stems only
        # narrow, never establish
        ops = self.by_opid.get((method, name)) or []
        if not name or not ops:
            return None
        if len(ops) > 1:
            self.gaps.append("operationId %s appears on %d paths (%s); no single operation binds %s" % (name, len(ops), ", ".join(p for p, _, _ in ops), ep.get("id")))
            self.unbound.add(str(ep.get("id")))
            return None
        oa_path, item, op = ops[0]
        claimants = [e for e in self.eps if str(e.get("http_method") or "").upper() == method and member_name(e.get("member")) == name]
        if len(claimants) > 1:
            schema_name = request_schema_name(self.openapi, op)
            survivors = [e for e in claimants if schema_name and type_stem(schema_name) in member_param_stems(e.get("member"))]
            if len(survivors) > 1:
                narrow = [e for e in survivors if any(t.startswith(_stem(str(e.get("type") or ""))) for t in operation_tag_stems(op))]
                survivors = narrow if len(narrow) == 1 else survivors
            if len(survivors) != 1:
                if ep is claimants[0]:
                    self.gaps.append("ambiguous binding: operationId %s (%s %s) is claimed by %d members and its request schema %s singles out %s: %s"
                                     % (name, method, oa_path, len(claimants), schema_name or "(none)", "none" if not survivors else "%d" % len(survivors),
                                        ", ".join(str(e.get("id")) for e in claimants)))
                return None
            if survivors[0] is not ep:
                return None
        op_vars = re.findall(r"\{([^{}]+)\}", oa_path)
        route_vars = re.findall(r"\{([^{}]+)\}", route)
        if set(op_vars) != set(route_vars) and not (len(op_vars) == 1 and len(route_vars) == 1):
            self.gaps.append("%s%s: operationId %s binds %s %s (variables: %s) to route %s (variables: %s); path-variable sets differ; not bound"
                             % ((kind + " ") if kind else "", ep.get("id"), name, method, oa_path, ", ".join(op_vars) or "none",
                                route, ", ".join(route_vars) or "none"))
            self.unbound.add(str(ep.get("id")))
            return None
        renamed = ("; single path variable {%s} read as {%s}" % (op_vars[0], route_vars[0])) if op_vars != route_vars and op_vars else ""
        return oa_path, item, op, "openapi-path:%s≠route:%s; bound by operationId %s%s" % (oa_path, route, name, renamed)

    # -- rules -------------------------------------------------------------
    def run(self) -> None:
        for ep in self.eps:
            eid = str(ep.get("id") or "")
            method = str(ep.get("http_method") or "").upper()
            route = str(ep.get("http_path") or "")
            if not method and str(ep.get("kind") or "http") != "http":
                self.gaps.append("entry point %s has no HTTP method (a non-HTTP entry point is captured by observation); nothing is derived for it" % eid)
                continue
            # a read consults the document for path-parameter examples only;
            # the binding rules (and their gaps) are for the writes it feeds.
            # A mapping that declares no method binds to no operation either:
            # the document keys its operations by method
            found = self._lookup(ep, strict=method not in ("GET", "HEAD"), kind=_RULE_OF_METHOD.get(method, "")) if method else None
            examples = path_param_examples(self.openapi, found[1], found[2]) if found else {}
            got, unresolved = self._resolve_vars(ep, examples)
            for name in unresolved:
                self.gaps.append("path variable {%s} of %s resolves nowhere (no seed row, no OpenAPI example); scenarios needing it are not emitted" % (name, eid))
            if "*" in route:
                self.gaps.append("entry point %s route %s carries a wildcard and is not a request" % (eid, route))
                continue
            if not method:
                self._methodless_read(ep, got, unresolved)
                continue
            if method in ("GET", "HEAD"):
                continue  # reads are captured by capture-source-oracles.py with path_vars
            if method == "POST":
                self._create(ep, found, got, unresolved)
            elif method == "PUT":
                self._update(ep, found, got, unresolved)
            elif method == "DELETE":
                self._delete(ep, got, unresolved)
            else:
                self.gaps.append("entry point %s uses %s, for which no derivation rule exists" % (eid, method))
        self._cors()
        self.scenarios.sort(key=lambda s: str(s["id"]))

    # -- an entry point whose mapping declares no HTTP method ---------------
    def _structure_member(self, ep: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
        """(the type, the handler, why not) for an entry point, from M1's
        structure model. An overload the signature does not single out is a
        reason, not a guess."""
        if not self.persistence.available:
            return {}, {}, "M1's structure model was not read"
        type_fqn = str(ep.get("type") or "")
        t = self.persistence.by_fqn.get(type_fqn)
        if not isinstance(t, dict):
            return {}, {}, "the structure model records no type %s" % (type_fqn or "(none)")
        member = str(ep.get("member") or "")
        name = member_name(ep.get("member"))
        methods = [m for m in (t.get("methods") or []) if isinstance(m, dict)]
        exact = [m for m in methods if str(m.get("signature") or "") == member]
        if len(exact) == 1:
            return t, exact[0], ""
        by_name = [m for m in methods if str(m.get("name") or "") == name]
        if name and len(by_name) == 1:
            return t, by_name[0], ""
        return t, {}, "the structure model records no single member %s on %s" % (member or name or "(unnamed)", type_fqn)

    def _methodless_read(self, ep: dict[str, Any], got: dict[str, str], unresolved: list[str]) -> None:
        """A mapping that names no HTTP method answers every one of them, so a
        GET is a request the evidence supports, and its ONE read scenario's
        contract is the source's own first response (redirects are never
        followed). Nothing here states an expected status class: whether the
        source answers 2xx or 3xx is not knowable a priori, so qualification
        judges the evidence and RECORDS the class it observed."""
        eid, route, type_fqn = str(ep["id"]), str(ep.get("http_path") or ""), str(ep.get("type") or "")
        member = str(ep.get("member") or "") or member_name(ep.get("member"))
        t, m, why = self._structure_member(ep)
        if why:
            self.gaps.append("entry point %s has no HTTP method and none is derivable (%s); nothing is derived for it" % (eid, why))
            return
        mapping, why = methodless_mapping(t, m)
        if not mapping:
            self.gaps.append("entry point %s has no HTTP method and no method-less mapping to derive one from (%s); "
                             "a servlet mapping is not a request the corpus can derive, and nothing is derived for it" % (eid, why))
            return
        consumed = request_body_param(m)
        if consumed:
            self.gaps.append("entry point %s declares %s without an HTTP method, but its handler consumes a request body (@%s %s); "
                             "a GET carries none, so nothing is derived for it" % (eid, mapping, _REQUEST_BODY_ANN, consumed))
            return
        if unresolved:
            return  # the unresolved variable is already a typed gap
        path = route
        for name, value in sorted(got.items()):
            path = path.replace("{%s}" % name, value)
        if "{" in path or "}" in path:
            self.gaps.append("entry point %s route %s is still a template after path-variable resolution; a scenario carries a concrete URL" % (eid, route))
            return
        sid = "sc:read-%s" % _read_slug(path)
        self._add({
            "id": sid, "entry_point": eid, "method": "GET", "path": path, "headers": {},
            "identity": {"kind": "none"}, "body_absent": True, "reset_before": False,
            "effects": [], "normalization": [],
            "derived_from": {"kind": "read", "entry_point": eid,
                             "evidence": ["bundle:%s" % eid,
                                          "structure:%s#%s @%s without method → GET (Spring: no method matches every method)"
                                          % (type_fqn, member, _ANY_METHOD_ANN)]
                             + [self.path_var_evidence.get(n, "") for n in sorted(got) if self.path_var_evidence.get(n)]},
            "qualify": {"intent": "positive", "usable_first_response": True},
            "why": "the mapping declares no HTTP method, so it answers a GET too; the contract is the source's OWN first response "
                   "(status, headers and body, redirects not followed) -- whether it is 2xx or 3xx is not knowable in advance, "
                   "so the observed status class is recorded rather than expected",
        })

    def _create(self, ep: dict[str, Any], found: Any, got: dict[str, str], unresolved: list[str]) -> None:
        eid, route, type_fqn = str(ep["id"]), str(ep.get("http_path") or ""), str(ep.get("type") or "")
        if "{" in route:
            self.gaps.append("create %s: path %s carries variables; the create rule needs a collection path" % (eid, route))
            return
        if found is None:
            if eid not in self.unbound:  # why it did not bind is already a typed gap
                self.gaps.append("create %s: no OpenAPI operation for POST %s" % (eid, route))
            return
        oa_path, _item, op, binding = found
        schema = body_schema(self.openapi, op)
        if schema is None:
            self.gaps.append("create %s: OpenAPI POST %s declares no JSON request body schema" % (eid, oa_path))
            return
        sch = merged_schema(self.openapi, schema)
        label = sch.get("label") or "requestBody"
        gaps: list[str] = []
        body, ok = example_of(self.openapi, schema, label, gaps, skip=("id",))
        if not ok or not isinstance(body, dict):
            self.gaps.extend(gaps or ["create %s: no example body for %s" % (eid, label)])
            return
        body.pop("id", None)
        resource = _resource(route)
        policy = self._policy_of(type_fqn)
        headers = {"Content-Type": "application/json"}
        if policy:
            headers["Origin"] = _policy_origin(self.policies[policy].get("values"), self.origin)
        evidence = ["bundle:%s" % eid, binding, "openapi:%s#post.requestBody(%s)" % (oa_path, label)]
        if policy:
            evidence.append("structure:%s@CrossOrigin(%s)" % (type_fqn, policy))
        identity, id_evidence = self._identity_field(oa_path, _item, op)
        if id_evidence:
            evidence.append(id_evidence)
        sid = "sc:create-%s" % resource
        sc: dict[str, Any] = {
            "id": sid, "entry_point": eid, "method": "POST", "path": route, "headers": headers,
            "identity": {"kind": "none"}, "body_file": _write_body(self.root, sid, body), "body_absent": False,
            "reset_before": True,
            "effects": [{"id": "eff:%s-list-after-create" % resource, "method": "GET", "path": route}],
            "normalization": [],
            "derived_from": {"kind": "create", "entry_point": eid, "evidence": evidence},
            # identity-aware, not count-based: exactly one entity with a NEW
            # identity, carrying the body, every prior entity kept, and the
            # Location naming that identity (architect review of 708cfef9: a
            # duplicate row with an existing id and a Location pointing at
            # 999 passed a count). identity_field null -> the gate is
            # INCONCLUSIVE, never a guess
            "qualify": {"intent": "positive", "expect_status": [201], "location": "absolute-under-base", "after_contains_body": True,
                        "creates_one_entity": True, "identity_field": identity},
            "why": "the document's own example of %s, created on the collection the route names; the read-back shows exactly one new entity carrying it" % label,
        }
        if policy:
            sc["cors_policy"] = policy
        self._add(sc)
        # create-invalid, ONE per constrained property: a firstName rejection
        # is not telephone coverage. Each body violates exactly one declared
        # constraint (a pattern, verified against it; else a required
        # minLength string set to "")
        constrained: list[tuple[str, Any]] = []
        for pname, pnode in (sch.get("properties") or {}).items():
            psch = merged_schema(self.openapi, pnode, pname)
            if pname not in body:
                continue
            if psch.get("pattern"):
                bad_value = _invalid_value(body[pname], str(psch["pattern"]))
                if bad_value is not None:
                    constrained.append((pname, bad_value))
                    continue
            if pname in (sch.get("required") or []) and psch.get("type") == "string" and int(psch.get("minLength") or 0) >= 1:
                constrained.append((pname, ""))
        if not constrained:
            self.gaps.append("create-invalid %s: %s has no property with a pattern or a required minLength string; no invalid body can be derived" % (eid, label))
            return
        for field, bad_value in constrained:
            invalid = dict(body)
            invalid[field] = bad_value
            isid = "sc:create-invalid-%s-%s" % (resource, field)
            isc: dict[str, Any] = {
                "id": isid, "entry_point": eid, "method": "POST", "path": route, "headers": dict(headers),
                "identity": {"kind": "none"}, "body_file": _write_body(self.root, isid, invalid), "body_absent": False,
                "reset_before": True,
                "effects": [{"id": "eff:%s-list-after-invalid-create-%s" % (resource, field), "method": "GET", "path": route}],
                "normalization": [],
                "derived_from": {"kind": "create-invalid", "entry_point": eid,
                                 "evidence": evidence + ["openapi:%s.%s constraint" % (label, field)]},
                "qualify": {"intent": "negative", "expect_status": [400], "errors_header_names_field": field, "after_equals_before": True},
                "why": "the same body with %s violating the constraint the document declares; the source must reject it and create nothing" % field,
            }
            if policy:
                isc["cors_policy"] = policy
            self._add(isc)

    def _identity_field(self, oa_path: str, item: dict[str, Any], post_op: dict[str, Any]) -> tuple[str | None, str]:
        """(the collection's identity property, evidence) from the OpenAPI
        RESPONSE schema of the collection GET -- the ``get`` of the same path
        item the create bound to -- the items' property named ``id``, else
        the first readOnly integer property (``Owner`` = allOf(OwnerFields)
        + id). When the path item has no listing, the create's own 2xx
        response entity says the same. None when the document does not say:
        the gate then refuses to judge the create, never counts."""
        def entity_identity(sch: dict[str, Any], where: str) -> tuple[str | None, str]:
            props = sch.get("properties") or {}
            label = sch.get("label") or "entity"
            if "id" in props:
                return "id", "openapi:%s %s(%s).id" % (oa_path, where, label)
            for pname, pnode in props.items():
                psch = merged_schema(self.openapi, pnode, pname)
                if psch.get("readOnly") is True and psch.get("type") == "integer":
                    return pname, "openapi:%s %s(%s).%s readOnly integer" % (oa_path, where, label, pname)
            return None, ""

        def json_schemas(op: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
            out = []
            for code, resp in sorted((op.get("responses") or {}).items(), key=lambda kv: str(kv[0])):
                if not str(code).startswith("2") and str(code) != "default":
                    continue
                resp, _ = _deref(self.openapi, resp)
                for ctype, media in ((resp or {}).get("content") or {}).items():
                    if "json" in str(ctype).lower() and isinstance(media, dict) and media.get("schema") is not None:
                        out.append((str(code), merged_schema(self.openapi, media["schema"])))
            return out

        get_op = item.get("get") if isinstance(item, dict) else None
        if isinstance(get_op, dict):
            for code, sch in json_schemas(get_op):
                items = sch.get("items") if sch.get("type") == "array" or "items" in sch else None
                if items is None:
                    continue
                found = entity_identity(merged_schema(self.openapi, items), "#get.responses.%s items" % code)
                if found[0]:
                    return found
        for code, sch in json_schemas(post_op):
            found = entity_identity(sch, "#post.responses.%s" % code)
            if found[0]:
                return found
        return None, ""

    def _update(self, ep: dict[str, Any], found: Any, got: dict[str, str], unresolved: list[str]) -> None:
        eid, route = str(ep["id"]), str(ep.get("http_path") or "")
        names = re.findall(r"\{([^{}]+)\}", route)
        if len(names) != 1:
            self.gaps.append("update %s: path %s has %d variables; the update rule needs exactly one" % (eid, route, len(names)))
            return
        if unresolved:
            return  # the unresolved variable is already a gap
        if not route.endswith("{%s}" % names[0]):
            self.gaps.append("update %s: variable {%s} is not the terminal segment of %s; the item and collection reads cannot be named" % (eid, names[0], route))
            return
        if found is None:
            if eid not in self.unbound:  # why it did not bind is already a typed gap
                self.gaps.append("update %s: no OpenAPI operation for PUT %s" % (eid, route))
            return
        oa_path, _item, op, binding = found
        schema = body_schema(self.openapi, op)
        if schema is None:
            self.gaps.append("update %s: OpenAPI PUT %s declares no JSON request body schema" % (eid, oa_path))
            return
        sch = merged_schema(self.openapi, schema)
        label = sch.get("label") or "requestBody"
        gaps: list[str] = []
        body, ok = example_of(self.openapi, schema, label, gaps, skip=("id",))
        if not ok or not isinstance(body, dict):
            self.gaps.extend(gaps or ["update %s: no example body for %s" % (eid, label)])
            return
        seeded = got[names[0]]
        if "id" in (sch.get("properties") or {}):
            idsch = merged_schema(self.openapi, sch["properties"]["id"], "id")
            body["id"] = int(seeded) if idsch.get("type") == "integer" and re.fullmatch(r"-?\d+", seeded) else seeded
        item_path = route.replace("{%s}" % names[0], seeded)
        collection = route[: route.rfind("/{")] or "/"
        resource = _resource(collection)
        sid = "sc:update-%s-%s" % (resource, seeded)
        self._add({
            "id": sid, "entry_point": eid, "method": "PUT", "path": item_path,
            "headers": {"Content-Type": "application/json"}, "identity": {"kind": "none"},
            "body_file": _write_body(self.root, sid, body), "body_absent": False, "reset_before": True,
            "effects": [{"id": "eff:%s-%s-after-update" % (resource, seeded), "method": "GET", "path": item_path},
                        {"id": "eff:%s-list-after-update" % resource, "method": "GET", "path": collection}],
            "normalization": [],
            "derived_from": {"kind": "update", "entry_point": eid,
                             "evidence": ["bundle:%s" % eid, binding, "openapi:%s#put.requestBody(%s)" % (oa_path, label), self.path_var_evidence.get(names[0], "")]},
            "qualify": {"intent": "positive", "expect_status": [200, 204], "after_contains_body": True},
            "why": "the document's own example of %s written over the seeded row %s; the read-backs show the row and the list carry it" % (label, seeded),
        })

    # -- the seed rows a delete may address ---------------------------------
    def _seed_table(self, var: str, route: str) -> str:
        for table in table_candidates(var, route):
            if table in self.seed:
                return table
        return ""

    def _column_values(self, table: str, column: str) -> list[str]:
        return column_values(self.seed, self.columns, table, column)

    @staticmethod
    def _by_id(values: list[str]) -> list[str]:
        numeric = all(re.fullmatch(r"-?\d+", v) for v in values) if values else False
        return sorted(dict.fromkeys(values), key=(lambda v: (0, int(v), "")) if numeric else (lambda v: (1, 0, v)))

    def _delete_target(self, eid: str, route: str, var: str, seeded: str) -> dict[str, Any]:
        """Which seed row a delete may address, and which one it may not.

        A delete is derived against the database the source actually loads, so
        the row it addresses must be one nothing points at. v9 picked row 1
        blindly and the source answered 400
        ``DataIntegrityViolationException ... FK_VET_SPECIALTIES_SPECIALTIES``:
        every seeded specialty is referenced by ``vet_specialties``.

        Returns ``table``, ``chosen`` (the deletable row, "" when there is
        none), ``evidence``, ``blocked`` (a referenced row, "" when there is
        none), ``constraints`` (what references it), the ``blocked_fks`` that
        reference that row, and ``removal`` ({verdict: [evidence]}) -- what,
        if anything, takes those references away."""
        out: dict[str, Any] = {"table": "", "chosen": seeded, "evidence": [self.path_var_evidence.get(var, "")],
                               "blocked": "", "constraints": "", "blocked_fks": [], "removal": {}, "removal_rows": [], "mappings": []}
        table = self._seed_table(var, route)
        if not table:
            self.gaps.append("delete %s: no seed table is named by {%s} or by the segments of %s (seed tables: %s); "
                             "its foreign keys are unknown and the row is chosen from the path variable alone"
                             % (eid, var, route, ", ".join(sorted(self.seed)) or "none"))
            return out
        out["table"] = table
        # EVERY inbound reference counts here. Whether the source lets the
        # parent go is decided below, per constraint, from the schema AND the
        # application's own relationships -- not from ON DELETE alone.
        inbound = [fk for fk in self.foreign_keys if fk["ref_table"] == table]
        if not inbound:
            return out
        ids = self._by_id(self._column_values(table, inbound[0]["ref_column"] or "id"))
        if not ids:
            self.gaps.append("delete %s: %s is referenced by %s but its %s column cannot be read from the seed; the row is chosen from the path variable alone"
                             % (eid, table, ", ".join(sorted(fk_label(fk) for fk in inbound)), inbound[0]["ref_column"] or "id"))
            return out
        referenced_by: dict[str, set[str]] = {}
        fk_of_label: dict[str, dict[str, Any]] = {}
        for fk in inbound:
            vals = {v for v in self._column_values(fk["table"], fk["column"]) if v in set(ids)}
            if vals:
                referenced_by[fk_label(fk)] = vals
                fk_of_label[fk_label(fk)] = fk
        referenced = {v for vals in referenced_by.values() for v in vals}
        schema_evidence = "schema:%s" % "; ".join("FOREIGN KEY %s → %s.%s" % (fk_label(fk), fk["ref_table"], fk["ref_column"]) for fk in inbound)
        constraints = ", ".join(sorted(referenced_by)) or ", ".join(sorted(fk_label(fk) for fk in inbound))
        free = [i for i in ids if i not in referenced]
        if free:
            out["chosen"] = free[0]
            out["evidence"] = ["seed:%s#%s unreferenced by %s" % (table, free[0], constraints), schema_evidence]
        else:
            out["chosen"] = ""
            out["evidence"] = []
            self.gaps.append("delete %s: every seed row of %s is referenced (%s); no deletable row derivable" % (eid, table, constraints))
        blocked = self._by_id(sorted(referenced))
        if not blocked:
            return out
        out["blocked"] = blocked[0]
        labels = sorted(label for label, vals in referenced_by.items() if blocked[0] in vals)
        out["constraints"] = ", ".join(labels)
        out["blocked_fks"] = [fk_of_label[label] for label in labels]
        rows: list[dict[str, Any]] = []
        removal: dict[str, list[str]] = {}
        mappings: list[str] = []
        for label in labels:
            verdict, why, mapping = application_removes(self.persistence, table, fk_of_label[label], self.foreign_keys)
            rows.append({"label": label, "fk": fk_of_label[label], "verdict": verdict, "why": why})
            removal.setdefault(verdict, []).append(why)
            mappings.extend(m for m in mapping if m)
        out["removal"] = removal
        out["removal_rows"] = rows
        out["mappings"] = sorted(dict.fromkeys(mappings))
        return out

    # -- the rows that reference a row, and how they are read back -----------
    def _table_rows(self, table: str) -> list[dict[str, str]]:
        return table_rows(self.seed, self.columns, table)

    def _item_route(self, table: str) -> tuple[str, str]:
        """(route, variable) of the bound item GET whose row is a row of
        ``table``, "" when the bundle exposes none: a join table has no route,
        so its rows are simply not observable and the scenario says so."""
        best: tuple[tuple[int, str, str], str, str] | None = None
        for e in self.eps:
            if str(e.get("http_method") or "").upper() != "GET":
                continue
            r = str(e.get("http_path") or "")
            names = re.findall(r"\{([^{}]+)\}", r)
            if len(names) != 1 or "*" in r or not r.endswith("{%s}" % names[0]):
                continue
            if self._seed_table(names[0], r) != table:
                continue
            key = (len(r), r, str(e.get("id")))
            if best is None or key < best[0]:
                best = (key, r, names[0])
        return (best[1], best[2]) if best is not None else ("", "")

    def _referencing_children(self, fk: dict[str, Any], parent_id: str) -> tuple[list[tuple[str, str, str]], str]:
        """([(child resource, child id, its item path)] for the rows of
        ``fk['table']`` pointing at ``parent_id``, why none)."""
        child_table = str(fk["table"])
        route, var = self._item_route(child_table)
        if not route:
            return [], "no bound item route reads a row of %s" % child_table
        cols = self.seed.get(child_table, {}).get("columns") or self.columns.get(child_table) or []
        key = "id" if "id" in cols else (_snake(var) if _snake(var) in cols else "")
        if not key:
            return [], "no column of %s identifies the row %s reads" % (child_table, route)
        resource = _resource(route[: route.rfind("/{")] or "/")
        hits = self._by_id([r[key] for r in self._table_rows(child_table) if r.get(fk["column"]) == parent_id and r.get(key)])
        return [(resource, i, route.replace("{%s}" % var, i)) for i in hits], ""

    def _delete(self, ep: dict[str, Any], got: dict[str, str], unresolved: list[str]) -> None:
        eid, route = str(ep["id"]), str(ep.get("http_path") or "")
        names = re.findall(r"\{([^{}]+)\}", route)
        if len(names) != 1:
            self.gaps.append("delete %s: path %s has %d variables; the delete rule needs exactly one" % (eid, route, len(names)))
            return
        if unresolved:
            return
        if not route.endswith("{%s}" % names[0]):
            self.gaps.append("delete %s: variable {%s} is not the terminal segment of %s" % (eid, names[0], route))
            return
        var = names[0]
        resource = _resource(route[: route.rfind("/{")] or "/")
        target = self._delete_target(eid, route, var, got[var])
        chosen, seed_evidence = str(target["chosen"]), list(target["evidence"])
        if chosen:
            item_path = route.replace("{%s}" % var, chosen)
            eff = "eff:%s-%s-after-delete" % (resource, chosen)
            self._add({
                "id": "sc:delete-%s-%s" % (resource, chosen), "entry_point": eid, "method": "DELETE", "path": item_path,
                "headers": {}, "identity": {"kind": "none"}, "body_absent": True, "reset_before": True,
                "effects": [{"id": eff, "method": "GET", "path": item_path}],
                "normalization": [],
                "derived_from": {"kind": "delete", "entry_point": eid, "evidence": ["bundle:%s" % eid] + [e for e in seed_evidence if e]},
                "qualify": {"intent": "positive", "expect_status": [200, 204], "after_effect_status": {eff: 404}},
                "why": "the seeded row %s exists by construction and nothing references it; the read-back after the delete must not find it" % chosen,
            })
        blocked_id, constraints = str(target["blocked"]), str(target["constraints"])
        if not blocked_id:
            return
        self._referenced_delete(ep, route, var, resource, blocked_id, constraints, target)

    def _referenced_delete(self, ep: dict[str, Any], route: str, var: str, resource: str, blocked_id: str,
                           constraints: str, target: dict[str, Any]) -> None:
        """What a row ANOTHER row points at proves, decided by the evidence.

        The schema says a reference exists; only the application says whether
        it survives the parent's delete. Three answers, three outcomes: nothing
        removes it (the source refuses -- a negative scenario), something does
        (the source deletes the lot -- a positive cascading scenario naming the
        children), or the evidence does not say (a typed gap and NO scenario:
        an expectation nobody can derive is not an oracle)."""
        eid = str(ep["id"])
        item_path = route.replace("{%s}" % var, blocked_id)
        removal: dict[str, list[str]] = target["removal"]
        fk_evidence = ["seed:%s#%s referenced by %s" % (target["table"], blocked_id, constraints)] + [
            "schema:FOREIGN KEY %s → %s.%s%s" % (fk_label(fk), fk["ref_table"], fk["ref_column"],
                                                 " ON DELETE %s" % fk["on_delete"].upper() if fk["on_delete"] else "")
            for fk in target["blocked_fks"]]
        if "unknown" in removal:
            for r in target["removal_rows"]:
                if r["verdict"] == "unknown":
                    self.gaps.append("delete-referenced %s: whether the application removes %s.%s references is not derivable (%s)"
                                     % (eid, r["fk"]["table"], r["fk"]["column"], r["why"]))
            return
        if "none" in removal:
            eff = "eff:%s-%s-after-refused-delete" % (resource, blocked_id)
            self._add({
                "id": "sc:delete-referenced-%s-%s" % (resource, blocked_id), "entry_point": eid, "method": "DELETE", "path": item_path,
                "headers": {}, "identity": {"kind": "none"}, "body_absent": True, "reset_before": True,
                "effects": [{"id": eff, "method": "GET", "path": item_path}],
                "normalization": [],
                "derived_from": {"kind": "delete-referenced", "entry_point": eid,
                                 "evidence": ["bundle:%s" % eid] + fk_evidence
                                 + ["schema:%s declares no ON DELETE CASCADE or SET NULL" % constraints]
                                 + list(target["mappings"]) + sorted(dict.fromkeys(removal["none"]))},
                "qualify": {"intent": "negative", "expect_status_class": "4xx", "after_effect_status": {eff: 200}},
                "why": "seed row %s is referenced by %s, the schema carries no ON DELETE CASCADE or SET NULL and the application declares "
                       "nothing that removes those references, so the source refuses the delete: the response is a 4xx (any) and the "
                       "read-back still answers 200 with the row" % (blocked_id, constraints),
            })
            return
        # the references go with the parent: what the source demonstrates is a
        # DELETE that succeeds and takes the children with it
        eff = "eff:%s-%s-after-cascading-delete" % (resource, blocked_id)
        effects = [{"id": eff, "method": "GET", "path": item_path}]
        after: dict[str, int] = {eff: 404}
        notes: list[str] = []
        for fk in target["blocked_fks"]:
            children, why = self._referencing_children(fk, blocked_id)
            if why:
                notes.append("note:the rows of %s that reference %s#%s are not observable through routes (%s); only the deleted row is checked"
                             % (fk["table"], target["table"], blocked_id, why))
                continue
            if len(children) > _CASCADE_CHILD_CAP:
                notes.append("note:%d rows of %s reference %s#%s; only the first %d are read back"
                             % (len(children), fk["table"], target["table"], blocked_id, _CASCADE_CHILD_CAP))
                children = children[:_CASCADE_CHILD_CAP]
            for child_resource, child_id, child_path in children:
                ceff = "eff:%s-%s-after-cascading-delete" % (child_resource, child_id)
                if ceff in after:
                    continue
                effects.append({"id": ceff, "method": "GET", "path": child_path})
                after[ceff] = 404
        self._add({
            "id": "sc:delete-cascading-%s-%s" % (resource, blocked_id), "entry_point": eid, "method": "DELETE", "path": item_path,
            "headers": {}, "identity": {"kind": "none"}, "body_absent": True, "reset_before": True,
            "effects": effects,
            "normalization": [],
            "derived_from": {"kind": "delete-cascading", "entry_point": eid,
                             "evidence": ["bundle:%s" % eid] + fk_evidence + list(target["mappings"])
                             + sorted(dict.fromkeys(removal.get("application", []) + removal.get("schema", []))) + notes},
            "qualify": {"intent": "positive", "expect_status": [200, 204], "after_effect_status": after},
            "why": "seed row %s is referenced by %s, and the reference is removed with the row (%s), so the source performs the delete: "
                   "the response is 200 or 204, the row reads back 404 and so does each referencing row a bound route can read"
                   % (blocked_id, constraints, "; ".join(sorted(dict.fromkeys(removal.get("application", []) + removal.get("schema", []))))),
        })

    def _cors(self) -> None:
        for pid, pol in self.policies.items():
            origin = _policy_origin(pol.get("values"), self.origin)
            carriers = list(pol.get("types") or [])
            if pol.get("kind") == "global":
                # a registry applies to every controller; exercise it on one
                # that carries no @CrossOrigin of its own (whose answer would
                # be the annotation's, not the registry's)
                carriers = sorted(t for t in self.by_type if t and not self._policy_of(t)) or sorted(t for t in self.by_type if t)
            actual = next((self._collection_get(t) for t in carriers if self._collection_get(t)), None)
            post = next((self._create_post(t) for t in carriers if self._create_post(t)), None)
            short = _short(pid)
            if actual is None:
                self.gaps.append("cors policy %s: no controller carrying it has a collection GET to exercise the actual exchange" % pid)
            else:
                q: dict[str, Any] = {"intent": "positive", "expect_status": [200], "cors_allow_origin": True}
                exposed = _exposed(pol.get("values"))
                if exposed:
                    q["cors_expose_headers"] = exposed
                self._add({
                    "id": "sc:cors-actual-%s" % short, "entry_point": str(actual["id"]), "method": "GET",
                    "path": str(actual.get("http_path")), "headers": {"Origin": origin}, "identity": {"kind": "none"},
                    "body_absent": True, "reset_before": True, "effects": [], "normalization": [], "cors_policy": pid,
                    "derived_from": {"kind": "cors-actual", "entry_point": str(actual["id"]),
                                     "evidence": ["structure:%s(%s)" % (pid, ", ".join(pol.get("types") or [])), "bundle:%s" % actual["id"]]},
                    "qualify": q,
                    "why": "an actual cross-origin read on a controller carrying %s; the permission and exposure headers are the policy's" % pid,
                })
            if post is None:
                self.gaps.append("cors policy %s: no controller carrying it has a create (POST) path for the preflight" % pid)
            else:
                self._add({
                    "id": "sc:cors-preflight-%s" % short, "entry_point": str(post["id"]), "method": "OPTIONS",
                    "path": str(post.get("http_path")),
                    "headers": {"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
                    "body_absent": True, "reset_before": False, "effects": [], "normalization": [], "cors_policy": pid,
                    "derived_from": {"kind": "cors-preflight", "entry_point": str(post["id"]),
                                     "evidence": ["structure:%s(%s)" % (pid, ", ".join(pol.get("types") or [])), "bundle:%s" % post["id"]]},
                    "qualify": {"intent": "positive", "expect_status": [200, 204], "cors_allow_origin": True, "cors_allow_method": "POST", "cors_allow_headers": ["content-type"]},
                    "why": "the preflight a browser sends before the create under %s; no credentials, no effects" % pid,
                })


# --------------------------------------------------------------------------
# the enabled security mode: one probe set per authorization policy (ADR-014)
# --------------------------------------------------------------------------
# ADR-014 keeps the source's authorization semantics, and says what an
# enabled-mode oracle has to show: each distinct policy exercised with an
# allowed identity, anonymous access, invalid credentials and an authenticated
# identity that lacks the required role, compared against the SOURCE's actual
# outcomes -- challenges and denied-write effects included. It also says what
# to do when the fixtures for that are not there: record a blocker. So nothing
# here invents an identity, a role or a credential. What is missing is named.
#
# The request is not derived a second time. A policy guards an entry point the
# disabled corpus already carries a qualified-shaped scenario for, and that
# scenario's method, path, headers and body bytes are reused verbatim, bound
# by its id and its body digest: the two modes then differ in exactly one
# thing, which is the identity the request carries.
#
# One identity is not enough for a REFUSAL, though. What a refused write must
# show is that the state did not change, and the caller it refused is answered
# 401 by the read-backs too; so a negative probe also names an
# ``effects_identity`` -- the identity the policy accepts, the allowed probe's
# own -- which the capture and the comparator take the before/after read-backs
# as. Where no declared identity holds the role there is none to take them,
# and the ``auth-effects`` gap says so instead of stating a predicate nothing
# could settle.
_AUTH_INVALID = "invalid"       # the reserved --identity name: a credential declared INVALID
# the checks that judge what a request DID, carried from the base scenario to
# the allowed probe (its status is not carried: the source's actual outcome is
# what the capture records, and 201-or-not is not knowable for an identity
# nobody has run the request as yet)
_EFFECT_CHECKS = ("after_effect_status", "after_contains_body", "before_lacks_body", "creates_one_entity", "after_equals_before")
_READ_METHODS = ("GET", "HEAD", "OPTIONS")


def _identity_rows(identities: Any, roles: Any) -> tuple[list[dict[str, Any]], str, list[str]]:
    """(the seeded identities, the invalid credential reference, gaps).

    ``--identity NAME=REF`` declares which credential reference authenticates
    as which seeded identity; the reserved NAME ``invalid`` declares a
    reference the Operator states is NOT a valid credential. ``--identity-roles
    NAME=ROLE[,ROLE...]`` declares what that identity holds. Only names travel:
    a password is never read here, and never recorded anywhere."""
    refs = parse_assignments(identities, "--identity")
    declared = parse_assignments(roles, "--identity-roles")
    gaps: list[str] = []
    invalid_ref = refs.pop(_AUTH_INVALID, "")
    if _AUTH_INVALID in declared:
        gaps.append("auth-identity %s: %r is the reserved name of a credential declared INVALID; it holds no roles"
                    % (_AUTH_INVALID, _AUTH_INVALID))
        declared.pop(_AUTH_INVALID, None)
    rows: list[dict[str, Any]] = []
    for name in sorted(refs):
        held = [r.strip() for r in str(declared.pop(name, "")).split(",") if r.strip()]
        rows.append({"name": name, "credential_ref": refs[name], "roles": sorted(dict.fromkeys(held)),
                     "roles_source": "declared" if held else "", "roles_evidence": []})
    for name in sorted(declared):
        gaps.append("auth-identity %s: roles are declared for it and no --identity %s=CREDENTIAL_REF names how it authenticates" % (name, name))
    return rows, invalid_ref, gaps


def seed_identity_roles(seed: dict[str, dict[str, Any]], columns: dict[str, list[str]], foreign_keys: list[dict[str, Any]],
                        persistence: PersistenceModel, wanted: list[str]) -> tuple[dict[str, list[str]], list[str], str]:
    """({seeded identity: the roles it holds}, evidence, why-not) read from the
    source's OWN seed through the JPA identity mapping.

    The Operator declares what the seeded identities hold; the seed SAYS it,
    and a declaration the evidence contradicts is a gap rather than an oracle.
    Nothing here knows what a user table or a role table is called. The join is
    made from the policies themselves: the table carrying a column whose seeded
    values are the roles the policies accept is the role table, its single
    foreign key names the identity table, and both must be mapped by an entity
    in M1's structure model -- that mapping is what makes them the identity
    store the application reads rather than two tables that happen to match.
    The delete rules already parse this seed and these constraints; this reads
    the same parse."""
    if not wanted:
        return {}, [], "no policy states a role to look for"
    if not persistence.available:
        return {}, [], "M1's structure model was not read, so no entity maps the seeded tables"
    if not seed:
        return {}, [], "the frozen source's seed was not read"
    accepted: set[str] = set()
    for role in wanted:
        accepted |= {role, ROLE_PREFIX + role if not role.startswith(ROLE_PREFIX) else role[len(ROLE_PREFIX):]}
    for table in sorted(seed):
        cols = (seed.get(table) or {}).get("columns") or columns.get(table) or []
        for column in cols:
            values = [v for v in column_values(seed, columns, table, column) if v]
            if not values or not (set(values) & accepted):
                continue
            if not persistence.by_table.get(table):
                return {}, [], ("the roles the policies accept are seeded in %s, which no JPA entity maps; "
                                "the identity store is not derivable from it" % table)
            fks = [fk for fk in foreign_keys if fk["table"] == table]
            if len(fks) != 1:
                return {}, [], ("%s carries the seeded roles and %d foreign keys (%s); which one names the identity it "
                                "belongs to is not derivable" % (table, len(fks), ", ".join(sorted(fk_label(fk) for fk in fks)) or "none"))
            fk = fks[0]
            if not persistence.by_table.get(fk["ref_table"]):
                return {}, [], "%s references %s, which no JPA entity maps; the identity store is not derivable" % (table, fk["ref_table"])
            held: dict[str, list[str]] = {}
            for row in table_rows(seed, columns, table):
                who, role = row.get(fk["column"], ""), row.get(column, "")
                if who and role:
                    held.setdefault(who, [])
                    if role not in held[who]:
                        held[who].append(role)
            if not held:
                return {}, [], "%s.%s carries the seeded roles but no row names both an identity and a role" % (table, column)
            evidence = [
                "seed:%s.%s carries the roles the policies accept" % (table, column),
                "schema:FOREIGN KEY %s → %s.%s" % (fk_label(fk), fk["ref_table"], fk["ref_column"]),
                "structure:%s → %s (JPA identity mapping)" % (", ".join(sorted(persistence.by_table[fk["ref_table"]])), fk["ref_table"]),
                "structure:%s → %s (JPA identity mapping)" % (", ".join(sorted(persistence.by_table[table])), table),
            ]
            return {k: sorted(v) for k, v in sorted(held.items())}, evidence, ""
    return {}, [], "no seeded column carries any role the policies accept"


# The policy a source applies to a request NO annotation names, when its
# enabled configuration requires authentication for every request
# (``anyRequest().authenticated()`` on the pilot specimen). It is not read off
# a controller, because it is not written on one: the Operator declares it in
# decisions.yaml and the id says so, rather than digesting an annotation that
# does not exist. Every entry point an explicit policy already guards keeps
# that policy -- a role is more than authentication, and the probes that prove
# a role are not replaced by the probes that prove a login.
IMPLICIT_POLICY_ID = "authz:request-authenticated"
# the decided key, spelled as a reader of decisions.yaml would look it up
REQUEST_POLICY_SUBJECT = "decisions.%s.request_policy" % SECURITY_SECTION
FIXTURES_SUBJECT = "decisions.%s.fixtures" % SECURITY_SECTION


class EnabledDerivation:
    """The enabled-mode corpus: four probes per authorization policy over a
    request the disabled corpus already states."""

    def __init__(self, root: Path, base: dict[str, Any], base_sha: str, policies: dict[str, dict[str, Any]],
                 constants: dict[str, dict[str, str]], identities: list[dict[str, Any]], invalid_ref: str,
                 entry_points: list[dict[str, Any]] | None = None, request_policy: str = "") -> None:
        self.root = root
        self.base = base
        self.base_sha = base_sha
        # a copy: the implicit request policy is added to THIS map, and the
        # caller's own reading of the source's annotations stays what the
        # structure model said
        self.policies = dict(policies)
        self.constants = constants
        self.identities = identities
        self.invalid_ref = invalid_ref
        self.gaps: list[str] = []
        self.scenarios: list[dict[str, Any]] = []
        self.covered: list[dict[str, Any]] = []
        self.by_ep: dict[str, list[dict[str, Any]]] = {}
        for sc in (base.get("scenarios") or []):
            if isinstance(sc, dict):
                self.by_ep.setdefault(str(sc.get("entry_point") or ""), []).append(sc)
        # the bundle's own entry points, and the path variables the disabled
        # derivation already resolved from the source's seed: between them a
        # guarded READ has a concrete request without anything being invented
        self.eps: dict[str, dict[str, Any]] = {}
        for e in (entry_points or []):
            if isinstance(e, dict) and str(e.get("id") or ""):
                self.eps[str(e["id"])] = e
        self.path_vars: dict[str, str] = {str(k): str(v) for k, v in (base.get("path_vars") or {}).items()}
        self.guards: dict[str, list[str]] = {}
        for pid, pol in sorted(self.policies.items()):
            for eid in (pol.get("entry_points") or []):
                self.guards.setdefault(str(eid), []).append(pid)
        self.request_policy = str(request_policy or "")
        self._add_request_policy()

    def _add_request_policy(self) -> None:
        """The policy the source applies to a request no annotation names.

        ``anyRequest().authenticated()`` guards the routes that carry no
        ``@PreAuthorize`` as surely as the annotated ones -- on the pilot
        specimen the root redirect among them -- and a derivation that walks
        only the annotations leaves them unprobed, which reads at M4 as
        "nothing to prove" rather than "not measured". The Operator declares
        what the enabled configuration requires (decisions.yaml's
        ``security.request_policy``), and it is applied to every HTTP entry
        point this derivation has a request for: the ones an explicit policy
        already guards keep theirs, because a role is more than a login and
        the probes that prove it are not replaced.

        An entry point the request policy covers and NOTHING can request is
        named as a gap: absence of a probe is a claim, and the claim is that
        there is no request for it, not that the route is unguarded."""
        if self.request_policy != REQUEST_POLICY_AUTHENTICATED:
            return
        guarded = set(self.guards)
        candidates: list[str] = []
        for eid, ep in sorted(self.eps.items()):
            # an HTTP entry point, as the bundle records one; a scheduled task
            # or a message listener is not a request and has no request policy
            if str(ep.get("kind") or "") == "http" or str(ep.get("http_method") or "") or str(ep.get("http_path") or ""):
                candidates.append(eid)
        candidates += [eid for eid in sorted(self.by_ep) if eid and eid not in self.eps]
        probeable, unprobeable = [], []
        for eid in sorted(dict.fromkeys(candidates)):
            if eid in guarded:
                continue
            base, _why = self._base_for(eid)
            (probeable if base is not None else unprobeable).append(eid)
        if probeable:
            self.policies[IMPLICIT_POLICY_ID] = {
                "annotation": "", "expression": self.request_policy, "implicit": True,
                "declared_by": REQUEST_POLICY_SUBJECT, "entry_points": list(probeable), "types": [],
                "members": [], "roles": [],
            }
            for eid in probeable:
                self.guards.setdefault(eid, []).append(IMPLICIT_POLICY_ID)
        if unprobeable:
            self.gaps.append("auth-base %s: %s %s → every request, and %s has no request the disabled corpus states or this "
                             "producer can derive; %s not exercised"
                             % (IMPLICIT_POLICY_ID, REQUEST_POLICY_SUBJECT, self.request_policy,
                                ", ".join(unprobeable), "it is" if len(unprobeable) == 1 else "they are"))

    # -- helpers -----------------------------------------------------------
    def _add(self, sc: dict[str, Any]) -> None:
        if any(s["id"] == sc["id"] for s in self.scenarios):
            self.gaps.append("scenario id %s would be derived twice (entry point %s); the second is not emitted" % (sc["id"], sc["entry_point"]))
            return
        self.scenarios.append(sc)

    def _base_for(self, eid: str) -> tuple[dict[str, Any] | None, str]:
        """(the disabled-mode scenario whose request this policy is probed
        with, why-none).

        Qualified-shaped: it carries a qualification contract, so what its
        capture must show is already stated and the allowed probe can reuse
        the assertions about what the request DID. A preflight carries no
        identity by construction, and a cross-origin exchange belongs to the
        CORS oracle -- an authorization probe carrying an Origin would answer
        two questions at once and be counted for neither."""
        rows = [sc for sc in self.by_ep.get(eid, [])
                if isinstance(sc.get("qualify"), dict) and sc["qualify"]
                and str(sc.get("method") or "").upper() != "OPTIONS"
                and not any(str(k).lower() == "origin" for k in (sc.get("headers") or {}))]
        if not rows:
            # A plain read is the one guarded request the disabled corpus does
            # NOT carry: it derives no scenario for a GET (the idempotent reads
            # are captured outside the corpus), so a policy on a read used to
            # be recorded as an unexercisable base and never probed -- which is
            # exactly the authorization the enabled mode exists to prove. The
            # request is not invented: the entry point states the method and
            # the route, and the concrete path comes from the path variables
            # the disabled derivation already resolved out of the source's own
            # seed. What remains unresolvable stays the gap it was.
            return self._read_base(eid)
        rows.sort(key=lambda sc: (0 if str((sc.get("qualify") or {}).get("intent") or "positive") == "positive" else 1,
                                  len(str(sc.get("id"))), str(sc.get("id"))))
        return rows[0], ""

    _NO_BASE = ("the disabled corpus carries no qualified-shaped scenario for it that an identity may be added to "
                "(reads are captured outside the corpus and a cross-origin exchange is the CORS oracle's)")

    def _read_base(self, eid: str) -> tuple[dict[str, Any] | None, str]:
        """(a read request derived for this guarded entry point, why-none).

        The same shape the disabled derivation gives a mapping that declares no
        HTTP method: a GET of a concrete path, no body, no declared effect, no
        reset (a read changes nothing, so the state it runs against is the one
        the previous scenario left), and a contract that judges the evidence is
        usable rather than expecting a status class nobody has observed. The
        allowed probe then records what the source answers and the refusals
        expect a 4xx -- which is the whole question a policy on a read asks."""
        ep = self.eps.get(eid)
        if not isinstance(ep, dict):
            return None, self._NO_BASE
        method = str(ep.get("http_method") or "").upper()
        route = str(ep.get("http_path") or "")
        if method not in ("GET", "HEAD"):
            return None, self._NO_BASE
        if not route or "*" in route:
            return None, ("%s and its route %s is not a request (a wildcard names no concrete URL)"
                          % (self._NO_BASE, route or "(none)"))
        path, missing = route, []
        for name in re.findall(r"\{([^{}]+)\}", route):
            value = self.path_vars.get(name)
            if value is None:
                missing.append(name)
                continue
            path = path.replace("{%s}" % name, value)
        if missing or "{" in path or "}" in path:
            return None, ("%s, and its route %s cannot be made concrete: the disabled corpus resolves no value for %s"
                          % (self._NO_BASE, route, ", ".join("{%s}" % m for m in missing) or route))
        return {
            "id": "sc:read-%s" % _read_slug(path), "entry_point": eid, "method": method, "path": path,
            "headers": {}, "identity": {"kind": "none"}, "body_absent": True, "reset_before": False,
            "effects": [], "normalization": [],
            "qualify": {"intent": "positive", "usable_first_response": True},
            # not part of any corpus: this request is derived here, and the
            # probes say so rather than citing a scenario nobody can look up
            "_derived_base": {
                "route": route,
                "evidence": ["bundle:%s %s %s (a guarded read the disabled corpus derives no scenario for)" % (eid, method, route)]
                + ["corpus:%s path variable {%s} = %s" % (_rel(self.root / CORPUS, self.root), n, self.path_vars[n])
                   for n in sorted(re.findall(r"\{([^{}]+)\}", route))],
            },
        }, ""

    def _holder(self, roles: list[str]) -> dict[str, Any] | None:
        """The declared identity that holds one of the accepted roles, fewest
        roles first: the least-privileged identity that the policy accepts
        proves the policy, and one that holds everything proves less."""
        rows = [i for i in self.identities if any(role_matches(h, r) for h in i["roles"] for r in roles)]
        rows.sort(key=lambda i: (len(i["roles"]), i["name"]))
        return rows[0] if rows else None

    def _any_identity(self) -> dict[str, Any] | None:
        """Any declared identity, fewest roles first: a policy that asks only
        for authentication is satisfied by every one of them, and the least
        privileged proves it without also proving a role."""
        rows = sorted(self.identities, key=lambda i: (len(i["roles"]), i["name"]))
        return rows[0] if rows else None

    def _outsider(self, roles: list[str]) -> dict[str, Any] | None:
        """A declared identity that is authenticated and holds NONE of the
        accepted roles. An identity whose roles nobody knows is not one: it
        may hold the role, and the scenario would expect a refusal the source
        does not give."""
        rows = [i for i in self.identities if i["roles"] and not any(role_matches(h, r) for h in i["roles"] for r in roles)]
        rows.sort(key=lambda i: (len(i["roles"]), i["name"]))
        return rows[0] if rows else None

    def _body_of(self, base: dict[str, Any]) -> tuple[str, str]:
        """(body_file, its digest) of the reused request; ("", "") when the
        request carries no body."""
        bf = str(base.get("body_file") or "")
        if not bf:
            return "", ""
        p = self.root / bf
        return bf, (sha256_file(p) if p.is_file() else "")

    def _probe(self, kind: str, slug: str, pid: str, pol: dict[str, Any], roles: list[str], eid: str,
               base: dict[str, Any], identity: dict[str, Any], who: dict[str, Any] | None,
               qualify: dict[str, Any], why: str, extra_evidence: list[str] | None = None,
               effects_who: dict[str, Any] | None = None) -> None:
        bf, body_sha = self._body_of(base)
        derived_base = base.get("_derived_base") or {}
        request_evidence = (list(derived_base.get("evidence") or []) if derived_base else
                            ["corpus:%s reused (%s %s, body %s)" % (base["id"], base["method"], base["path"], body_sha or "absent"),
                             "corpus:%s digest %s" % (_rel(self.root / CORPUS, self.root), self.base_sha)])
        # where the policy came from. An annotation says which one, on which
        # members; the request policy says which DECISION, and that it covers
        # every request -- so a reader of the scenario can tell a guard read
        # off the source's code from a guard the Operator declared.
        policy_evidence = (
            ["policy:%s %s %s → every request" % (pid, REQUEST_POLICY_SUBJECT, pol.get("expression")),
             "policy:%s any declared identity satisfies it; anonymous and invalid credentials are refused" % pid]
            if pol.get("implicit") else
            ["policy:%s @%s(%s) on %s" % (pid, pol.get("annotation"), pol.get("expression"), ", ".join(pol.get("members") or [])),
             "policy:%s accepts %s" % (pid, ", ".join(roles))])
        evidence = [
            "bundle:%s" % eid,
        ] + policy_evidence + [
            # the identity is named by what it HOLDS and by the environment
            # variable that holds its credential; never by a credential
            ("identity:%s holds %s, credential_ref %s%s"
             % (who["name"], ", ".join(who["roles"]) or "no declared role", who["credential_ref"],
                " (%s)" % who["roles_source"] if who["roles_source"] else "")
             if who else ("identity:anonymous; the request carries no credential" if str(identity.get("kind") or "none") == "none"
                          else "identity:credential_ref %s, declared invalid by the Operator" % str(identity.get("credential_ref") or ""))),
        ] + request_evidence
        if effects_who is not None:
            # WHOSE view the read-backs are. A refusal's own caller is answered
            # 401 by the effects too, and a 401 says nothing about the state,
            # so the before/after probes are taken as the identity this policy
            # ACCEPTS -- the same one the allowed probe runs as, named here by
            # what it holds and by the variable holding its credential
            evidence.append("effects-identity:%s holds %s, credential_ref %s; the before and after read-backs are taken as this "
                            "identity, so the state a refused request leaves is observable rather than another 401"
                            % (effects_who["name"], ", ".join(effects_who["roles"]) or "no declared role",
                               effects_who["credential_ref"]))
        sc: dict[str, Any] = {
            "id": "sc:auth-%s-%s" % (kind, slug), "entry_point": eid,
            "method": str(base["method"]), "path": str(base["path"]),
            "headers": {str(k): str(v) for k, v in (base.get("headers") or {}).items()},
            "identity": dict(identity),
            "reset_before": bool(base.get("reset_before", True)),
            "effects": [dict(e) for e in (base.get("effects") or [])],
            "normalization": list(base.get("normalization") or []),
            "security_mode": "enabled",
            "authorization_policy": pid,
            # where the request came from: a scenario of the disabled corpus
            # (bound by id and body digest), or this producer's own read
            # derivation for a guarded read that corpus does not carry
            "base_source": "derived-read" if derived_base else "corpus",
            "base_scenario": "" if derived_base else str(base["id"]),
            "base_route": str(derived_base.get("route") or "") if derived_base else "",
            "base_body_sha256": body_sha,
            "derived_from": {"kind": "auth-%s" % kind, "entry_point": eid, "evidence": evidence + list(extra_evidence or [])},
            "qualify": dict(qualify),
            "why": why,
        }
        if effects_who is not None:
            sc["effects_identity"] = {"kind": "basic", "credential_ref": str(effects_who["credential_ref"])}
        if bf:
            sc["body_file"] = bf
        else:
            sc["body_absent"] = True
        if kind in ("anonymous", "invalid"):
            # the challenge is part of the refusal: a source that answers 401
            # with WWW-Authenticate has stated how to authenticate, and a
            # destination that drops it has changed the behaviour. Asserted on
            # the first response only -- redirects are never followed
            sc["asserted_headers"] = [CHALLENGE_HEADER]
        self._add(sc)

    @staticmethod
    def _allowed_qualify(base: dict[str, Any]) -> dict[str, Any]:
        """The allowed identity's contract: the source's ACTUAL outcome (the
        capture records the status class it gave, nothing expects one) plus
        the base scenario's assertions about what the request did."""
        bq = base.get("qualify") or {}
        q: dict[str, Any] = {"intent": "positive", "usable_first_response": True}
        for name in _EFFECT_CHECKS:
            if name in bq:
                q[name] = json.loads(json.dumps(bq[name]))
        if "creates_one_entity" in q and "identity_field" in bq:
            q["identity_field"] = bq["identity_field"]
        return q

    @staticmethod
    def _denied_qualify(base: dict[str, Any], effects_who: dict[str, Any] | None) -> dict[str, Any]:
        """A refusal's contract: a 4xx of any kind -- 401 and 403 are both the
        source's own answer and neither is assumed -- and, for a write, the
        read-backs the base scenario declares unchanged across it.

        "Unchanged" is only a claim somebody can judge when the read-backs are
        taken as an identity the policy accepts (``effects_who``); with none
        declared they are the refused caller's own 401s, and the contract does
        not state a predicate nothing could settle -- the gap says so
        instead."""
        q: dict[str, Any] = {"intent": "negative", "expect_status_class": "4xx"}
        if base.get("effects") and str(base.get("method") or "").upper() not in _READ_METHODS and effects_who is not None:
            q["after_equals_before"] = True
        return q

    # -- CORS with security enabled (ADR-020) -------------------------------
    def _guard_identity(self, eid: str) -> tuple[dict[str, Any] | None, str]:
        """(the declared identity the entry point's guard accepts, the guard's
        policy id). An unguarded route is still asked authenticated: any
        declared identity, least privileged first."""
        for pid in self.guards.get(eid, []):
            pol = self.policies.get(pid) or {}
            if pol.get("implicit"):
                return self._any_identity(), pid
            roles, why = authorization_roles(str(pol.get("annotation") or ""), str(pol.get("expression") or ""), self.constants)
            if why or not roles:
                return None, pid
            return self._holder(roles), pid
        return self._any_identity(), ""

    def _cors_scenario(self, base: dict[str, Any], sid: str, kind: str, stype: str, identity: dict[str, Any],
                       who: dict[str, Any] | None, pid_cors: str, guard: str, why: str, qualify: dict[str, Any]) -> None:
        bf, body_sha = self._body_of(base)
        evidence = ["bundle:%s" % base["entry_point"],
                    "corpus:%s reused (%s %s, headers %s)" % (base["id"], base["method"], base["path"],
                                                             ", ".join(sorted(base.get("headers") or {}))),
                    "corpus:%s digest %s" % (_rel(self.root / CORPUS, self.root), self.base_sha),
                    "cors-policy:%s (the source's own, from the disabled corpus's cors_policies)" % pid_cors,
                    ("identity:%s holds %s, credential_ref %s" % (who["name"], ", ".join(who["roles"]) or "no declared role",
                                                                 who["credential_ref"]))
                    if who else "identity:anonymous; the request carries no credential"]
        if stype == SCENARIO_DIAGNOSTIC_PROBE:
            evidence.append("probe:an OPTIONS carrying credentials is not what a browser sends (WHATWG Fetch: a CORS preflight "
                            "never carries credentials); it is recorded and compared as a diagnostic probe and discharges "
                            "no browser-preflight coverage")
        sc: dict[str, Any] = {
            "id": sid, "entry_point": str(base["entry_point"]), "method": str(base["method"]), "path": str(base["path"]),
            "headers": {str(k): str(v) for k, v in (base.get("headers") or {}).items()},
            "identity": dict(identity), "reset_before": bool(base.get("reset_before", True)),
            "effects": [], "normalization": list(base.get("normalization") or []),
            "security_mode": "enabled", "authorization_policy": guard, "cors_policy": pid_cors,
            "scenario_type": stype,
            "base_source": "corpus", "base_scenario": str(base["id"]), "base_route": "", "base_body_sha256": body_sha,
            "derived_from": {"kind": kind, "entry_point": str(base["entry_point"]), "evidence": evidence},
            "qualify": dict(qualify), "why": why,
            # a refusal's challenge is part of the answer, and its ABSENCE on a
            # CORS answer is compared like any asserted header
            "asserted_headers": [CHALLENGE_HEADER],
        }
        if bf:
            sc["body_file"] = bf
        else:
            sc["body_absent"] = True
        self._add(sc)

    def _cors_run(self) -> None:
        """Per CORS policy the disabled corpus exercises: the browser
        preflight (no credentials), the actual request anonymous and as a
        declared identity the route's guard accepts, and an authenticated
        OPTIONS typed as a diagnostic probe. The requests are the disabled
        corpus's own; what the source answers with security ENABLED is the
        capture's to record -- a refusal is recorded as the source PREVENTING
        the browser exchange, never qualified as a permission."""
        declared = {str(p.get("id")) for p in (self.base.get("cors_policies") or []) if isinstance(p, dict)}
        by_policy: dict[str, dict[str, dict[str, Any]]] = {}
        for sc in (self.base.get("scenarios") or []):
            if not isinstance(sc, dict) or not str(sc.get("cors_policy") or ""):
                continue
            kind = str((sc.get("derived_from") or {}).get("kind") or "")
            if kind in ("cors-actual", "cors-preflight"):
                by_policy.setdefault(str(sc["cors_policy"]), {}).setdefault(kind, sc)
        observed = {"intent": "observed", "usable_first_response": True, "cors_browser_access": True}
        for pid in sorted(declared):
            short = _short(pid)
            have = by_policy.get(pid, {})
            pre, actual = have.get("cors-preflight"), have.get("cors-actual")
            if pre is None:
                self.gaps.append("cors-enabled %s: the disabled corpus carries no preflight for it; no enabled preflight or "
                                 "diagnostic probe is derived" % pid)
            else:
                self._cors_scenario(pre, "sc:cors-enabled-preflight-%s" % short, "cors-enabled-preflight",
                                    SCENARIO_BROWSER_PREFLIGHT, {"kind": "none"}, None, pid, "",
                                    "the browser preflight of %s with security enabled -- no credentials, as a browser sends "
                                    "it; whether the source permits the method and headers is what the capture records" % pid,
                                    observed)
                who, guard = self._guard_identity(str(pre["entry_point"]))
                if who is None:
                    self.gaps.append("cors-enabled %s: no declared identity is accepted by %s; the authenticated diagnostic "
                                     "probe is not derived" % (pid, guard or "the route"))
                else:
                    self._cors_scenario(pre, "sc:cors-enabled-probe-authenticated-%s" % short, "cors-diagnostic-probe",
                                        SCENARIO_DIAGNOSTIC_PROBE,
                                        {"kind": "basic", "credential_ref": who["credential_ref"]}, who, pid, guard,
                                        "a DIAGNOSTIC authenticated OPTIONS for %s: recorded and compared, never browser-"
                                        "preflight coverage" % pid,
                                        {"intent": "observed", "usable_first_response": True})
            if actual is None:
                self.gaps.append("cors-enabled %s: the disabled corpus carries no actual cross-origin request for it; none is "
                                 "derived" % pid)
                continue
            self._cors_scenario(actual, "sc:cors-enabled-actual-anonymous-%s" % short, "cors-enabled-actual-anonymous",
                                SCENARIO_CORS_ACTUAL, {"kind": "none"}, None, pid, "",
                                "the actual cross-origin request of %s with security enabled and no credentials" % pid, observed)
            who, guard = self._guard_identity(str(actual["entry_point"]))
            if who is None:
                self.gaps.append("cors-enabled %s: no declared identity is accepted by %s; the authenticated actual request is "
                                 "not derived and the policy's authenticated behaviour stays unmeasured" % (pid, guard or "the route"))
                continue
            self._cors_scenario(actual, "sc:cors-enabled-actual-authenticated-%s" % short, "cors-enabled-actual-authenticated",
                                SCENARIO_CORS_ACTUAL, {"kind": "basic", "credential_ref": who["credential_ref"]}, who, pid,
                                guard, "the actual cross-origin request of %s as a declared identity %s accepts: the "
                                "permission and exposure headers of the authenticated answer" % (pid, guard or "the route"),
                                observed)

    # -- the rule ----------------------------------------------------------
    def run(self) -> None:
        self._cors_run()
        for pid, pol in sorted(self.policies.items()):
            expression = str(pol.get("expression") or "")
            # how each role NAME was arrived at travels with every scenario the
            # policy derives: a role read out of a constant is a claim about
            # the source's own code, and the scenario has to say which type,
            # which stereotype made it a bean, and which model carried the value
            constant_evidence: list[str] = []
            if pol.get("implicit"):
                # the declared request policy names no role: it is satisfied
                # by authenticating at all, so there is no expression to read
                # and no constant to resolve
                roles, why = [], ""
                if not self.identities:
                    self.gaps.append("auth-allowed %s: %s %s accepts any declared identity and none is declared; no scenario "
                                     "is derived for the entry points no annotation guards"
                                     % (pid, REQUEST_POLICY_SUBJECT, expression))
                    continue
            else:
                roles, why = authorization_roles(str(pol.get("annotation") or ""), expression, self.constants, constant_evidence)
                if why or not roles:
                    self.gaps.append("auth-policy %s: not in the supported grammar (%s); no scenario is derived for %s"
                                     % (expression or "(empty)", why or "it names no role", pid))
                    continue
            for eid in sorted(str(e) for e in (pol.get("entry_points") or [])):
                base, none_why = self._base_for(eid)
                if base is None:
                    self.gaps.append("auth-base %s %s: %s; the policy is not exercised" % (pid, eid, none_why))
                    continue
                slug = str(base["id"]).split(":", 1)[-1]
                if len(self.guards.get(eid, [])) > 1:
                    slug = "%s-%s" % (slug, _short(pid))
                self._policy_probes(pid, pol, roles, eid, base, slug, constant_evidence)
            if not (pol.get("entry_points") or []):
                self.gaps.append("auth-base %s: the policy guards no entry point the evidence bundle records; it is not exercised" % pid)
        self.scenarios.sort(key=lambda s: str(s["id"]))
        # a policy guarding two entry points states its blockers once: the
        # missing identity is the policy's, not each request's
        self.gaps = list(dict.fromkeys(self.gaps))

    def _policy_probes(self, pid: str, pol: dict[str, Any], roles: list[str], eid: str,
                       base: dict[str, Any], slug: str, constant_evidence: list[str] | None = None) -> None:
        constant_evidence = list(constant_evidence or [])
        implicit = bool(pol.get("implicit"))
        derived_base = bool(base.get("_derived_base"))
        # what the probes are "the same request as": a scenario the Operator
        # can look up in the disabled corpus, or the read this producer
        # derived for a guarded entry point that corpus states nothing about
        whence = ("the read %s %s derived for %s" % (base["method"], base["path"], eid) if derived_base
                  else str(base["id"]))
        # what the policy ACCEPTS, in the words the probes are explained with:
        # a role set, or authentication itself
        accepts = ", ".join(roles) if roles else str(pol.get("expression") or REQUEST_POLICY_AUTHENTICATED)
        self.covered.append({"policy": pid, "entry_point": eid, "base_scenario": "" if derived_base else str(base["id"]),
                             "base_source": "derived-read" if derived_base else "corpus",
                             "base_request": "%s %s" % (base["method"], base["path"]), "roles": list(roles)})
        # who proves the policy: the least-privileged identity it accepts, and
        # -- for a policy that asks only for authentication -- any declared
        # identity, the least privileged of them for the same reason
        allowed = self._any_identity() if implicit else self._holder(roles)
        if allowed is None:
            self.gaps.append("auth-allowed %s: no declared identity holds %s; declare one (--identity NAME=CREDENTIAL_REF with "
                             "--identity-roles NAME=%s) or record the blocker" % (pid, ", ".join(roles), roles[0]))
        else:
            self._probe("allowed", slug, pid, pol, roles, eid, base,
                        {"kind": "basic", "credential_ref": allowed["credential_ref"]}, allowed,
                        self._allowed_qualify(base),
                        "the same request as %s, carrying an identity the policy accepts; what the source answers IS the "
                        "expectation -- the capture records it -- and what the request did is judged the way %s judges it"
                        % (whence, whence),
                        constant_evidence + list(allowed.get("roles_evidence") or []))
        # WHO reads the state back after a refusal. The refused caller cannot:
        # the effect probes carry its identity too, so an anonymous DELETE's
        # before and after read-backs are two more 401s and "unchanged" is not
        # judgeable (v9, 2026-09-14: 15 negative scenarios INCONCLUSIVE on
        # exactly that). The identity the policy ACCEPTS -- the allowed
        # probe's own -- takes them instead. With none declared the read-backs
        # stay the refused caller's, and the gap says so rather than the
        # contract stating a predicate nothing can settle.
        effects_who = allowed if (allowed is not None and base.get("effects")) else None
        if effects_who is None and base.get("effects") and str(base.get("method") or "").upper() not in _READ_METHODS:
            self.gaps.append("auth-effects %s %s: a refused write's read-backs are taken with the refusing request's own identity, which "
                             "shows the state as that caller sees it, and no declared identity holds %s to take them instead; the state "
                             "this policy's refusals leave is not observable and no after_equals_before is derived"
                             % (pid, eid, ", ".join(roles)))
        self._probe("anonymous", slug, pid, pol, roles, eid, base, {"kind": "none"}, None,
                    self._denied_qualify(base, effects_who),
                    "the same request with no credential at all: the policy accepts %s, so the source refuses it (any 4xx -- "
                    "401 and 403 are both its own answer), sends its challenge if it has one, and the read-backs the base "
                    "scenario declares are unchanged across it" % accepts, constant_evidence,
                    effects_who=effects_who)
        if not self.invalid_ref:
            self.gaps.append("auth-invalid %s: no credential is declared invalid (--identity %s=CREDENTIAL_REF); the invalid-credential "
                             "probe is not derived" % (pid, _AUTH_INVALID))
        else:
            self._probe("invalid", slug, pid, pol, roles, eid, base,
                        {"kind": "basic", "credential_ref": self.invalid_ref}, None,
                        self._denied_qualify(base, effects_who),
                        "the same request carrying the credential reference the Operator declares invalid: the source refuses it "
                        "(any 4xx), sends its challenge if it has one, and the read-backs are unchanged across it",
                        constant_evidence, effects_who=effects_who)
        if implicit:
            # there is no identity that authenticates and still fails a policy
            # whose whole requirement is authentication: the "authenticated
            # without the role" probe has no subject here, and inventing one
            # would expect a refusal nobody gives
            return
        outsider = self._outsider(roles)
        if outsider is None:
            # ADR-014's blocker: an identity that lacks the role is a FIXTURE.
            # Inventing one would be manufacturing a privileged identity's
            # opposite -- an account the source does not have -- and the
            # refusal it expects would be nobody's behaviour
            self.gaps.append("auth-norole %s: no declared identity lacks %s; the seed provides none" % (pid, ", ".join(roles)))
            return
        self._probe("norole", slug, pid, pol, roles, eid, base,
                    {"kind": "basic", "credential_ref": outsider["credential_ref"]}, outsider,
                    self._denied_qualify(base, effects_who),
                    "the same request carrying an authenticated identity that holds %s and none of %s: authentication is not "
                    "authorization, so the source refuses it (any 4xx) and the read-backs are unchanged across it"
                    % (", ".join(outsider["roles"]), ", ".join(roles)),
                    constant_evidence + list(outsider.get("roles_evidence") or []),
                    effects_who=effects_who)


def _sql_evidence(root: Path, copy: Path, inputs: dict[str, Any], gaps: list[str]) -> tuple[
        str, str, str, Path | None, dict[str, dict[str, Any]], dict[str, list[str]], list[dict[str, Any]]]:
    """(source engine, destination engine, the engine the seed was read from,
    the seed file, the seeded rows, the schema's columns, its foreign keys).

    The frozen source's own SQL, read once for whichever mode is being
    derived: the disabled corpus addresses seeded rows with it, and the
    enabled corpus reads the seeded identities' roles out of the same parse.
    Which files were read is recorded on the receipt (``inputs.sql``): a
    missing schema is why a decision was made blind."""
    src_engine, dest_engine = _decided_engines(root)
    seed_p, engine = find_seed(copy, src_engine)
    seed: dict[str, dict[str, Any]] = {}
    columns: dict[str, list[str]] = {}
    foreign_keys: list[dict[str, Any]] = []
    sql_read: list[dict[str, str]] = []
    if seed_p is None:
        gaps.append("no seed file src/main/resources/db/<engine>/populateDB.sql under the frozen source; path variables and seeded rows cannot be named")
        inputs["seed"] = {"path": "", "sha256": ""}
    else:
        inputs["seed"] = _input(seed_p, copy)
        sql_read.append(inputs["seed"])
        seed = parse_seed(seed_p.read_text(encoding="utf-8", errors="replace"))
        schema_files = find_schema_sql(seed_p)
        if not schema_files:
            gaps.append("no schema file declaring CREATE TABLE beside %s; the seed's foreign keys are unknown and a delete cannot avoid a referenced row"
                        % _rel(seed_p, copy))
        for schema_p in schema_files:
            text = schema_p.read_text(encoding="utf-8", errors="replace")
            sql_read.append(_input(schema_p, copy))
            columns.update(parse_schema_columns(text))
            foreign_keys.extend(parse_foreign_keys(text))
        if schema_files:
            inputs["schema"] = _input(schema_files[0], copy)
    # which SQL the derivation actually read is part of the audit trail: a
    # missing schema file is why a delete was derived blind
    inputs["sql"] = sql_read
    return src_engine, dest_engine, engine, seed_p, seed, columns, foreign_keys


def _from_decisions(args: Any, mode: str) -> bool:
    """Whether the identities come from ``decisions.yaml``.

    The decided file is the DEFAULT for the enabled mode: a run nobody gave
    identities on the command line reads the ones an ADR backs, rather than
    deriving a corpus with no identity at all and calling the result a
    blocker. ``--identity`` is still honoured, for a fixture and for the
    Operator working one policy at a time."""
    if mode == DEFAULT_SECURITY_MODE:
        return False
    if getattr(args, "from_decisions", False):
        return True
    return not (getattr(args, "identity", None) or getattr(args, "identity_roles", None))


def decided_identities(root: Path) -> tuple[list[dict[str, Any]], str, dict[str, str], str]:
    """(the identity rows, the invalid credential reference, the security
    switch, why-not) from ``decisions.yaml``.

    Who the enabled mode authenticates as is a DECISION the Operator records
    and an ADR backs, not an argument typed at a shell: an identity on a
    command line is not reviewable, does not survive the run and binds to
    nothing. Only names travel here either -- ``credential_ref`` is the NAME of
    an environment variable, and the loader refuses one that looks like the
    credential itself.

    A missing section is a REASON, not an empty answer: the caller records it
    and does nothing, which is ADR-014's recorded blocker rather than a corpus
    derived as though the source had no security."""
    try:
        doc = load_decisions(root)
    except (DecisionsError, OSError) as exc:
        return [], "", {}, str(exc)
    decided = security(doc)
    if not decided:
        refusals = security_gaps(doc)
        if refusals:
            return [], "", {}, ("%s declares a security section this loader refuses: %s"
                                % (DECISIONS.as_posix(), "; ".join("%s %s" % (g["subject"], g["detail"]) for g in refusals)))
        return [], "", {}, ("%s declares no security section (ADR-014: the switch, the seeded identities and the credential "
                            "REFERENCES the enabled mode authenticates with)" % DECISIONS.as_posix())
    rows = [{"name": str(i["name"]), "credential_ref": str(i["credential_ref"]),
             "roles": sorted(dict.fromkeys(str(r) for r in (i.get("roles") or []) if str(r).strip())),
             "roles_source": "declared" if i.get("roles") else "", "roles_evidence": []}
            for i in decided["identities"]]
    rows.sort(key=lambda r: r["name"])
    return rows, str(decided.get("invalid_credential_ref") or ""), dict(decided["switch"]), ""


def decided_request_policy(root: Path) -> tuple[str, str]:
    """(what the source's enabled configuration requires of a request no
    annotation names, why-none).

    Read from the decided file whichever way the identities arrived: it is a
    fact about the SOURCE's own configuration, not about who a run
    authenticates as. Not declared is a reason the receipt carries, never a
    silence -- "the unannotated routes were not probed" and "the Operator
    declared they need no identity" are different claims."""
    try:
        doc = load_decisions(root)
    except (DecisionsError, OSError) as exc:
        return "", str(exc)
    decided = security(doc)
    if not decided:
        return "", ("%s declares no usable security section, so what its enabled configuration requires of an unannotated "
                    "route is not declared" % DECISIONS.as_posix())
    policy = str(decided.get("request_policy") or "")
    if not policy:
        return "", ("%s declares no security.request_policy; only the entry points an annotation guards are probed, and the "
                    "unannotated ones are neither probed nor claimed" % DECISIONS.as_posix())
    return policy, ""


def decided_fixtures(root: Path) -> tuple[list[dict[str, Any]], str]:
    """(the declared fixture variants of the source baseline, why-none).

    A variant is a database state the declared dataset does not have, and the
    statements that reach it are the Operator's -- opaque SQL here, applied
    after the declared dataset and never instead of it."""
    try:
        doc = load_decisions(root)
    except (DecisionsError, OSError) as exc:
        return [], str(exc)
    decided = security(doc)
    if not decided:
        refusals = security_gaps(doc)
        if refusals:
            return [], ("%s declares a security section this loader refuses: %s"
                        % (DECISIONS.as_posix(), "; ".join("%s %s" % (g["subject"], g["detail"]) for g in refusals)))
        return [], "%s declares no security section, so it declares no fixture variant" % DECISIONS.as_posix()
    rows = list(decided.get("fixtures") or [])
    if not rows:
        return [], ("%s declares no security.fixtures; a variant of the source baseline is recorded only where the Operator "
                    "declares one" % DECISIONS.as_posix())
    return rows, ""


SOURCE_JAVA = "src/main/java"


def _source_classpath(root: Path) -> Path | None:
    """The FROZEN source's own build classpath, or None.

    Discovered the way the structural extractor discovers it: the build
    producer's receipt says whether packaging the source produced one, and the
    file is where that producer wrote it. None is not a failure -- a literal
    initializer needs no classpath -- and it is never silently replaced by the
    destination's, which is a different tree's dependencies."""
    receipt = producer_receipt(root, "build")
    cp = Path(root) / "evidence" / "build" / "classpath.txt"
    if not receipt.is_file():
        return None
    try:
        available = bool(load_json(receipt).get("classpath_available"))
    except (OSError, ValueError):
        return None
    return cp if available and cp.is_file() and cp.stat().st_size else None


def _resolve_constants(root: Path, copy: Path, policies: dict[str, Any], constants: dict[str, Any],
                       inputs: dict[str, Any], gaps: list[str]) -> dict[str, Any]:
    """The constants catalog the policies are read with: M1's sealed model,
    and -- only for what it does not carry -- the FROZEN SOURCE itself.

    A structure model sealed before the extractor recorded field initializers
    states the constants type and its fields with no value, so
    ``hasRole(@roles.VET_ADMIN)`` resolves to nothing and the whole enabled
    corpus is gaps (measured on destination v9, 2026-09-15: 0 scenarios, 4
    ``not in the supported grammar``). The frozen tree that model was made
    from is still on disk, and a literal initializer is readable from it
    without any classpath. So it is compiled and asked -- but only when a
    policy actually needs a constant the sealed model lacks, and the sealed
    model keeps precedence wherever it has a value: this is a fallback for
    older runs, never a second opinion about a sealed claim.

    The run is recorded on the receipt (``inputs.constants``): the tool, the
    sources it read and their digest, the model's digest, and which fields it
    answered for."""
    wanted: list[str] = []
    for _pid, pol in sorted(policies.items()):
        for tok in role_reference_tokens(str(pol.get("annotation") or ""), str(pol.get("expression") or "")):
            if resolve_role_constant(tok, constants)[1] and tok not in wanted:
                wanted.append(tok)
    if not wanted:
        return constants
    record: dict[str, Any] = {
        "tool": "jdk-dest-model", "tree": _rel(copy, root), "source_root": SOURCE_JAVA,
        "requested": list(wanted), "resolved": [], "source_digest": "", "model_sha256": "",
        "classpath": "", "resolution": "", "status": "", "reason": "",
    }
    classpath = _source_classpath(root)
    try:
        model = tree_model(root, copy, source_root=SOURCE_JAVA, classpath=classpath)
    except DestModelUnavailable as exc:
        record["status"] = "unavailable"
        record["reason"] = str(exc)
        inputs["constants"] = record
        gaps.append("auth-constants: the frozen source's own model could not be produced (%s); a constant M1's sealed "
                    "structure model does not carry cannot be resolved" % exc)
        return constants
    merged = merge_role_constants(constants, role_constants_from_model(model, FROZEN_SOURCE_MODEL))
    record["status"] = "ok"
    record["classpath"] = _rel(classpath, root) if classpath is not None else ""
    record["resolution"] = "full" if model.get("classpath_available") else "partial"
    record["source_digest"] = str(model.get("sources_digest") or "")
    record["model_sha256"] = digest(model.get("types") or [])
    record["resolved"] = sorted({tok for tok in wanted if not resolve_role_constant(tok, merged)[1]})
    inputs["constants"] = record
    return merged


def _derive_enabled(root: Path, args: Any, mode: str, out_p: Path, receipt_p: Path, bundle_sha: str,
                    freeze: dict[str, Any], copy: Path, inputs: dict[str, Any], gaps: list[str], blocked: Any,
                    idle: Any = None) -> int:
    """The enabled-mode corpus (ADR-014): the authorization probes.

    Refuses when the evidence the probes are made of is absent -- the
    source's policies, or the disabled corpus whose requests they reuse. What
    is merely UNDECLARED (an identity holding the role, one lacking it, a
    credential that is invalid) is a typed gap and no scenario, which is the
    blocker ADR-014 asks for rather than a manufactured identity."""
    structure_p = root / STRUCTURE
    inputs["structure"] = _input(structure_p, root)
    policies, policy_gap = source_authorization_policy_map(root)
    if policy_gap:
        return blocked("the source's authorization policies are unknown: %s; an enabled-mode corpus is derived per policy" % policy_gap)
    constants, constants_gap = source_role_constants(root)
    if constants_gap:
        gaps.append("auth-constants: %s; an expression naming a constant cannot be read" % constants_gap)
    try:
        base = load_corpus(root)
    except CorpusError as exc:
        return blocked("the %s corpus is what the enabled probes reuse their requests from, and it does not hold: %s"
                       % (DEFAULT_SECURITY_MODE, exc))
    base_sha = corpus_digest(base)
    inputs["base_corpus"] = {"path": CORPUS.as_posix(), "sha256": base_sha}
    switch: dict[str, str] = {}
    if _from_decisions(args, mode):
        identities, invalid_ref, switch, why = decided_identities(root)
        if why:
            # nothing is derived, and the receipt SAYS what is missing: a
            # fixture nobody declared is a recorded blocker (ADR-014), never
            # an invented identity and never silence
            return (idle or blocked)("no enabled-mode scenario is derived: %s" % why)
        identities_from = DECISIONS.as_posix()
    else:
        try:
            identities, invalid_ref, identity_gaps = _identity_rows(args.identity, args.identity_roles)
        except CorpusError as exc:
            print("REFUSE: DERIVE_SCENARIOS %s" % exc, file=sys.stderr)
            return 2
        gaps.extend(identity_gaps)
        identities_from = "--identity"
    # what the SEED says the identities hold. The roles the policies accept
    # are what the identity store is found by, so the expressions are read
    # first -- an unreadable one is a gap of its own below, at the policy
    _, _, _, _, seed, columns, foreign_keys = _sql_evidence(root, copy, inputs, gaps)
    persistence = load_persistence_model(root, set(columns) | set(seed))
    # a constant a policy names and the sealed model does not carry is read
    # from the frozen source itself, and the receipt says it was. Asked here,
    # where the first answer is needed: a run that derives nothing does not
    # compile another tree to find out.
    constants = _resolve_constants(root, copy, policies, constants, inputs, gaps)
    wanted: list[str] = []
    for pol in policies.values():
        roles, _why = authorization_roles(str(pol.get("annotation") or ""), str(pol.get("expression") or ""), constants)
        wanted.extend(roles)
    seeded, seed_evidence, seed_why = seed_identity_roles(seed, columns, foreign_keys, persistence, sorted(set(wanted)))
    for row in identities:
        derived = seeded.get(row["name"]) or []
        if derived and row["roles"] and sorted(row["roles"]) != sorted(derived):
            gaps.append("auth-identity %s: the Operator declares %s and the seed gives %s; the seed is the evidence and is used"
                        % (row["name"], ", ".join(row["roles"]), ", ".join(derived)))
        if derived:
            row["roles"] = list(derived)
            row["roles_source"] = "declared and seeded" if row["roles_source"] else "from the seed"
            row["roles_evidence"] = list(seed_evidence)
        elif not row["roles"]:
            gaps.append("auth-roles %s: no roles are declared for it (--identity-roles %s=ROLE) and none are derivable from the seed (%s); "
                        "it is used for no probe" % (row["name"], row["name"], seed_why or "it names no seeded identity"))
    bundle_eps = [e for e in (load_json(root / EVIDENCE_BUNDLE).get("entry_points") or []) if isinstance(e, dict)]
    # what the source's enabled configuration requires of a request no
    # annotation names. It is a property of the SOURCE, so it is read from the
    # decided file whichever way the identities arrived -- and a tree that
    # declares none derives exactly what it derived before.
    request_policy, request_policy_why = decided_request_policy(root)
    d = EnabledDerivation(root, base, base_sha, policies, constants, identities, invalid_ref, entry_points=bundle_eps,
                          request_policy=request_policy)
    d.run()
    gaps.extend(d.gaps)
    policies = d.policies
    doc = {
        "schema": SCHEMA,
        "security_mode": mode,
        "derived_from": {
            "producer": PRODUCER, "evidence_bundle_sha256": bundle_sha,
            "source_digest": str(freeze.get("source_digest") or ""),
            "security_mode": mode,
            "base_corpus": dict(inputs["base_corpus"]),
            "structure_sha256": inputs["structure"]["sha256"],
        },
        "initial_state": dict(base.get("initial_state") or {}),
        "path_vars": dict(base.get("path_vars") or {}),
        # the source's own CORS policies, exercised here with security
        # enabled (ADR-020) by the cors-enabled scenarios
        "cors_policies": [dict(p) for p in (base.get("cors_policies") or []) if isinstance(p, dict)],
        "identities": [{"name": i["name"], "credential_ref": i["credential_ref"], "roles": list(i["roles"]),
                        "roles_source": i["roles_source"]} for i in identities],
        "identities_from": identities_from,
        "invalid_credential_ref": invalid_ref,
        # the specimen's own switch, as the Operator decided it: a property
        # KEY and the value that names its enabled setting, so the capture
        # starts the source the way this corpus was derived for
        "security_switch": dict(switch),
        # what the enabled configuration requires of a request no annotation
        # names, and -- when nothing declares it -- why nothing was applied.
        # "not declared" and "declared and applied" must not look alike.
        "request_policy": request_policy,
        "request_policy_note": request_policy_why if not request_policy else "",
        "authorization_policies": [
            {"id": pid, "annotation": pol.get("annotation"), "expression": pol.get("expression"),
             "declared_by": str(pol.get("declared_by") or ""),
             "roles": ([] if pol.get("implicit") else
                       authorization_roles(str(pol.get("annotation") or ""), str(pol.get("expression") or ""), constants)[0]),
             "entry_points": list(pol.get("entry_points") or []), "members": list(pol.get("members") or [])}
            for pid, pol in sorted(policies.items())],
        "scenarios": d.scenarios,
        "gaps": gaps,
    }
    corpus_sha = corpus_digest(doc)
    write_canonical(out_p, doc)
    bodies = {str(s["body_file"]): sha256_file(root / str(s["body_file"])) for s in d.scenarios if s.get("body_file")}
    requests = {str(s["id"]): request_of(root, s)["request_sha256"] for s in d.scenarios}
    write_canonical(receipt_p, {
        "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "ok", "reason": "",
        "security_mode": mode,
        "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha, "corpus": _rel(out_p, root),
        "base_corpus": dict(inputs["base_corpus"]),
        # the credentials are REFERENCES: which variable holds which identity's
        # credential, never what it holds
        "identities": [{"name": i["name"], "credential_ref": i["credential_ref"], "roles": list(i["roles"]),
                        "roles_source": i["roles_source"]} for i in identities],
        "identities_from": identities_from, "security_switch": dict(switch),
        "invalid_credential_ref": invalid_ref,
        "request_policy": request_policy, "request_policy_note": request_policy_why if not request_policy else "",
        "seed_identity_roles": {k: list(v) for k, v in sorted(seeded.items())},
        "seed_identity_roles_evidence": list(seed_evidence), "seed_identity_roles_gap": seed_why,
        "authorization_policies": [row["id"] for row in doc["authorization_policies"]],
        "covered": d.covered,
        "inputs": inputs, "origin": args.origin,
        "scenarios": [str(s["id"]) for s in d.scenarios], "bodies": bodies, "requests": requests, "gaps": gaps,
    })
    print("OK: derived %d %s-mode scenario(s) over %d policy(ies), %d gap(s) (corpus %s, base %s) → %s"
          % (len(d.scenarios), mode, len(policies), len(gaps), corpus_sha[:12], base_sha[:12], _rel(out_p, root)))
    for g in gaps:
        print("  - gap: %s" % g)
    return 0


def _variant_reader(base: dict[str, Any], identities: list[dict[str, Any]], invalid_ref: str) -> tuple[dict[str, Any] | None, str]:
    """(the declared identity a refused write's read-backs are taken as, why-none).

    A refuse-intent variant refuses the base request's OWN identity -- that is
    what the Operator declared it for -- so the read-backs cannot be taken as
    that identity: under the variant they are refused too, and two refusals
    prove nothing about the state. They are taken as another DECLARED
    identity instead: a different credential reference, not the one declared
    invalid, holding every role the refused identity holds (the read-backs
    answered it on the baseline, so an identity holding at least as much is
    answered too). Fewest roles first, then by name. The fixture's statements
    are never parsed: which identity is refused is read off the request, and
    whether the chosen reader is itself refused under the variant is what the
    capture shows -- a read-back that does not answer 2xx is unusable
    evidence at qualification, never a silent pass."""
    refused = normalized_identity(base.get("identity"))
    refused_ref = str(refused.get("credential_ref") or "")
    label = ("credential_ref %s" % refused_ref if refused_ref else
             "%s/%s" % (refused.get("user_env"), refused.get("password_env")) if refused.get("user_env") else "no credential")
    rows = [i for i in identities if isinstance(i, dict)]
    known = [i for i in rows if refused_ref and str(i.get("credential_ref") or "") == refused_ref]
    needed = sorted(dict.fromkeys(str(r) for r in (known[0].get("roles") or []))) if known else []
    if refused_ref and not known:
        return None, ("the refused request authenticates as %s, which no declared identity names, so the roles its read-backs "
                      "need are not known" % label)
    candidates = [i for i in rows
                  if str(i.get("credential_ref") or "")
                  and normalized_identity({"kind": "basic", "credential_ref": i["credential_ref"]}) != refused
                  and str(i.get("credential_ref")) != invalid_ref
                  and all(any(role_matches(h, r) for h in (i.get("roles") or [])) for r in needed)]
    candidates.sort(key=lambda i: (len(i.get("roles") or []), str(i.get("name") or "")))
    if not candidates:
        return None, ("missing effects identity: decisions.%s.identities declares no identity other than %s (the one this "
                      "variant refuses)%s; declare one -- and make it exist, enabled, in the variant's dataset -- so the refused "
                      "write's read-backs can be taken as an identity the variant does not refuse"
                      % (SECURITY_SECTION, label, " that holds %s" % ", ".join(needed) if needed else ""))
    return candidates[0], ""


EFFECTS_SECOND_IDENTITY = "second_identity"
EFFECTS_REVERT_THEN_READ = _variant_revert.STRATEGY


def _variant_revert_plan(fixture: dict[str, Any], seed_p: Path | None, dataset: dict[str, str]) -> tuple[dict[str, Any] | None, str]:
    """(the computed revert of the fixture's statements, why-not). Computed
    only from single-column UPDATEs over the declared dataset the variant is
    applied after; everything else is a typed reason (_variant_revert)."""
    if seed_p is None:
        return None, "the declared dataset is not in the frozen source, so no baseline value is known"
    schema_text = "".join(p.read_text(encoding="utf-8", errors="replace") for p in find_schema_sql(seed_p))
    try:
        return _variant_revert.compute_plan([str(s) for s in (fixture.get("statements") or [])],
                                            seed_p.read_text(encoding="utf-8", errors="replace"), schema_text,
                                            dict(dataset)), ""
    except _variant_revert.RevertRefusal as exc:
        return None, "REVERT_NOT_COMPUTABLE: %s" % exc


def effect_db_scope(base: dict[str, Any], reads: list[dict[str, Any]], columns: dict[str, list[str]],
                    foreign_keys: list[dict[str, Any]], eps: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The database state a refused write's no-effect claim covers (ADR-021),
    derived from what the scenario already reads: the tables its entry
    point's route and its effect reads name (the same singular/plural
    tolerance the path-variable mapping uses, against the source schema's
    own tables), and every table whose foreign key references one of them --
    the relationships a write could change. The definition travels with the
    scenario; an empty scope is a reason, never an empty claim."""
    tables = set(columns)
    found: dict[str, str] = {}
    ep = eps.get(str(base.get("entry_point") or "")) or {}
    route = str(ep.get("http_path") or "")
    for var in re.findall(r"\{([^{}]+)\}", route):
        for cand in table_candidates(var, route):
            if cand in tables:
                found.setdefault(cand, "route %s {%s}" % (route, var))
                break
    for e in reads:
        path = str(e.get("path") or "")
        for seg in [x for x in path.split("/") if x and not x.isdigit()]:
            for cand in dict.fromkeys([seg.lower(), _snake(seg), _plural(seg.lower()), _singular(seg.lower())]):
                if cand in tables:
                    found.setdefault(cand, "read %s %s" % (e.get("id"), path))
                    break
    if not found:
        return {"tables": [], "why": ("no table of the source schema is named by %s's route or its read-backs; the "
                                      "database state its refusal leaves is not scoped" % base.get("id"))}
    related = {fk["table"]: "foreign key %s → %s" % (fk["table"], fk["ref_table"])
               for fk in foreign_keys if fk.get("ref_table") in found and fk.get("table") in tables}
    evidence = ["scope:%s (%s)" % (t, found[t]) for t in sorted(found)]
    evidence += ["scope:%s (%s)" % (t, related[t]) for t in sorted(related) if t not in found]
    return {"tables": sorted(set(found) | set(related)), "evidence": evidence,
            "rule": ("the tables the entry point's route and the scenario's read-backs name in the source schema, and every "
                     "table whose foreign key references one of them")}


def _variant_scenario(root: Path, variant: str, fixture: dict[str, Any], base: dict[str, Any], base_sha: str,
                      base_corpus_rel: str, dataset: dict[str, str], identities: list[dict[str, Any]] | None = None,
                      invalid_ref: str = "", gaps: list[str] | None = None, revert: dict[str, Any] | None = None,
                      revert_why: str = "no revert was computed", db_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """One scenario of a fixture variant: the base scenario's request, sent
    against the varied dataset.

    The REQUEST is untouched -- same method, path, headers, identity and
    bytes -- because a difference in the answer is then the fixture and
    nothing else, exactly the way the enabled mode reuses the disabled
    corpus's requests. What it expects is what the Operator declared: a 4xx
    when the variant's declared intent is a refusal, and otherwise a usable
    first response, because an expectation nobody declared is not invented.

    The base's effect ASSERTIONS do not travel: they judge what the request
    did under the baseline. Its effect READ REQUESTS do, for a refused write
    (ADR-018: the account-status exit is measured, not waived): an identical
    4xx does not show the write did not happen. Two ways to read the state,
    recorded on ``effects_reader.strategy``:

    - ``second_identity``: a declared identity the variant does not refuse
      (``_variant_reader``) takes the reads before and after the request,
      under the variant; the contract is that they are equal.
    - ``revert_then_read`` (when no such identity is declared -- a second
      fixture identity would be an invented one): the reads are taken as the
      base identity on the verified BASELINE, the variant is applied, the
      request is refused, the variant's own changes are reverted by the
      computed plan (``_variant_revert``), and the reads are taken again; the
      contract is that they equal the baseline reads the source recorded.

    Nothing here states what the reads hold -- the source capture does. With
    neither strategy available the scenario carries no read-back and says why
    (``effects_unobservable``); the comparator keeps it INCONCLUSIVE and names
    that reason."""
    refuse = str(fixture.get("intent") or "") == "refuse"
    bf = str(base.get("body_file") or "")
    p = root / bf
    body_sha = (sha256_file(p) if bf and p.is_file() else "")
    slug = str(base["id"]).split(":", 1)[-1]
    evidence = [
        "bundle:%s" % str(base.get("entry_point") or ""),
        "corpus:%s reused (%s %s, body %s)" % (base["id"], base["method"], base["path"], body_sha or "absent"),
        "corpus:%s digest %s" % (base_corpus_rel, base_sha),
        "fixture:%s %s[%s] applies %d statement(s) after the declared dataset %s (%s)"
        % (variant, FIXTURES_SUBJECT, variant, len(fixture.get("statements") or []), dataset.get("path"), dataset.get("sha256")),
        "fixture:%s the source is started with %s pointed at that variant dataset"
        % (variant, fixture.get("dataset_config_key")),
    ]
    # the statements VERBATIM: they are the fixture's own SQL, they are what
    # the variant is, and a receipt that paraphrased them could not be used
    # to reproduce the run
    evidence += ["fixture:%s statement: %s" % (variant, s) for s in (fixture.get("statements") or [])]
    evidence.append("fixture:%s intent %s" % (variant, "refuse: the source is declared to refuse these requests, so any 4xx "
                                              "is the expectation" if refuse else
                                              "(none declared): what the source answers IS the expectation, and the capture "
                                              "records it"))
    qualify: dict[str, Any] = ({"intent": "negative", "expect_status_class": "4xx"} if refuse
                               else {"intent": "positive", "usable_first_response": True})
    effects: list[dict[str, Any]] = []
    reader: dict[str, Any] | None = None
    reader_row: dict[str, Any] = {}
    unobservable = ""
    write = str(base.get("method") or "").upper() not in _READ_METHODS
    reads = [e for e in (base.get("effects") or []) if isinstance(e, dict)
             and str(e.get("method") or "GET").upper() in _READ_METHODS]
    if refuse and write:
        if not reads:
            unobservable = ("the base scenario %s declares no read-back, so what the refused write left is not observable"
                            % base["id"])
        else:
            reader, second_why = _variant_reader(base, list(identities or []), invalid_ref)
            if reader is not None:
                reader_row = {"strategy": EFFECTS_SECOND_IDENTITY, "name": str(reader.get("name") or ""),
                              "credential_ref": str(reader["credential_ref"])}
                qualify["after_equals_before"] = True
                evidence.append("effects-identity:%s holds %s, credential_ref %s; the before and after read-backs of the "
                                "refused write are taken as this identity, which the variant does not refuse, and must be "
                                "equal" % (reader.get("name"), ", ".join(reader.get("roles") or []) or "no declared role",
                                           reader["credential_ref"]))
            else:
                own = normalized_identity(base.get("identity"))
                own_ref = str(own.get("credential_ref") or "")
                if revert is not None and own_ref:
                    named = [i for i in (identities or []) if str(i.get("credential_ref") or "") == own_ref]
                    reader = {"name": str(named[0].get("name") or "") if named else "", "credential_ref": own_ref}
                    reader_row = {"strategy": EFFECTS_REVERT_THEN_READ, "name": reader["name"], "credential_ref": own_ref}
                    qualify["before_reads_usable"] = True
                    # the SOURCE's post-request state, observed after the
                    # revert of the fixture rows only, equals its baseline
                    qualify["after_equals_before"] = True
                    evidence.append("effects-identity:%s, credential_ref %s (the request's own); %s: the read-backs are "
                                    "taken on the verified baseline, the variant is applied, the request is refused, the "
                                    "variant's changes are reverted (%s) and the read-backs are taken again -- they must "
                                    "equal the baseline's" % (reader["name"] or "the base identity", own_ref,
                                                              EFFECTS_REVERT_THEN_READ,
                                                              "; ".join(revert.get("statements") or [])))
                else:
                    unobservable = "%s; and %s" % (second_why, revert_why if own_ref else
                                                   "the refused request carries no credential reference to read as after a revert")
        if reader is not None:
            # ADR-021: "unchanged" is a DATABASE claim over a declared scope,
            # read before and after the request; HTTP read-backs are kept
            # beside it and never qualify it on their own
            qualify["db_unchanged"] = True
            # the read REQUESTS only -- id, method, path -- with the role they
            # play here; what they answer is the source capture's to record
            effects = [{"id": str(e.get("id") or e.get("path")), "method": str(e.get("method") or "GET").upper(),
                        "path": str(e.get("path") or "/"), "role": EFFECT_ROLE_UNCHANGED} for e in reads]
        else:
            evidence.append("effects-unobservable:%s" % unobservable)
            if gaps is not None:
                gaps.append("fixture-effects %s %s: %s; the scenario stays INCONCLUSIVE" % (variant, base["id"], unobservable))
    sc: dict[str, Any] = {
        "id": "sc:fixture-%s-%s" % (variant, slug),
        "entry_point": str(base.get("entry_point") or ""),
        "method": str(base["method"]), "path": str(base["path"]),
        "headers": {str(k): str(v) for k, v in (base.get("headers") or {}).items()},
        "identity": dict(base.get("identity") or {"kind": "none"}),
        # ALWAYS: a variant scenario is defined by its dataset state, so it
        # starts from the variant, never from whatever the previous scenario
        # left (a revert-then-read write ends on the baseline)
        "reset_before": True,
        "effects": effects,
        "normalization": list(base.get("normalization") or []),
        "security_mode": str(base.get("security_mode") or ""),
        "security_variant": variant,
        "authorization_policy": str(base.get("authorization_policy") or ""),
        "base_source": "corpus",
        "base_scenario": str(base["id"]),
        "base_route": str(base.get("base_route") or ""),
        "base_body_sha256": body_sha,
        "derived_from": {"kind": "fixture-%s" % variant, "entry_point": str(base.get("entry_point") or ""),
                         "evidence": evidence},
        "qualify": qualify,
        "why": ("the same request as %s, against the source baseline varied by %s[%s]; %s"
                % (base["id"], FIXTURES_SUBJECT, variant,
                   "the Operator declares the source refuses it under this variant, so any 4xx is the expectation and the "
                   "challenge header is read where the source sends one" if refuse else
                   "what the source answers IS the expectation -- the capture records it")
                + ("; the read-backs the source records before and after it are unchanged" if effects else "")),
    }
    if reader is not None:
        sc["effects_identity"] = {"kind": "basic", "credential_ref": str(reader["credential_ref"])}
        sc["effects_reader"] = dict(reader_row)
        sc["effects_db_scope"] = dict(db_scope or {"tables": [], "why": "no database scope was derived"})
    if unobservable:
        sc["effects_unobservable"] = unobservable
    if refuse:
        # the same reading the other refusals get: a source that says how to
        # authenticate has stated something a destination can drop
        sc["asserted_headers"] = [CHALLENGE_HEADER]
    if bf:
        sc["body_file"] = bf
    else:
        sc["body_absent"] = True
    return sc


def _derive_variant(root: Path, args: Any, mode: str, variant: str, out_p: Path, receipt_p: Path, bundle_sha: str,
                    freeze: dict[str, Any], copy: Path, inputs: dict[str, Any], gaps: list[str], blocked: Any,
                    idle: Any) -> int:
    """A fixture variant of a mode's baseline corpus (ADR-014).

    The architect's exit asks what the source does when an identity the seed
    ENABLES is disabled -- behaviour no capture taken against the declared
    dataset can show, and not a reason to edit the dataset every other capture
    is taken against. So the variant is a separate corpus over the same
    requests: the mode's own scenarios of the declared class, each expecting
    what the Operator says the source answers under the variant, with the
    statements recorded verbatim so the run can be reproduced from the
    evidence."""
    fixtures, why = decided_fixtures(root)
    if why:
        return idle("no %s-mode fixture variant is derived: %s" % (mode, why))
    rows = [f for f in fixtures if str(f.get("name") or "") == variant]
    if not rows:
        return blocked("%s declares no security fixture named %r (it declares: %s); a variant is derived only from a "
                       "declared one" % (DECISIONS.as_posix(), variant, ", ".join(str(f.get("name")) for f in fixtures)))
    fixture = rows[0]
    try:
        base = load_corpus(root, mode)
    except CorpusError as exc:
        return blocked("the %s corpus is what a variant of that mode varies, and it does not hold: %s" % (mode, exc))
    base_sha = corpus_digest(base)
    base_corpus_rel = corpus_path(mode).as_posix()
    inputs["base_corpus"] = {"path": base_corpus_rel, "sha256": base_sha}
    wanted_class = str(fixture.get("scenarios") or "")
    selected = [sc for sc in (base.get("scenarios") or [])
                if isinstance(sc, dict) and str((sc.get("derived_from") or {}).get("kind") or "") == wanted_class]
    if not selected:
        return idle("the %s corpus carries no scenario of class %s, which is what %s[%s] varies; nothing is derived "
                    "and this receipt says so" % (mode, wanted_class, FIXTURES_SUBJECT, variant))
    # the DECLARED dataset the statements are applied after: the frozen
    # source's own seed, the same file the mode's corpus was derived from,
    # recorded with its digest so the capture builds the variant from exactly
    # the bytes this derivation saw
    _src, _dest, _engine, seed_p, _seed, _cols, _fks = _sql_evidence(root, copy, inputs, gaps)
    bundle_eps = {str(e.get("id")): e for e in (load_json(root / EVIDENCE_BUNDLE).get("entry_points") or [])
                  if isinstance(e, dict)}
    if seed_p is None:
        return blocked("the fixture's statements are applied AFTER the declared dataset, and the frozen source carries none "
                       "(no seed file was found); the variant dataset cannot be built")
    dataset = {"path": str(inputs["seed"]["path"]), "sha256": str(inputs["seed"]["sha256"])}
    base_identities = [dict(i) for i in (base.get("identities") or []) if isinstance(i, dict)]
    revert, revert_why = (_variant_revert_plan(fixture, seed_p, dataset) if str(fixture.get("intent") or "") == "refuse"
                          else (None, "the variant declares no refusal"))
    scenarios = [_variant_scenario(root, variant, fixture, sc, base_sha, base_corpus_rel, dataset, base_identities,
                                   str(base.get("invalid_credential_ref") or ""), gaps, revert, revert_why,
                                   effect_db_scope(sc, [e for e in (sc.get("effects") or []) if isinstance(e, dict)],
                                                   _cols, _fks, bundle_eps))
                 for sc in selected]
    scenarios.sort(key=lambda s: str(s["id"]))
    fixture_row = {
        "name": variant, "scenarios": wanted_class, "intent": str(fixture.get("intent") or ""),
        "dataset_config_key": str(fixture.get("dataset_config_key") or ""),
        # verbatim: fixture SQL, not a credential, and the thing the variant IS
        "statements": [str(s) for s in (fixture.get("statements") or [])],
        "dataset": dict(dataset),
        "declared_by": "%s[%s]" % (FIXTURES_SUBJECT, variant),
    }
    if any((s.get("effects_reader") or {}).get("strategy") == EFFECTS_REVERT_THEN_READ for s in scenarios):
        # what reset-parity-db.sh --revert-variant executes: computed here,
        # bound into the corpus digest, and read back only through the loader
        fixture_row["revert"] = dict(revert or {})
    elif revert_why and str(fixture.get("intent") or "") == "refuse":
        fixture_row["revert_refused"] = revert_why
    doc = {
        "schema": SCHEMA,
        "security_mode": mode,
        "security_variant": variant,
        "derived_from": {
            "producer": PRODUCER, "evidence_bundle_sha256": bundle_sha,
            "source_digest": str(freeze.get("source_digest") or ""),
            "security_mode": mode, "security_variant": variant,
            "base_corpus": dict(inputs["base_corpus"]),
            "variant_derivation": VARIANT_DERIVATION,
        },
        "initial_state": dict(base.get("initial_state") or {}),
        "path_vars": dict(base.get("path_vars") or {}),
        "cors_policies": [],
        "identities": [dict(i) for i in (base.get("identities") or []) if isinstance(i, dict)],
        "identities_from": str(base.get("identities_from") or ""),
        "invalid_credential_ref": str(base.get("invalid_credential_ref") or ""),
        "security_switch": dict(base.get("security_switch") or {}),
        "request_policy": str(base.get("request_policy") or ""),
        "fixture": dict(fixture_row),
        # the policies the varied scenarios cite are the base corpus's, kept
        # so an id on a scenario still resolves to the policy it names
        "authorization_policies": [dict(p) for p in (base.get("authorization_policies") or []) if isinstance(p, dict)],
        "scenarios": scenarios,
        "gaps": gaps,
    }
    corpus_sha = corpus_digest(doc)
    write_canonical(out_p, doc)
    bodies = {str(s["body_file"]): sha256_file(root / str(s["body_file"])) for s in scenarios if s.get("body_file")}
    requests = {str(s["id"]): request_of(root, s)["request_sha256"] for s in scenarios}
    write_canonical(receipt_p, {
        "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "ok", "reason": "",
        "security_mode": mode, "security_variant": variant, "variant_derivation": VARIANT_DERIVATION,
        "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha, "corpus": _rel(out_p, root),
        "base_corpus": dict(inputs["base_corpus"]),
        # which refused writes carry read-backs, as whom, and which do not and why
        "effects": {str(s["id"]): ({"identity": dict(s["effects_identity"]), "reads": [e["id"] for e in s["effects"]],
                                    "role": EFFECT_ROLE_UNCHANGED,
                                    "strategy": str((s.get("effects_reader") or {}).get("strategy") or "")}
                                   if s.get("effects_identity")
                                   else {"unobservable": str(s["effects_unobservable"])})
                    for s in scenarios if s.get("effects_identity") or s.get("effects_unobservable")},
        "fixture": dict(fixture_row),
        "identities": [dict(i) for i in (base.get("identities") or []) if isinstance(i, dict)],
        "identities_from": str(base.get("identities_from") or ""),
        "security_switch": dict(base.get("security_switch") or {}),
        "invalid_credential_ref": str(base.get("invalid_credential_ref") or ""),
        "inputs": inputs, "origin": args.origin,
        "scenarios": [str(s["id"]) for s in scenarios], "bodies": bodies, "requests": requests, "gaps": gaps,
    })
    print("OK: derived %d %s-mode scenario(s) for fixture variant %s over the %s class, %d gap(s) (corpus %s, base %s) → %s"
          % (len(scenarios), mode, variant, wanted_class, len(gaps), corpus_sha[:12], base_sha[:12], _rel(out_p, root)))
    for g in gaps:
        print("  - gap: %s" % g)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default="", help="corpus path, relative to --root (default: the corpus of --security-mode)")
    ap.add_argument("--receipt", default="", help="derivation receipt path, relative to --root (default: beside the corpus)")
    ap.add_argument("--origin", default="http://parity.invalid:4200",
                    help="the cross-origin Origin to send when a policy allows any origin; a policy that declares origins gets its first one")
    ap.add_argument("--security-mode", default=DEFAULT_SECURITY_MODE, choices=list(SECURITY_MODES),
                    help="which security mode this corpus is for (ADR-014); enabled derives the authorization probes")
    ap.add_argument("--identity", action="append", default=[], metavar="NAME=CREDENTIAL_REF",
                    help="enabled mode, repeatable: the environment variable holding the credential that authenticates as the "
                         "seeded identity NAME; the reserved NAME 'invalid' declares a credential that is NOT valid. "
                         "Only the NAME of the variable is ever read or recorded")
    ap.add_argument("--from-decisions", action="store_true",
                    help="enabled mode: read the identities, their credential REFERENCES and the source's security switch "
                         "from decisions.yaml's security section (ADR-014). The default whenever --security-mode enabled is "
                         "given with no --identity: who the source is captured as is a decision an ADR backs, not an "
                         "argument typed at a shell. A missing section derives nothing and records why")
    ap.add_argument("--fixture-variant", default="", metavar="NAME",
                    help="derive the corpus of a declared fixture VARIANT of this mode's baseline (ADR-014): one scenario per "
                         "scenario of the class security.fixtures[NAME].scenarios names, expecting what the source answers "
                         "with that fixture's statements applied after the declared dataset. The variant's corpus, captures "
                         "and parity live under their own suffixed paths, so a variant's evidence can never be read as the "
                         "baseline's")
    ap.add_argument("--identity-roles", action="append", default=[], metavar="NAME=ROLE[,ROLE...]",
                    help="enabled mode, repeatable: the roles the seeded identity NAME holds, as the Operator reads them off the "
                         "seed; derived from the seed too where the structure model maps the identity store, and a declaration "
                         "the seed contradicts is a gap")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        mode = normalize_security_mode(args.security_mode)
        variant = normalize_variant(args.fixture_variant, mode)
    except CorpusError as exc:
        print("REFUSE: DERIVE_SCENARIOS %s" % exc, file=sys.stderr)
        return 2
    if args.from_decisions and (args.identity or args.identity_roles):
        print("REFUSE: DERIVE_SCENARIOS --from-decisions reads the identities decisions.yaml declares and --identity states "
              "them on the command line; pass one or the other, so the corpus says where they came from", file=sys.stderr)
        return 2
    if variant and (args.identity or args.identity_roles):
        # a variant varies the DATASET a mode's corpus is replayed against; who
        # it authenticates as is that corpus's decision and is reused from it
        print("REFUSE: DERIVE_SCENARIOS --fixture-variant reuses the identities of the %s corpus it varies; declare them "
              "there, not on the variant" % mode, file=sys.stderr)
        return 2
    if mode == DEFAULT_SECURITY_MODE and (args.identity or args.identity_roles or args.from_decisions):
        # a mistyped command must not derive the anonymous corpus while the
        # Operator believes identities went into it
        print("REFUSE: DERIVE_SCENARIOS --identity/--identity-roles declare who the ENABLED mode authenticates as; "
              "the %s mode sends no credential (pass --security-mode enabled)" % DEFAULT_SECURITY_MODE, file=sys.stderr)
        return 2
    out_p = root / (args.out or corpus_path(mode, variant).as_posix())
    receipt_p = root / (args.receipt or derive_receipt_path(mode, variant).as_posix())
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        print("REFUSE: DERIVE_SCENARIOS missing %s; the corpus is derived from the frozen source the bundle describes" % EVIDENCE_BUNDLE, file=sys.stderr)
        return 1
    bundle = load_json(bundle_p)
    bundle_sha = digest(bundle)
    inputs: dict[str, Any] = {"evidence_bundle": _input(bundle_p, root)}
    gaps: list[str] = []

    def blocked(reason: str) -> int:
        doc = {
            "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "blocked", "reason": reason,
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": "", "inputs": inputs, "scenarios": [], "gaps": gaps,
        }
        if mode != DEFAULT_SECURITY_MODE:
            # a receipt of the default mode is where it always was and says
            # what it always said; another mode always names itself
            doc["security_mode"] = mode
        if variant:
            doc["security_variant"] = variant
        write_canonical(receipt_p, doc)
        print("REFUSE: DERIVE_SCENARIOS %s" % reason, file=sys.stderr)
        return 1

    def idle(reason: str) -> int:
        """Nothing to derive, and the receipt says what is missing.

        Distinct from blocked: the evidence this derivation is made of is
        intact, and what is absent is a FIXTURE the Operator has not declared
        (ADR-014 asks for that to be recorded, not repaired and not invented).
        The step is not red for it -- a specimen with no security switch has
        no enabled mode -- but it is never silent either."""
        doc = {
            "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "idle", "reason": reason,
            "security_mode": mode,
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": "", "corpus": _rel(out_p, root),
            "inputs": inputs, "scenarios": [], "gaps": gaps,
        }
        if variant:
            doc["security_variant"] = variant
        write_canonical(receipt_p, doc)
        print("OK: no %s-mode corpus derived (%s); the receipt says so → %s" % (mode, reason, _rel(receipt_p, root)))
        return 0

    if out_p.is_file():
        try:
            existing = load_json(out_p)
        except (OSError, ValueError):
            existing = {}
        if isinstance(existing, dict) and existing.get("approved_by") and not existing.get("derived_from"):
            return blocked("%s is a hand-authored corpus (approved_by %r); it is not overwritten -- move it, or derive to another --out"
                           % (_rel(out_p, root), existing.get("approved_by")))
    freeze_p = producer_receipt(root, "freeze")
    if not freeze_p.is_file():
        return blocked("no freeze receipt; the corpus is derived from the FROZEN source, never from the destination")
    freeze = load_json(freeze_p)
    inputs["freeze"] = _input(freeze_p, root)
    copy = Path(str(freeze.get("analysis_copy") or ""))
    if not copy.is_dir():
        return blocked("the freeze receipt's analysis_copy %s is not a directory" % copy)
    if variant:
        # a variant reuses the MODE's requests unchanged; what varies is the
        # dataset the source is started with, and that is the fixture's
        return _derive_variant(root, args, mode, variant, out_p, receipt_p, bundle_sha, freeze, copy, inputs, gaps,
                               blocked, idle)
    if mode != DEFAULT_SECURITY_MODE:
        # the enabled mode reuses the other mode's requests; it derives no
        # body, so it needs no OpenAPI document -- what it needs is the
        # source's policies, the seed behind them and that corpus
        return _derive_enabled(root, args, mode, out_p, receipt_p, bundle_sha, freeze, copy, inputs, gaps, blocked, idle)
    found = find_openapi(copy)
    if found is None:
        return blocked("no OpenAPI document (openapi: + paths:) under %s; request bodies come from its examples, never from a worker" % (copy / RESOURCES))
    oa_path, openapi = found
    inputs["openapi"] = _input(oa_path, copy)
    src_engine, dest_engine, engine, seed_p, seed, columns, foreign_keys = _sql_evidence(root, copy, inputs, gaps)
    structure_p = root / STRUCTURE
    inputs["structure"] = _input(structure_p, root)
    policies, policy_gap = source_cors_policy_map(root)
    if policy_gap:
        gaps.append("CORS policies unknown: %s; no cross-origin scenario is derived" % policy_gap)
    # the other half of a delete's evidence: whether the APPLICATION removes
    # the rows that point at the one being deleted (JPA cascade / orphan
    # removal / an owned @ManyToMany join table), read from the same structure
    # model the CORS policies come from
    persistence = load_persistence_model(root, set(columns) | set(seed))
    try:
        d = Derivation(root, bundle, openapi, seed, columns, policies, args.origin, foreign_keys, persistence)
        d.run()
    except Refusal as exc:
        return blocked(str(exc))
    gaps.extend(d.gaps)
    cors_policies = []
    for pid, pol in policies.items():
        values = pol.get("values") or {}
        note = ("@CrossOrigin(%s) on %s" % (json.dumps(values, sort_keys=True), ", ".join(pol.get("types") or []))
                if pol.get("kind") == "crossorigin" else "CORS registry configured by %s" % ", ".join(pol.get("types") or []))
        cors_policies.append({"id": pid, "request_headers": ["Content-Type"], "note": note})
    doc = {
        "schema": SCHEMA,
        "derived_from": {
            "producer": PRODUCER, "evidence_bundle_sha256": bundle_sha,
            "source_digest": str(freeze.get("source_digest") or ""),
            "openapi": inputs["openapi"], "seed": inputs["seed"],
            "structure_sha256": inputs["structure"]["sha256"],
        },
        "initial_state": {
            "reset": RESET_TEXT,
            "dataset": ("the frozen source's own seed %s (tables %s), restored by restarting the source" % (inputs["seed"]["path"], ", ".join(sorted(seed)))
                        if seed_p is not None else "no seed file was found under the frozen source"),
            "engines": "source %s, destination %s" % (src_engine or engine or "unknown", dest_engine or "as decided in decisions.yaml"),
        },
        "path_vars": dict(sorted(d.path_vars.items())),
        "cors_policies": cors_policies,
        "scenarios": d.scenarios,
        "gaps": gaps,
    }
    corpus_sha = corpus_digest(doc)
    write_canonical(out_p, doc)
    # the corpus digest binds body FILENAMES; the bytes and the complete
    # request digests are bound here, so an edited body file (architect
    # review of 708cfef9: body_only_edit_after_derivation) is refused too
    bodies = {str(s["body_file"]): sha256_file(root / str(s["body_file"])) for s in d.scenarios if s.get("body_file")}
    requests = {str(s["id"]): request_of(root, s)["request_sha256"] for s in d.scenarios}
    write_canonical(receipt_p, {
        "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "ok", "reason": "",
        "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha, "corpus": _rel(out_p, root),
        "inputs": inputs, "seed_engine": engine, "origin": args.origin,
        "scenarios": [str(s["id"]) for s in d.scenarios], "bodies": bodies, "requests": requests, "gaps": gaps,
    })
    print("OK: derived %d scenario(s), %d gap(s) (corpus %s, bundle %s) → %s" % (len(d.scenarios), len(gaps), corpus_sha[:12], bundle_sha[:12], _rel(out_p, root)))
    for g in gaps:
        print("  - gap: %s" % g)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
