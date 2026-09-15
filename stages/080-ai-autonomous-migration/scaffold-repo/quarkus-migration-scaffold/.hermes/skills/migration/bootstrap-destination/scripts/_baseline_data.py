#!/usr/bin/env python3
"""The destination's baseline data, derived from the dataset the CONTRACT declares.

ADR-009 keeps PostgreSQL as the destination engine, but the logical data the
destination starts from -- and the generated-identity behaviour on top of it --
must reproduce the baseline the source was CAPTURED on. Those are two different
claims, and v9 satisfied only the first: the bootstrap installed the source's
own ``db/postgresql`` assets, while the corpus declares the source's
``db/hsqldb`` seed as ``initial_state.dataset``. Measured on the specimen, the
two files hold the same rows with 17 different date literals, and the
PostgreSQL schema restarts every identity sequence at a fixed 100 where the
engine the source ran on continued from the seeded maximum. Both differences
are invisible to the build and fatal to parity: a POST returns a ``Location``
with the wrong id, and the read-back of any seeded row can differ in a date.

So the baseline is DERIVED, not chosen:

- the declared dataset is whatever the contract names (the corpus's
  ``initial_state`` / ``derived_from.seed``), and only when the contract names
  nothing is it discovered by the same rule the derivation uses;
- its INSERT statements are translated to the destination engine one literal at
  a time, and a literal form this translator has no rule for REFUSES with the
  statement quoted -- a seed that is silently half-understood is worse than one
  that is not loaded;
- one sequence-alignment statement per generated-identity column the
  DESTINATION SCHEMA declares makes each sequence continue from the seeded
  maximum. The columns are read from the destination schema asset the bootstrap
  installs, not from ``information_schema``: the asset is what the reset itself
  applies, it is readable with no live instance (the bootstrap has none), and
  it makes the generated file a deterministic function of two files under
  version control rather than of whatever database happened to be up.

Nothing here knows a table, a column, or a value of any specimen. The specimen
enters through ``decisions.yaml``, the corpus, and the two SQL assets.

Also the reset's half of the contract: ``plan_from_asset`` re-measures the
generated file, ``verification_sql`` asserts it INSIDE the database after the
load, and ``verify_observations`` is the same judgement over query results a
test can hand it without a database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

TRANSLATOR = "baseline-data-translator"
TRANSLATOR_VERSION = "1.0.0"

#: the one name of the derived asset; it lives beside the destination schema
#: asset (``src/main/resources/db/<engine>/``) and is versioned with the product
BASELINE_FILENAME = "baseline-data.sql"
#: the marker that says this file is generated and may be re-generated
BASELINE_MARKER = "rhoai3.baseline-data/v1"

RESOURCES = Path("src") / "main" / "resources"
CORPUS = Path("verification") / "scenarios" / "corpus.json"
#: the same discovery rule as derive-source-scenarios.py::find_seed
SEED_BASENAME = "populateDB.sql"
DEFAULT_SEED_ENGINE = "hsqldb"

#: engines the translator has rules for; anything else is reported, never guessed
SUPPORTED_ENGINES = ("postgresql",)

_TEMPORAL_KEYWORDS = ("TIMESTAMP", "DATE", "TIME")
_IDENTITY_MARKERS = ("SERIAL", "BIGSERIAL", "SMALLSERIAL", "IDENTITY", "AUTO_INCREMENT")
_CONSTRAINT_WORDS = ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "KEY",
                     "INDEX", "EXCLUDE", "LIKE", "PERIOD")


class BaselineRefusal(Exception):
    """A dataset the translator will not pretend to understand."""

    def __init__(self, subject: str, detail: str) -> None:
        super().__init__(detail)
        self.subject = subject
        self.detail = detail


# ---------------------------------------------------------------------------
# scanning (no regex: SQL string literals do not survive one)
# ---------------------------------------------------------------------------
def _is_ident_start(c: str) -> bool:
    return c.isalpha() or c in "_$"


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c in "_$"


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _end_of_quoted(text: str, i: int, subject: str) -> int:
    """Index just past the literal or quoted identifier starting at ``i``."""
    q = text[i]
    j = i + 1
    n = len(text)
    while j < n:
        if text[j] == q:
            if text[j + 1:j + 2] == q:
                j += 2
                continue
            return j + 1
        j += 1
    raise BaselineRefusal(subject, "unterminated %s literal in: %s" % ("string" if q == "'" else "quoted-identifier", text.strip()))


def statements(text: str, subject: str = "dataset") -> list[str]:
    """Statements, with ``--`` and ``/* */`` comments removed, split on the
    semicolons that are not inside a literal."""
    out: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = _end_of_quoted(text, i, subject)
            buf.append(text[i:j])
            i = j
            continue
        if c == "-" and text[i + 1:i + 2] == "-":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            buf.append(" ")
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            if j < 0:
                raise BaselineRefusal(subject, "unterminated block comment")
            i = j + 2
            buf.append(" ")
            continue
        if c == ";":
            out.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    out.append("".join(buf).strip())
    return [s for s in out if s]


def words(text: str) -> list[str]:
    """The upper-cased bare words of a statement; literals are skipped."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if _is_ident_start(c):
            j = i
            while j < n and _is_ident_char(text[j]):
                j += 1
            out.append(text[i:j].upper())
            i = j
            continue
        if c in "'\"":
            i = _end_of_quoted(text, i, "statement")
            continue
        i += 1
    return out


