"""JSON Schema (draft-07 subset) validator for planner contracts.

Supports the keywords the ``.hermes/planning/schemas`` files use:
``type``, ``properties``, ``required``, ``additionalProperties`` (bool or
schema), ``items``, ``enum``, ``const``, ``pattern``, ``minItems``,
``minimum``, ``maximum``, ``minLength``, ``oneOf`` and ``$ref`` to
``#/definitions/<name>``. Anything else in a schema is refused at load so
a contract cannot silently validate less than it appears to.

Returns every violation (full gap set), never the first one.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from planner.canonical import load_json

SUPPORTED = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "title",
        "description",
        "definitions",
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "pattern",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "minLength",
        "oneOf",
        "examples",
        "default",
    }
)

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class SchemaError(ValueError):
    pass


def _check_supported(schema: Any, where: str) -> None:
    if isinstance(schema, dict):
        for key, val in schema.items():
            if key not in SUPPORTED:
                raise SchemaError("%s: unsupported keyword %r" % (where, key))
            if key in ("properties", "definitions"):
                for name, sub in (val or {}).items():
                    _check_supported(sub, "%s.%s.%s" % (where, key, name))
            elif key in ("items", "additionalProperties"):
                if isinstance(val, dict):
                    _check_supported(val, "%s.%s" % (where, key))
            elif key == "oneOf":
                for i, sub in enumerate(val or []):
                    _check_supported(sub, "%s.oneOf[%d]" % (where, i))


def load_schema(path: Path) -> dict:
    schema = load_json(path)
    if not isinstance(schema, dict):
        raise SchemaError("%s: schema root must be an object" % path)
    _check_supported(schema, str(path))
    return schema


def _resolve(schema: dict, root: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not ref.startswith("#/definitions/"):
        raise SchemaError("unsupported $ref %r" % ref)
    name = ref[len("#/definitions/") :]
    target = (root.get("definitions") or {}).get(name)
    if not isinstance(target, dict):
        raise SchemaError("unknown definition %r" % name)
    return target


def _type_ok(value: Any, typ: str) -> bool:
    py = _TYPES.get(typ)
    if py is None:
        raise SchemaError("unknown type %r" % typ)
    if typ == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if typ == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, py)


def validate(value: Any, schema: dict, *, root: dict | None = None, path: str = "$") -> list[str]:
    root = root if root is not None else schema
    schema = _resolve(schema, root)
    errors: list[str] = []

    if "oneOf" in schema:
        hits = 0
        for sub in schema["oneOf"]:
            if not validate(value, sub, root=root, path=path):
                hits += 1
        if hits != 1:
            errors.append("%s: expected exactly one oneOf branch, matched %d" % (path, hits))
            return errors

    typ = schema.get("type")
    if typ is not None:
        types = typ if isinstance(typ, list) else [typ]
        if not any(_type_ok(value, t) for t in types):
            errors.append("%s: expected type %s" % (path, "|".join(types)))
            return errors

    if "const" in schema and value != schema["const"]:
        errors.append("%s: expected const %r" % (path, schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: %r not in enum %s" % (path, value, schema["enum"]))

    if isinstance(value, str):
        pat = schema.get("pattern")
        if pat and not re.search(pat, value):
            errors.append("%s: %r does not match %s" % (path, value, pat))
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: shorter than minLength %d" % (path, schema["minLength"]))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %r < minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: %r > maximum %r" % (path, value, schema["maximum"]))

    if isinstance(value, dict):
        props = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append("%s: missing required %r" % (path, key))
        for key, val in value.items():
            if key in props:
                errors.extend(validate(val, props[key], root=root, path="%s.%s" % (path, key)))
                continue
            extra = schema.get("additionalProperties", True)
            if extra is False:
                errors.append("%s: unexpected property %r" % (path, key))
            elif isinstance(extra, dict):
                errors.extend(validate(val, extra, root=root, path="%s.%s" % (path, key)))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: fewer than minItems %d" % (path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: more than maxItems %d" % (path, schema["maxItems"]))
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(value):
                errors.extend(validate(item, items, root=root, path="%s[%d]" % (path, i)))

    return errors


def validate_file(value: Any, schema_path: Path) -> list[str]:
    return validate(value, load_schema(schema_path))
