"""Strict YAML subset loader for ``decisions.yaml`` and ``migration.yaml``.

PyYAML is preferred when importable (dest python3.11). This fallback
parses only the subset the planner contracts use, and refuses anything
else rather than guessing:

- block mappings (``key: value`` / ``key:`` + nested block)
- block sequences (``- item`` / ``- key: value`` object items)
- scalars: quoted strings, ints, floats, ``true``/``false``/``null``/``~``
- empty flow ``[]`` / ``{}``
- simple flow sequences of unquoted/quoted scalars (``[id]``, ``[a, b]``);
  the app-migration PetClinic stamp historically wrote ``idFields: [id]``
  and UDI ``python3`` is 3.9 without PyYAML
- quoted mapping keys (``"9966": "8080"`` in PetClinic ``valueMap``)

No anchors, tags, multi-line scalars, nested flow collections, flow maps
with members, or multi-document streams. Those raise ``YamlLiteError`` so a
human writes the decision in the supported shape instead of the planner
inferring it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class YamlLiteError(ValueError):
    pass


_KEY_RE = re.compile(
    r"""^(?:["']([A-Za-z0-9_.\-/]+)["']|([A-Za-z0-9_.\-/]+))\s*:(?:\s+(.*))?$"""
)
_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def _scalar(raw: str, line_no: int) -> Any:
    s = raw.strip()
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
        if not inner:
            return []
        if "{" in inner or "[" in inner:
            raise YamlLiteError(
                "line %d: unsupported YAML construct %r (use block form)" % (line_no, s)
            )
        parts = [p.strip() for p in inner.split(",")]
        if any(not p for p in parts):
            raise YamlLiteError(
                "line %d: unsupported YAML construct %r (use block form)" % (line_no, s)
            )
        return [_scalar(p, line_no) for p in parts]
    if s[0] in "[{" or s[0] in "&*!|>":
        raise YamlLiteError(
            "line %d: unsupported YAML construct %r (use block form)" % (line_no, s)
        )
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        body = s[1:-1]
        if s[0] == '"':
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote = ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (not out or out[-1].isspace()):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _lines(text: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if raw.strip() == "---":
            if rows:
                raise YamlLiteError("line %d: multi-document streams unsupported" % i)
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YamlLiteError("line %d: tabs in indentation" % i)
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        rows.append((i, indent, stripped.strip()))
    return rows


def _parse_block(rows: list[tuple[int, int, str]], pos: int, indent: int) -> tuple[Any, int]:
    if pos >= len(rows):
        return None, pos
    line_no, ind, text = rows[pos]
    if ind != indent:
        raise YamlLiteError("line %d: unexpected indentation" % line_no)
    if text.startswith("- ") or text == "-":
        return _parse_seq(rows, pos, indent)
    return _parse_map(rows, pos, indent)


def _parse_map(rows, pos, indent) -> tuple[dict, int]:
    out: dict[str, Any] = {}
    while pos < len(rows):
        line_no, ind, text = rows[pos]
        if ind < indent:
            break
        if ind > indent:
            raise YamlLiteError("line %d: unexpected indentation" % line_no)
        if text.startswith("- "):
            raise YamlLiteError("line %d: sequence item inside a mapping" % line_no)
        m = _KEY_RE.match(text)
        if not m:
            raise YamlLiteError("line %d: expected 'key: value'" % line_no)
        key, rest = (m.group(1) or m.group(2)), m.group(3)
        if key in out:
            raise YamlLiteError("line %d: duplicate key %r" % (line_no, key))
        pos += 1
        if rest is not None and rest.strip() != "":
            out[key] = _scalar(rest, line_no)
            continue
        if pos < len(rows) and rows[pos][1] > indent:
            value, pos = _parse_block(rows, pos, rows[pos][1])
            out[key] = value
        elif pos < len(rows) and rows[pos][1] == indent and rows[pos][2].startswith("- "):
            value, pos = _parse_seq(rows, pos, indent)
            out[key] = value
        else:
            out[key] = None
    return out, pos


def _parse_seq(rows, pos, indent) -> tuple[list, int]:
    out: list[Any] = []
    while pos < len(rows):
        line_no, ind, text = rows[pos]
        if ind < indent:
            break
        if ind > indent:
            raise YamlLiteError("line %d: unexpected indentation" % line_no)
        if not (text.startswith("- ") or text == "-"):
            break
        item = text[2:].strip() if text != "-" else ""
        pos += 1
        if not item:
            if pos < len(rows) and rows[pos][1] > indent:
                value, pos = _parse_block(rows, pos, rows[pos][1])
                out.append(value)
            else:
                out.append(None)
            continue
        m = _KEY_RE.match(item)
        if m:
            child_indent = indent + 2
            synthetic = [(line_no, child_indent, item)]
            while pos < len(rows) and rows[pos][1] >= child_indent:
                synthetic.append(rows[pos])
                pos += 1
            value, _ = _parse_map(synthetic, 0, child_indent)
            out.append(value)
            continue
        out.append(_scalar(item, line_no))
    return out, pos


def loads(text: str) -> Any:
    rows = _lines(text)
    if not rows:
        return {}
    value, pos = _parse_block(rows, 0, rows[0][1])
    if pos != len(rows):
        line_no = rows[pos][0]
        raise YamlLiteError("line %d: trailing content" % line_no)
    return value


def load_yaml(path: Path) -> Any:
    """Load YAML: PyYAML when available, else the strict subset parser."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return loads(text)