def split_top(text: str, subject: str = "statement") -> list[str]:
    """Split on the commas that are neither nested nor inside a literal."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            j = _end_of_quoted(text, i, subject)
            buf.append(text[i:j])
            i = j
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    parts.append("".join(buf).strip())
    return parts


def _read_paren(text: str, i: int, subject: str) -> tuple[str, int]:
    """(inner text, index after the closing paren) for the group at ``i``."""
    if text[i:i + 1] != "(":
        raise BaselineRefusal(subject, "expected ( in: %s" % text.strip())
    depth = 0
    j = i
    n = len(text)
    while j < n:
        c = text[j]
        if c in "'\"":
            j = _end_of_quoted(text, j, subject)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    raise BaselineRefusal(subject, "unbalanced parentheses in: %s" % text.strip())


def _read_identifier(text: str, i: int, subject: str) -> tuple[str, int]:
    i = _skip_ws(text, i)
    if i < len(text) and text[i] == '"':
        j = _end_of_quoted(text, i, subject)
        return text[i:j], j
    j = i
    while j < len(text) and (_is_ident_char(text[j]) or text[j] == "."):
        j += 1
    if j == i:
        raise BaselineRefusal(subject, "expected an identifier in: %s" % text.strip())
    return text[i:j], j


def _expect_word(text: str, i: int, want: str, subject: str) -> int:
    i = _skip_ws(text, i)
    j = i
    while j < len(text) and _is_ident_char(text[j]):
        j += 1
    if text[i:j].upper() != want:
        raise BaselineRefusal(subject, "expected %s in: %s" % (want, text.strip()))
    return j


# ---------------------------------------------------------------------------
# identifiers and literals, per destination engine
# ---------------------------------------------------------------------------
def stored_name(raw: str, engine: str) -> str:
    """The name the engine actually stores for this identifier.

    Unquoted identifiers fold -- PostgreSQL to lower case, the engine the
    declared dataset was written for may fold the other way -- and a quoted one
    is stored exactly as written. This is the only place that knows it."""
    raw = raw.strip()
    if raw.startswith('"'):
        if not raw.endswith('"') or len(raw) < 2:
            raise BaselineRefusal("identifier", "malformed quoted identifier %s" % raw)
        return raw[1:-1].replace('""', '"')
    if not raw or raw[0].isdigit():
        raise BaselineRefusal("identifier", "%r is not an identifier" % raw)
    for ch in raw:
        if not (_is_ident_char(ch) or ch == "."):
            raise BaselineRefusal("identifier", "%r is not an identifier the translator can fold" % raw)
    return raw.lower() if engine == "postgresql" else raw


def quote_name(name: str) -> str:
    return '"%s"' % name.replace('"', '""')


def quote_literal(value: str) -> str:
    return "'%s'" % value.replace("'", "''")


def _is_number(t: str) -> bool:
    i = 0
    n = len(t)
    if i < n and t[i] in "+-":
        i += 1
    digits = 0
    while i < n and t[i].isdigit():
        i += 1
        digits += 1
    if i < n and t[i] == ".":
        i += 1
        while i < n and t[i].isdigit():
            i += 1
            digits += 1
    if digits == 0:
        return False
    if i < n and t[i] in "eE":
        i += 1
        if i < n and t[i] in "+-":
            i += 1
        exp = 0
        while i < n and t[i].isdigit():
            i += 1
            exp += 1
        if exp == 0:
            return False
    return i == n


def _is_one_string(t: str) -> bool:
    if len(t) < 2 or t[0] != "'":
        return False
    try:
        return _end_of_quoted(t, 0, "literal") == len(t)
    except BaselineRefusal:
        return False


def translate_literal(raw: str, engine: str, stmt: str) -> str:
    """One value of one row, rendered for the destination engine.

    The understood forms are the ones that actually occur in a declared
    dataset: NULL, a boolean, a decimal or integer number, a single-quoted
    string (``''`` doubling and all), and a typed temporal literal
    (``DATE '2010-09-07'``). A bare ``'2010-09-07'`` going into a date column
    is a string literal in both engines and stays one. Everything else --- a
    function call, a binary literal, an escape-string prefix, an identifier ---
    refuses, because guessing its destination form is how a baseline quietly
    stops being the declared one."""
    t = raw.strip()
    if not t:
        raise BaselineRefusal("literal", "empty value in: %s" % stmt.strip())
    u = t.upper()
    if u == "NULL":
        return "NULL"
    if u in ("TRUE", "FALSE"):
        return u.lower()
    if _is_one_string(t):
        return t
    for kw in _TEMPORAL_KEYWORDS:
        if u.startswith(kw) and len(t) > len(kw) and (t[len(kw)].isspace() or t[len(kw)] == "'"):
            rest = t[len(kw):].strip()
            if _is_one_string(rest):
                return "%s %s" % (kw, rest)
    if _is_number(t):
        return t
    raise BaselineRefusal("literal", "the translator has no rule for the literal %s in: %s" % (t, stmt.strip()))


# ---------------------------------------------------------------------------
# the destination schema: which columns the engine generates
# ---------------------------------------------------------------------------
def _peek_word(text: str, i: int) -> tuple[str, int]:
    """(the next bare word upper-cased, index after it); ("", i) when the next
    thing is not a bare word."""
    j = _skip_ws(text, i)
    k = j
    while k < len(text) and _is_ident_char(text[k]):
        k += 1
    return text[j:k].upper(), k


def parse_schema(text: str, engine: str = "postgresql") -> dict[str, dict[str, Any]]:
    """table → {"columns": [...], "identity": [...]} in declaration order.

    Only ``CREATE TABLE`` is read; everything else in a schema asset (drops,
    indexes, sequence resets, constraints added later) is none of this
    function's business and is skipped rather than refused --- the schema is
    read, not translated."""
    out: dict[str, dict[str, Any]] = {}
    for stmt in statements(text, "schema"):
        w = words(stmt)
        if not w or w[0] != "CREATE" or "TABLE" not in w[:4]:
            continue
        i = _expect_word(stmt, 0, "CREATE", "schema")
        # CREATE [GLOBAL|LOCAL] [TEMP|TEMPORARY|UNLOGGED] TABLE [IF NOT EXISTS]
        while True:
            token, after = _peek_word(stmt, i)
            if not token:
                break
            i = after
            if token == "TABLE":
                break
        if _peek_word(stmt, i)[0] == "IF":
            for want in ("IF", "NOT", "EXISTS"):
                i = _expect_word(stmt, i, want, "schema")
        try:
            raw_name, i = _read_identifier(stmt, i, "schema")
            body, _ = _read_paren(stmt, _skip_ws(stmt, i), "schema")
        except BaselineRefusal:
            continue
        table = stored_name(raw_name, engine)
        columns: list[str] = []
        identity: list[str] = []
        for item in split_top(body, "schema"):
            if not item:
                continue
            iw = words(item)
            if not iw or iw[0] in _CONSTRAINT_WORDS:
                continue
            try:
                raw_col, _ = _read_identifier(item, 0, "schema")
                col = stored_name(raw_col, engine)
            except BaselineRefusal:
                continue
            columns.append(col)
            if any(marker in iw[1:] for marker in _IDENTITY_MARKERS):
                identity.append(col)
        out[table] = {"columns": columns, "identity": identity}
    return out


# ---------------------------------------------------------------------------
# the dataset: INSERT statements only
# ---------------------------------------------------------------------------
def parse_insert(stmt: str, engine: str) -> tuple[str, list[str] | None, list[list[str]]]:
    """(table, explicit column list or None, rows of raw value text)."""
    subject = "dataset"
    i = _expect_word(stmt, 0, "INSERT", subject)
    i = _expect_word(stmt, i, "INTO", subject)
    raw_table, i = _read_identifier(stmt, i, subject)
    i = _skip_ws(stmt, i)
    columns: list[str] | None = None
    if stmt[i:i + 1] == "(":
        body, i = _read_paren(stmt, i, subject)
        columns = [stored_name(c, engine) for c in split_top(body, subject) if c.strip()]
    i = _expect_word(stmt, i, "VALUES", subject)
    rows: list[list[str]] = []
    while True:
        i = _skip_ws(stmt, i)
        if stmt[i:i + 1] != "(":
            raise BaselineRefusal(subject, "expected a VALUES row in: %s" % stmt.strip())
        body, i = _read_paren(stmt, i, subject)
        rows.append(split_top(body, subject))
        i = _skip_ws(stmt, i)
        if stmt[i:i + 1] == ",":
            i += 1
            continue
        break
    rest = stmt[i:].strip()
    if rest:
        # the only trailing clause with a meaning here: conflict handling is the
        # source's own idempotent-import concern, and the reset always loads
        # into a schema it just created, so it carries nothing over
        if words(rest) != ["ON", "CONFLICT", "DO", "NOTHING"]:
            raise BaselineRefusal(subject, "the translator has no rule for the trailing clause %r in: %s" % (rest, stmt.strip()))
    return stored_name(raw_table, engine), columns, rows


class Baseline:
    """The derived baseline: what to load and what must then be true of it."""

    def __init__(self, engine: str) -> None:
        self.engine = engine
        self.statements: list[str] = []
        self.row_counts: dict[str, int] = {}
        self.sequences: list[dict[str, Any]] = []
        self.alignment: list[str] = []


def build_baseline(dataset_text: str, schema_text: str, engine: str) -> Baseline:
    """Translate the declared dataset and derive the sequence alignment."""
    if engine not in SUPPORTED_ENGINES:
        raise BaselineRefusal("engine", "the translator has no rules for destination engine %r (it knows %s)"
                              % (engine, ", ".join(SUPPORTED_ENGINES)))
    schema = parse_schema(schema_text, engine)
    out = Baseline(engine)
    seeded: dict[str, dict[str, list[str]]] = {}
    for stmt in statements(dataset_text, "dataset"):
        if words(stmt)[:1] != ["INSERT"]:
            raise BaselineRefusal("dataset", "the translator reads INSERT statements only; it has no rule for: %s" % stmt.strip())
        table, columns, rows = parse_insert(stmt, engine)
        if table not in schema:
            raise BaselineRefusal("dataset", "the declared dataset inserts into %s, which the destination schema asset does not declare" % table)
        declared = schema[table]["columns"]
        target = columns if columns is not None else declared
        values_out: list[str] = []
        for row in rows:
            if columns is not None and len(row) != len(columns):
                raise BaselineRefusal("dataset", "%d value(s) for %d named column(s) in: %s" % (len(row), len(columns), stmt.strip()))
            values_out.append("(%s)" % ", ".join(translate_literal(v, engine, stmt) for v in row))
            if len(row) == len(target):
                for name, value in zip(target, row):
                    seeded.setdefault(table, {}).setdefault(name, []).append(value.strip())
        head = "INSERT INTO %s" % quote_name(table)
        if columns is not None:
            head += " (%s)" % ", ".join(quote_name(c) for c in columns)
        out.statements.append("%s VALUES %s;" % (head, ", ".join(values_out)))
        out.row_counts[table] = out.row_counts.get(table, 0) + len(rows)
    for table in schema:
        for column in schema[table]["identity"]:
            values = (seeded.get(table) or {}).get(column) or []
            ints = [int(v) for v in values if _is_number(v) and "." not in v and "e" not in v.lower()]
            seeded_max = max(ints) if ints and len(ints) == len(values) else None
            out.sequences.append({"table": table, "column": column,
                                  "rows": out.row_counts.get(table, 0), "seeded_max": seeded_max})
            out.alignment.append(alignment_statement(table, column, engine))
    return out


def alignment_statement(table: str, column: str, engine: str) -> str:
    """Make the engine's generated-identity sequence continue from the seeded
    maximum --- which is what the engine the source ran on did, and what a
    schema that RESTARTs its sequences at a fixed number does not."""
    if engine != "postgresql":
        raise BaselineRefusal("engine", "no sequence-alignment rule for engine %r" % engine)
    return ("SELECT setval(pg_get_serial_sequence(%s, %s), "
            "COALESCE((SELECT max(%s) FROM %s), 1), "
            "(SELECT count(*) > 0 FROM %s));"
            % (quote_literal(table), quote_literal(column),
               quote_name(column), quote_name(table), quote_name(table)))


def alignment_target(stmt: str) -> tuple[str, str] | None:
    """(table, column) of an alignment statement, read back from the asset."""
    needle = "pg_get_serial_sequence"
    at = stmt.find(needle)
    if at < 0:
        return None
    try:
        body, _ = _read_paren(stmt, _skip_ws(stmt, at + len(needle)), "asset")
        args = split_top(body, "asset")
    except BaselineRefusal:
        return None
    if len(args) != 2 or not (_is_one_string(args[0]) and _is_one_string(args[1])):
        return None
    return args[0][1:-1].replace("''", "'"), args[1][1:-1].replace("''", "'")


# ---------------------------------------------------------------------------
# the asset: header, body, and the digest that says what it was generated from
# ---------------------------------------------------------------------------
def contract_digest(fields: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def render_asset(baseline: Baseline, contract: dict[str, Any]) -> str:
    rows = ", ".join("%s=%d" % (t, baseline.row_counts[t]) for t in sorted(baseline.row_counts)) or "(none)"
    seqs = ", ".join("%s.%s=%s" % (s["table"], s["column"], s["seeded_max"] if s["seeded_max"] is not None else "(from the loaded rows)")
                     for s in baseline.sequences) or "(none)"
    lines = [
        "-- marker: %s" % BASELINE_MARKER,
        "-- GENERATED by bootstrap-destination. Do not edit: the bootstrap refuses a",
        "-- hand-edited copy rather than overwrite it, and regenerates this file when",
        "-- the contract below changes. Fix the declared dataset or the schema asset.",
        "--",
        "-- The destination's initialized logical data, derived from the baseline the",
        "-- application contract declares, so the destination starts every parity",
        "-- comparison from the state the source was captured in (ADR-009).",
        "--",
        "-- translator: %s/%s" % (TRANSLATOR, TRANSLATOR_VERSION),
        "-- contract-sha256: %s" % contract_digest(contract),
        "-- destination-engine: %s" % contract["destination_engine"],
        "-- declared-dataset: %s" % contract["declared_dataset"]["path"],
        "-- declared-dataset-sha256: %s" % contract["declared_dataset"]["sha256"],
        "-- declared-dataset-named-by: %s" % contract["declared_dataset"]["named_by"],
        "-- schema-asset: %s" % contract["schema_asset"]["path"],
        "-- schema-asset-sha256: %s" % contract["schema_asset"]["sha256"],
        "-- rows: %s" % rows,
        "-- sequences: %s" % seqs,
        "",
        "-- the declared dataset, statement for statement, translated for this engine",
    ]
    lines += baseline.statements
    lines += [
        "",
        "-- every generated-identity column the destination schema declares continues",
        "-- from the seeded maximum, the way the engine the source ran on did",
    ]
    lines += baseline.alignment
    return "\n".join(lines) + "\n"


def header(text: str) -> dict[str, str]:
    """The ``-- key: value`` lines at the top of a generated asset."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("--"):
            if line:
                break
            continue
        body = line[2:].strip()
        if ": " not in body:
            continue
        key, _, value = body.partition(": ")
        out.setdefault(key.strip(), value.strip())
    return out


