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
from _scenarios import CORPUS, DERIVATION_SCHEMA, DERIVE_RECEIPT, SCHEMA, corpus_digest, source_cors_policy_map  # noqa: E402

ensure_hermes_lib()
from planner import yamlite  # noqa: E402
from planner.canonical import digest, load_json, sha256_file, write_canonical  # noqa: E402
from planner.paths import EVIDENCE_BUNDLE, STRUCTURE, producer_receipt  # noqa: E402

PRODUCER = "derive-source-scenarios.py"
BODIES = Path("verification") / "scenarios" / "bodies"
RESOURCES = Path("src") / "main" / "resources"
DEFAULT_ENGINE = "hsqldb"
RESET_TEXT = (".hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root . restores the destination "
              "instance; the frozen source restores the same dataset by restarting when its baseline engine is in-memory")
# characters tried, in order, to build a value a ``pattern`` forbids
FORBIDDEN_CANDIDATES = ("!", "#", "-", " ", "a", "1", "~", "%", "@")


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


def operation_stems(doc: dict[str, Any], op: dict[str, Any]) -> list[str]:
    out = [str(t).lower() for t in (op.get("tags") or []) if str(t).strip()]
    schema = body_schema(doc, op)
    if schema is not None:
        _, name = _deref(doc, schema)
        if name:
            out.append(name.lower())
    return out


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
    """{table: {"columns": [...] or [], "values": [first row]}} -- the first
    INSERT row per table is enough to name an existing identifier."""
    out: dict[str, dict[str, Any]] = {}
    for m in _INSERT_RE.finditer(text):
        table = m.group(1).lower()
        if table in out:
            continue
        cols = [c.strip().strip('`"').lower() for c in (m.group(3) or "").split(",") if c.strip()] if m.group(2) else []
        out[table] = {"columns": cols, "values": _tuple_values(text, m.end())}
    return out


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


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _plural(word: str) -> str:
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


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
        base = name[:-2]
        words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", base) or [base]
        candidates = [_plural(base.lower()), _plural(_snake(base)), _plural(words[-1].lower())]
        for table in dict.fromkeys(candidates):
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
                 columns: dict[str, list[str]], policies: dict[str, dict[str, Any]], origin: str) -> None:
        self.root = root
        self.openapi = openapi
        self.seed = seed
        self.columns = columns
        self.policies = policies
        self.origin = origin
        self.gaps: list[str] = []
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

    def _lookup(self, ep: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any], str] | None:
        """(path, path item, operation, binding evidence) for an entry point.

        By path when the document names the code's routes; else by
        ``operationId``, which in a spec-first source names the controller
        method the entry point embeds (``addOwner`` -> ``#addOwner(...)``).
        Two controllers can share a method name (petclinic's Owner and User
        controllers both declare ``addOwner``): then only the one whose name
        stem matches the operation's tag or body schema (``owner`` ->
        ``OwnerFields``) binds, and an ambiguity that survives is a gap, not
        a guess."""
        method = str(ep.get("http_method") or "").upper()
        found = find_operation(self.openapi, str(ep.get("http_path") or ""), method)
        if found is not None:
            return found[0], found[1], found[2], "openapi:%s#%s(path)" % (found[0], method.lower())
        name = member_name(ep.get("member"))
        ops = self.by_opid.get((method, name)) or []
        if not name or not ops:
            return None
        if len(ops) > 1:
            self.gaps.append("operationId %s appears on %d paths (%s); no single operation binds %s" % (name, len(ops), ", ".join(p for p, _, _ in ops), ep.get("id")))
            return None
        oa_path, item, op = ops[0]
        claimants = [e for e in self.eps if str(e.get("http_method") or "").upper() == method and member_name(e.get("member")) == name]
        if len(claimants) > 1:
            stems = operation_stems(self.openapi, op)
            survivors = [e for e in claimants if any(s.startswith(_stem(str(e.get("type") or ""))) for s in stems)]
            if len(survivors) != 1:
                if ep is claimants[0]:
                    self.gaps.append("operationId %s (%s %s) is claimed by %d entry points and its tags/schema (%s) single out none: %s"
                                     % (name, method, oa_path, len(claimants), ", ".join(stems) or "none", ", ".join(str(e.get("id")) for e in claimants)))
                return None
            if survivors[0] is not ep:
                return None
        return oa_path, item, op, "openapi:%s#%s(operationId %s)" % (oa_path, method.lower(), name)

    # -- rules -------------------------------------------------------------
    def run(self) -> None:
        for ep in self.eps:
            eid = str(ep.get("id") or "")
            method = str(ep.get("http_method") or "").upper()
            route = str(ep.get("http_path") or "")
            if not method:
                kind = str(ep.get("kind") or "http")
                self.gaps.append("entry point %s has no HTTP method (%s); nothing is derived for it" % (eid, "a non-HTTP entry point is captured by observation" if kind != "http" else "a servlet mapping is not a request the corpus can derive"))
                continue
            found = self._lookup(ep)
            examples = path_param_examples(self.openapi, found[1], found[2]) if found else {}
            got, unresolved = self._resolve_vars(ep, examples)
            for name in unresolved:
                self.gaps.append("path variable {%s} of %s resolves nowhere (no seed row, no OpenAPI example); scenarios needing it are not emitted" % (name, eid))
            if "*" in route:
                self.gaps.append("entry point %s route %s carries a wildcard and is not a request" % (eid, route))
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

    def _create(self, ep: dict[str, Any], found: Any, got: dict[str, str], unresolved: list[str]) -> None:
        eid, route, type_fqn = str(ep["id"]), str(ep.get("http_path") or ""), str(ep.get("type") or "")
        if "{" in route:
            self.gaps.append("create %s: path %s carries variables; the create rule needs a collection path" % (eid, route))
            return
        if found is None:
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
        sid = "sc:create-%s" % resource
        sc: dict[str, Any] = {
            "id": sid, "entry_point": eid, "method": "POST", "path": route, "headers": headers,
            "identity": {"kind": "none"}, "body_file": _write_body(self.root, sid, body), "body_absent": False,
            "reset_before": True,
            "effects": [{"id": "eff:%s-list-after-create" % resource, "method": "GET", "path": route}],
            "normalization": [],
            "derived_from": {"kind": "create", "entry_point": eid, "evidence": evidence},
            # count-based, not absent-before: a document's example is often a
            # seeded row verbatim (petclinic's OwnerFields example IS owner 1),
            # so "absent before" could never hold; "one more than before" can
            "qualify": {"expect_status": [201], "location": "absolute-under-base", "after_contains_body": True, "after_adds_one_body": True},
            "why": "the document's own example of %s, created on the collection the route names; the read-back shows one more matching row than before" % label,
        }
        if policy:
            sc["cors_policy"] = policy
        self._add(sc)
        # create-invalid: the same body with ONE property the schema refuses
        field, bad_value = "", None
        for pname, pnode in (sch.get("properties") or {}).items():
            psch = merged_schema(self.openapi, pnode, pname)
            if psch.get("pattern") and pname in body:
                bad_value = _invalid_value(body[pname], str(psch["pattern"]))
                if bad_value is not None:
                    field = pname
                    break
        if not field:
            for pname in (sch.get("required") or []):
                psch = merged_schema(self.openapi, (sch.get("properties") or {}).get(pname), pname)
                if psch.get("type") == "string" and int(psch.get("minLength") or 0) >= 1 and pname in body:
                    field, bad_value = pname, ""
                    break
        if not field:
            self.gaps.append("create-invalid %s: %s has no property with a pattern or a required minLength string; no invalid body can be derived" % (eid, label))
            return
        invalid = dict(body)
        invalid[field] = bad_value
        isid = "sc:create-invalid-%s" % resource
        isc: dict[str, Any] = {
            "id": isid, "entry_point": eid, "method": "POST", "path": route, "headers": dict(headers),
            "identity": {"kind": "none"}, "body_file": _write_body(self.root, isid, invalid), "body_absent": False,
            "reset_before": True,
            "effects": [{"id": "eff:%s-list-after-invalid-create" % resource, "method": "GET", "path": route}],
            "normalization": [],
            "derived_from": {"kind": "create-invalid", "entry_point": eid,
                             "evidence": evidence + ["openapi:%s.%s constraint" % (label, field)]},
            "qualify": {"expect_status": [400], "errors_header_names_field": field, "after_equals_before": True},
            "why": "the same body with %s violating the constraint the document declares; the read-back shows nothing was created" % field,
        }
        if policy:
            isc["cors_policy"] = policy
        self._add(isc)

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
            "qualify": {"expect_status": [200, 204], "after_contains_body": True},
            "why": "the document's own example of %s written over the seeded row %s; the read-backs show the row and the list carry it" % (label, seeded),
        })

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
        seeded = got[names[0]]
        item_path = route.replace("{%s}" % names[0], seeded)
        resource = _resource(route[: route.rfind("/{")] or "/")
        eff = "eff:%s-%s-after-delete" % (resource, seeded)
        self._add({
            "id": "sc:delete-%s-%s" % (resource, seeded), "entry_point": eid, "method": "DELETE", "path": item_path,
            "headers": {}, "identity": {"kind": "none"}, "body_absent": True, "reset_before": True,
            "effects": [{"id": eff, "method": "GET", "path": item_path}],
            "normalization": [],
            "derived_from": {"kind": "delete", "entry_point": eid, "evidence": ["bundle:%s" % eid, self.path_var_evidence.get(names[0], "")]},
            "qualify": {"expect_status": [200, 204], "after_effect_status": {eff: 404}},
            "why": "the seeded row %s exists by construction; the read-back after the delete must not find it" % seeded,
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
                q: dict[str, Any] = {"expect_status": [200], "cors_allow_origin": True}
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
                    "qualify": {"expect_status": [200, 204], "cors_allow_origin": True, "cors_allow_method": "POST", "cors_allow_headers": ["content-type"]},
                    "why": "the preflight a browser sends before the create under %s; no credentials, no effects" % pid,
                })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=CORPUS.as_posix(), help="corpus path, relative to --root")
    ap.add_argument("--receipt", default=DERIVE_RECEIPT.as_posix(), help="derivation receipt path, relative to --root")
    ap.add_argument("--origin", default="http://parity.invalid:4200",
                    help="the cross-origin Origin to send when a policy allows any origin; a policy that declares origins gets its first one")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    out_p = root / args.out
    receipt_p = root / args.receipt
    bundle_p = root / EVIDENCE_BUNDLE
    if not bundle_p.is_file():
        print("REFUSE: DERIVE_SCENARIOS missing %s; the corpus is derived from the frozen source the bundle describes" % EVIDENCE_BUNDLE, file=sys.stderr)
        return 1
    bundle = load_json(bundle_p)
    bundle_sha = digest(bundle)
    inputs: dict[str, Any] = {"evidence_bundle": _input(bundle_p, root)}
    gaps: list[str] = []

    def blocked(reason: str) -> int:
        write_canonical(receipt_p, {
            "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "blocked", "reason": reason,
            "evidence_bundle_sha256": bundle_sha, "corpus_sha256": "", "inputs": inputs, "scenarios": [], "gaps": gaps,
        })
        print("REFUSE: DERIVE_SCENARIOS %s" % reason, file=sys.stderr)
        return 1

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
    found = find_openapi(copy)
    if found is None:
        return blocked("no OpenAPI document (openapi: + paths:) under %s; request bodies come from its examples, never from a worker" % (copy / RESOURCES))
    oa_path, openapi = found
    inputs["openapi"] = _input(oa_path, copy)
    src_engine, dest_engine = _decided_engines(root)
    seed_p, engine = find_seed(copy, src_engine)
    seed: dict[str, dict[str, Any]] = {}
    columns: dict[str, list[str]] = {}
    if seed_p is None:
        gaps.append("no seed file src/main/resources/db/<engine>/populateDB.sql under the frozen source; path variables and seeded rows cannot be named")
        inputs["seed"] = {"path": "", "sha256": ""}
    else:
        inputs["seed"] = _input(seed_p, copy)
        seed = parse_seed(seed_p.read_text(encoding="utf-8", errors="replace"))
        schema_p = seed_p.with_name("schema.sql")
        if schema_p.is_file():
            inputs["schema"] = _input(schema_p, copy)
            columns = parse_schema_columns(schema_p.read_text(encoding="utf-8", errors="replace"))
    structure_p = root / STRUCTURE
    inputs["structure"] = _input(structure_p, root)
    policies, policy_gap = source_cors_policy_map(root)
    if policy_gap:
        gaps.append("CORS policies unknown: %s; no cross-origin scenario is derived" % policy_gap)
    try:
        d = Derivation(root, bundle, openapi, seed, columns, policies, args.origin)
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
    write_canonical(receipt_p, {
        "schema": DERIVATION_SCHEMA, "producer": PRODUCER, "at": _now(), "status": "ok", "reason": "",
        "evidence_bundle_sha256": bundle_sha, "corpus_sha256": corpus_sha, "corpus": _rel(out_p, root),
        "inputs": inputs, "seed_engine": engine, "origin": args.origin,
        "scenarios": [str(s["id"]) for s in d.scenarios], "gaps": gaps,
    })
    print("OK: derived %d scenario(s), %d gap(s) (corpus %s, bundle %s) → %s" % (len(d.scenarios), len(gaps), corpus_sha[:12], bundle_sha[:12], _rel(out_p, root)))
    for g in gaps:
        print("  - gap: %s" % g)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