def is_generated(text: str) -> bool:
    return header(text).get("marker") == BASELINE_MARKER


# ---------------------------------------------------------------------------
# the reset contract: what must be true after the load
# ---------------------------------------------------------------------------
def plan_from_asset(text: str) -> dict[str, Any]:
    """Re-measure the generated asset: rows per table, and the sequences it
    aligns. Measured from the BODY, never from the header it also carries."""
    if not is_generated(text):
        raise BaselineRefusal("asset", "the file carries no %s marker; it was not generated by %s" % (BASELINE_MARKER, TRANSLATOR))
    row_counts: dict[str, int] = {}
    sequences: list[dict[str, str]] = []
    for stmt in statements(text, "asset"):
        w = words(stmt)
        if w[:1] == ["INSERT"]:
            table, _columns, rows = parse_insert(stmt, "postgresql")
            row_counts[table] = row_counts.get(table, 0) + len(rows)
            continue
        target = alignment_target(stmt)
        if target is not None:
            sequences.append({"table": target[0], "column": target[1]})
            continue
        raise BaselineRefusal("asset", "the asset carries a statement the reset cannot account for: %s" % stmt.strip())
    return {"row_counts": row_counts, "sequences": sequences,
            "translator": header(text).get("translator", ""),
            "contract_sha256": header(text).get("contract-sha256", ""),
            "declared_dataset": header(text).get("declared-dataset", "")}


def _row_mismatch(table: str, seen: Any, want: int) -> str:
    return "BASELINE %s: %s row(s) after the reset, the derived baseline declares %d" % (table, seen, want)


def _seq_mismatch(table: str, column: str, nxt: Any, want: Any) -> str:
    return "BASELINE %s.%s: the sequence next value is %s but the seeded maximum + 1 is %s" % (table, column, nxt, want)


def _seq_missing(table: str, column: str) -> str:
    return "BASELINE %s.%s: the destination schema declares a generated identity but the engine has no sequence for it" % (table, column)


def verify_observations(plan: dict[str, Any], observed: dict[str, Any]) -> list[str]:
    """The reset's verdict over query results --- the same judgement
    ``verification_sql`` makes inside the database, in a form a test can hand
    canned numbers. [] is a verified baseline."""
    out: list[str] = []
    counts = observed.get("row_counts") or {}
    for table in sorted(plan.get("row_counts") or {}):
        want = int((plan["row_counts"])[table])
        if table not in counts:
            out.append(_row_mismatch(table, "no", want))
            continue
        if int(counts[table]) != want:
            out.append(_row_mismatch(table, int(counts[table]), want))
    seqs = observed.get("sequences") or {}
    for row in plan.get("sequences") or []:
        key = "%s.%s" % (row["table"], row["column"])
        seen = seqs.get(key)
        if not isinstance(seen, dict) or seen.get("next") is None:
            out.append(_seq_missing(row["table"], row["column"]))
            continue
        mx = seen.get("max")
        want = (0 if mx is None else int(mx)) + 1
        if int(seen["next"]) != want:
            out.append(_seq_mismatch(row["table"], row["column"], int(seen["next"]), want))
    return out


def verification_sql(plan: dict[str, Any]) -> str:
    """The same verdict, asserted inside the database after the load: a
    mismatch raises, the reset runner fails, and the reset exits non-zero.

    ``RAISE`` substitutes on ``%``, not on ``%s``: the message text is built
    with the same helpers ``verify_observations`` uses so the two refusals read
    alike, with ``%`` where the value goes."""
    out = ["-- the reset contract: the baseline the derived asset declares is the",
           "-- baseline the database now holds. A mismatch raises."]
    for table in sorted(plan.get("row_counts") or {}):
        want = int(plan["row_counts"][table])
        out.append(
            "DO $baseline$\nDECLARE n bigint;\nBEGIN\n"
            "  SELECT count(*) INTO n FROM %s;\n"
            "  IF n <> %d THEN\n"
            "    RAISE EXCEPTION %s, n;\n"
            "  END IF;\nEND $baseline$;"
            % (quote_name(table), want, quote_literal(_row_mismatch(table, "%", want))))
    for row in plan.get("sequences") or []:
        table, column = str(row["table"]), str(row["column"])
        out.append(
            "DO $baseline$\nDECLARE seq text; lv bigint; ic boolean; mx bigint; nxt bigint; want bigint;\nBEGIN\n"
            "  seq := pg_get_serial_sequence(%s, %s);\n"
            "  IF seq IS NULL THEN\n    RAISE EXCEPTION %s;\n  END IF;\n"
            "  EXECUTE format('SELECT last_value, is_called FROM %%s', seq) INTO lv, ic;\n"
            "  SELECT max(%s) INTO mx FROM %s;\n"
            "  nxt := lv + (CASE WHEN ic THEN 1 ELSE 0 END);\n"
            "  want := COALESCE(mx, 0) + 1;\n"
            "  IF nxt <> want THEN\n    RAISE EXCEPTION %s, nxt, want;\n  END IF;\nEND $baseline$;"
            % (quote_literal(table), quote_literal(column),
               quote_literal(_seq_missing(table, column)),
               quote_name(column), quote_name(table),
               quote_literal(_seq_mismatch(table, column, "%", "%"))))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# where the two inputs and the one output live
# ---------------------------------------------------------------------------
def baseline_path(root: Path, ds: dict[str, Any]) -> Path:
    """Beside the destination schema asset when the decision names one, else
    ``src/main/resources/db/<engine>/``."""
    schema_rel = str(ds.get("schema_sql") or "").strip()
    if schema_rel:
        return Path(root) / Path(schema_rel.replace("\\", "/")).parent / BASELINE_FILENAME
    return Path(root) / RESOURCES / "db" / str(ds.get("db_kind") or "unknown") / BASELINE_FILENAME


def _dataset_from_corpus(corpus: dict[str, Any]) -> tuple[str, str]:
    """(relative path, how the contract named it) or ("", "")."""
    seed = ((corpus.get("derived_from") or {}).get("seed") or {})
    path = str(seed.get("path") or "").strip()
    if path:
        return path.replace("\\", "/"), "corpus derived_from.seed"
    text = str((corpus.get("initial_state") or {}).get("dataset") or "")
    for token in text.replace("(", " ").replace(")", " ").replace(",", " ").split():
        token = token.strip("'\"`;:")
        if token.lower().endswith(".sql"):
            return token.replace("\\", "/"), "corpus initial_state.dataset"
    return "", ""


def discover_dataset(base: Path, source_engine: str) -> str:
    """The same rule derive-source-scenarios.py uses to find the seed: the
    source engine's directory, then the default, then whatever is there."""
    db = Path(base) / RESOURCES / "db"
    if not db.is_dir():
        return ""
    names = [source_engine, DEFAULT_SEED_ENGINE] + sorted(d.name for d in db.iterdir() if d.is_dir())
    for name in names:
        if name and (db / name / SEED_BASENAME).is_file():
            return (RESOURCES / "db" / name / SEED_BASENAME).as_posix()
    return ""


def declared_dataset(root: Path, ds: dict[str, Any], copy: Path | None = None) -> tuple[Path, str, str]:
    """(file, relative path, how it was named). The contract first; discovery
    only when the contract names nothing."""
    root = Path(root)
    rel, named_by = "", ""
    corpus_p = root / CORPUS
    if corpus_p.is_file():
        try:
            rel, named_by = _dataset_from_corpus(json.loads(corpus_p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            rel, named_by = "", ""
    if not rel:
        rel = discover_dataset(root, str(ds.get("source_baseline_db_kind") or ""))
        named_by = "discovery (the source engine's %s)" % SEED_BASENAME if rel else ""
    if not rel and copy is not None and Path(copy).is_dir():
        rel = discover_dataset(Path(copy), str(ds.get("source_baseline_db_kind") or ""))
        named_by = "discovery in the frozen copy" if rel else ""
    if not rel:
        return Path(""), "", ""
    for base in [root] + ([Path(copy)] if copy is not None else []):
        p = Path(base) / rel
        if p.is_file():
            return p, rel, named_by
    return Path(""), rel, named_by


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CLI: the reset asks this module what it must load and what must then be true
# ---------------------------------------------------------------------------
def _hermes_lib() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "lib" / ".hermes-lib").is_file():
            return parent / "lib"
    raise SystemExit("FAIL: .hermes/lib marker missing")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the derived baseline asset the reset loads, and the facts it must then verify")
    ap.add_argument("--root", required=True)
    ap.add_argument("--emit-verify", default="", help="write the post-load verification SQL to this path")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    sys.path.insert(0, str(_hermes_lib()))
    from planner.decisions import DecisionsError, datasource, load_decisions  # noqa: PLC0415

    try:
        ds = datasource(load_decisions(root))
    except DecisionsError as exc:
        print("FAIL: BASELINE %s" % exc, file=sys.stderr)
        return 1
    if not ds:
        print("FAIL: BASELINE the effective datasource is not decided in decisions.yaml", file=sys.stderr)
        return 1
    asset = baseline_path(root, ds)
    if not asset.is_file():
        print("no derived baseline asset at %s" % asset.relative_to(root).as_posix(), file=sys.stderr)
        return 3
    try:
        plan = plan_from_asset(asset.read_text(encoding="utf-8", errors="replace"))
    except BaselineRefusal as exc:
        print("FAIL: BASELINE %s: %s" % (asset.relative_to(root).as_posix(), exc.detail), file=sys.stderr)
        return 1
    if args.emit_verify:
        Path(args.emit_verify).write_text(verification_sql(plan), encoding="utf-8")
    print("baseline: %s" % asset.relative_to(root).as_posix())
    print("dataset: %s" % (plan["declared_dataset"] or "(unrecorded)"))
    print("translator: %s" % (plan["translator"] or "(unrecorded)"))
    print("rows: %s" % (" ".join("%s=%d" % (t, plan["row_counts"][t]) for t in sorted(plan["row_counts"])) or "(none)"))
    print("sequences: %s" % (" ".join("%s.%s" % (s["table"], s["column"]) for s in plan["sequences"]) or "(none)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
