#!/usr/bin/env python3
"""The revert of a fixture variant: what puts the varied columns back.

A refuse-intent fixture variant (ADR-014/ADR-018) refuses the very identity
the read-backs of a refused write would be taken as, so "the refused write
changed nothing" cannot be read under the variant. Instead of inventing a
second identity -- which the architect has refused -- the reads are taken
REVERT-THEN-READ: before the variant is applied (on the verified baseline,
as the base identity), and again after the refused request once the
variant's own changes are reverted. The comparison is after == before.

The revert is COMPUTED, never declared by a worker and never guessed: only
when every fixture statement is a single-column ``UPDATE t SET c = v WHERE
k = w`` and the declared dataset (the baseline the reset verifies) defines one
prior value of ``c`` for the rows ``k = w`` selects. Anything else is a typed
refusal naming the statement. The plan carries what each revert must FIND
before it runs (the variant value, on exactly the baseline's number of rows,
in a table still holding the baseline's number of rows) and what it must
LEAVE (the baseline value on those rows); the SQL asserts both and raises,
inside one block, so a revert that finds unexpected state changes nothing.

Parsing reuses the bootstrap's baseline scanner (no regular expressions: SQL
string literals do not survive one), and literals go through the same
translator the derived baseline is written with. Nothing here names a table,
a column or a value of any specimen.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_BASELINE_TOOL = (Path(__file__).resolve().parents[3] / "migration" / "bootstrap-destination" / "scripts"
                  / "_baseline_data.py")
_spec = importlib.util.spec_from_file_location("_baseline_data_for_revert", _BASELINE_TOOL)
bd = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(bd)  # type: ignore[union-attr]

STRATEGY = "revert_then_read"
ENGINE = "postgresql"          # the engine the revert SQL is written for (the reset's own)
PLAN_SCHEMA = "rhoai3.variant-revert/v1"


class RevertRefusal(Exception):
    """A fixture whose revert is not computable; the message is the typed reason."""


def _top_level_word(text: str, i: int, want: str) -> int:
    """Index of the first bare word ``want`` at or after ``i`` outside any
    literal or parenthesis; -1 when there is none."""
    depth = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            i = bd._end_of_quoted(text, i, "fixture")
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and bd._is_ident_start(c) and (i == 0 or not bd._is_ident_char(text[i - 1])):
            j = i
            while j < n and bd._is_ident_char(text[j]):
                j += 1
            if text[i:j].upper() == want:
                return i
            i = j
            continue
        i += 1
    return -1


def _literal(raw: str, stmt: str) -> str:
    try:
        return bd.translate_literal(raw, ENGINE, stmt)
    except bd.BaselineRefusal as exc:
        raise RevertRefusal("%s; a revert is computed only for a literal value" % exc.detail)


def parse_update(stmt: str) -> dict[str, str]:
    """{table, column, value, where_column, where_value} of one single-column
    UPDATE with one equality predicate; RevertRefusal otherwise."""
    text = stmt.strip().rstrip(";").strip()
    try:
        w = bd.words(text)
    except bd.BaselineRefusal as exc:
        raise RevertRefusal(exc.detail)
    if not w or w[0] != "UPDATE":
        raise RevertRefusal("%r is not an UPDATE; a revert is computed only for single-column UPDATEs" % text)
    try:
        i = bd._expect_word(text, 0, "UPDATE", "fixture")
        raw_table, i = bd._read_identifier(text, i, "fixture")
        i = bd._expect_word(text, i, "SET", "fixture")
        where = _top_level_word(text, i, "WHERE")
        if where < 0:
            raise RevertRefusal("%r updates without a WHERE; which rows it varies is not a set the baseline defines" % text)
        assignment = text[i:where]
        if len([p for p in bd.split_top(assignment, "fixture") if p]) != 1:
            raise RevertRefusal("%r sets more than one column; a revert is computed only for single-column UPDATEs" % text)
        raw_column, j = bd._read_identifier(assignment, 0, "fixture")
        j = bd._skip_ws(assignment, j)
        if assignment[j:j + 1] != "=":
            raise RevertRefusal("%r does not assign its column with =" % text)
        value = assignment[j + 1:].strip()
        predicate = text[where + len("WHERE"):]
        for joiner in ("AND", "OR", "NOT", "IN", "LIKE", "BETWEEN", "IS"):
            if _top_level_word(predicate, 0, joiner) >= 0:
                raise RevertRefusal("%r selects its rows with more than one equality (%s); a revert is computed only for "
                                    "WHERE column = literal" % (text, joiner))
        raw_key, k = bd._read_identifier(predicate, 0, "fixture")
        k = bd._skip_ws(predicate, k)
        if predicate[k:k + 1] != "=" or predicate[k + 1:k + 2] in ("=", ">", "<"):
            raise RevertRefusal("%r does not select its rows with column = literal" % text)
        key_value = predicate[k + 1:].strip()
        return {"table": bd.stored_name(raw_table, ENGINE), "column": bd.stored_name(raw_column, ENGINE),
                "value": _literal(value, text), "where_column": bd.stored_name(raw_key, ENGINE),
                "where_value": _literal(key_value, text)}
    except bd.BaselineRefusal as exc:
        raise RevertRefusal("%r: %s" % (text, exc.detail))


def _seed_rows(seed_text: str, schema_text: str, table: str) -> list[dict[str, str]]:
    """Every declared row of ``table`` as column -> translated literal."""
    try:
        schema = bd.parse_schema(schema_text, ENGINE) if schema_text else {}
        stmts = bd.statements(seed_text, "dataset")
    except bd.BaselineRefusal as exc:
        raise RevertRefusal("the declared dataset cannot be read: %s" % exc.detail)
    rows: list[dict[str, str]] = []
    for stmt in stmts:
        if not bd.words(stmt)[:1] == ["INSERT"]:
            continue
        try:
            name, cols, values = bd.parse_insert(stmt, ENGINE)
        except bd.BaselineRefusal as exc:
            if table.upper() in bd.words(stmt)[2:3]:
                raise RevertRefusal("the declared dataset's rows of %s cannot be read: %s" % (table, exc.detail))
            continue
        if name != table:
            continue
        names = cols or (schema.get(table) or {}).get("columns") or []
        if not names:
            raise RevertRefusal("the declared dataset inserts into %s without naming its columns and no schema declares them" % table)
        for vals in values:
            if len(vals) != len(names):
                raise RevertRefusal("a declared row of %s has %d values for %d columns" % (table, len(vals), len(names)))
            rows.append({c: _literal(v, stmt) for c, v in zip(names, vals)})
    return rows


def compute_plan(statements: list[str], seed_text: str, schema_text: str, dataset: dict[str, str]) -> dict[str, Any]:
    """The revert of a fixture's statements over the declared dataset;
    RevertRefusal with the typed reason when it is not computable."""
    if not statements:
        raise RevertRefusal("the fixture declares no statement to revert")
    rows: list[dict[str, Any]] = []
    touched: set[tuple[str, str]] = set()
    for stmt in statements:
        u = parse_update(str(stmt))
        key = (u["table"], u["column"])
        if key in touched or any((u["table"], u["where_column"]) == t for t in touched):
            raise RevertRefusal("%r changes a column another statement of the same fixture changes or selects on; the "
                                "order of the reverts would matter" % str(stmt).strip())
        touched.add(key)
        table_rows = _seed_rows(seed_text, schema_text, u["table"])
        if not table_rows:
            raise RevertRefusal("the declared dataset %s defines no row of %s" % (dataset.get("path"), u["table"]))
        if any(u["where_column"] not in r or u["column"] not in r for r in table_rows):
            missing = u["column"] if any(u["column"] not in r for r in table_rows) else u["where_column"]
            raise RevertRefusal("the declared dataset %s defines no value of %s.%s, so the baseline value to restore is "
                                "not known" % (dataset.get("path"), u["table"], missing))
        hit = [r for r in table_rows if r[u["where_column"]] == u["where_value"]]
        if not hit:
            raise RevertRefusal("%r selects no row of the declared dataset %s" % (str(stmt).strip(), dataset.get("path")))
        prior = sorted({r[u["column"]] for r in hit})
        if len(prior) != 1:
            raise RevertRefusal("the rows %r selects hold %d different baseline values of %s (%s); one revert cannot "
                                "restore them" % (str(stmt).strip(), len(prior), u["column"], ", ".join(prior)))
        if prior[0] == u["value"]:
            raise RevertRefusal("%r sets %s to the value the baseline already holds; it varies nothing"
                                % (str(stmt).strip(), u["column"]))
        rows.append({"table": u["table"], "column": u["column"], "variant_value": u["value"],
                     "baseline_value": prior[0], "where_column": u["where_column"], "where_value": u["where_value"],
                     "rows": len(hit), "table_rows": len(table_rows), "statement": str(stmt).strip()})
    return {"schema": PLAN_SCHEMA, "strategy": STRATEGY, "engine": ENGINE,
            "dataset": dict(dataset), "rows": rows,
            "statements": [revert_statement(r) for r in rows]}


def revert_statement(row: dict[str, Any]) -> str:
    return "UPDATE %s SET %s = %s WHERE %s = %s" % (
        bd.quote_name(row["table"]), bd.quote_name(row["column"]), row["baseline_value"],
        bd.quote_name(row["where_column"]), row["where_value"])


def plan_gap(plan: Any) -> str:
    """Why a recorded plan may not be executed; "" when it may."""
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA or plan.get("strategy") != STRATEGY:
        return "no %s revert plan is recorded" % STRATEGY
    if plan.get("engine") != ENGINE:
        return "the revert plan is written for %r and this reset speaks %s" % (plan.get("engine"), ENGINE)
    rows = plan.get("rows")
    if not isinstance(rows, list) or not rows:
        return "the revert plan names no row"
    for r in rows:
        if not isinstance(r, dict) or any(not str(r.get(k) or "") for k in (
                "table", "column", "variant_value", "baseline_value", "where_column", "where_value")):
            return "a revert row is incomplete"
        if int(r.get("rows") or 0) < 1 or int(r.get("table_rows") or 0) < int(r.get("rows") or 0):
            return "a revert row names no row count"
        try:
            for field in ("variant_value", "baseline_value", "where_value"):
                if _literal(str(r[field]), "revert plan") != str(r[field]):
                    return "a revert row carries a value that is not a translated literal"
            for field in ("table", "column", "where_column"):
                if bd.stored_name(str(r[field]), ENGINE) != str(r[field]):
                    return "a revert row carries a name that is not a stored identifier"
        except (RevertRefusal, bd.BaselineRefusal) as exc:
            return "a revert row is unusable: %s" % exc
    return ""


def revert_sql(plan: dict[str, Any]) -> str:
    """One block, all or nothing: each row must first be FOUND in the variant
    state -- the table still holds the baseline's row count, the predicate
    selects the baseline's rows, and every one of them holds the variant
    value -- then the update must touch exactly those rows, and they must then
    hold the baseline value. A RAISE rolls the whole block back."""
    gap = plan_gap(plan)
    if gap:
        raise RevertRefusal(gap)
    body: list[str] = []
    for r in plan["rows"]:
        t, c, k = bd.quote_name(r["table"]), bd.quote_name(r["column"]), bd.quote_name(r["where_column"])
        where = "%s = %s" % (k, r["where_value"])
        label = "%s.%s where %s" % (r["table"], r["column"], where)

        def check(sql: str, want: int, what: str) -> str:
            return ("  %s\n  IF n <> %d THEN\n    RAISE EXCEPTION %s, n;\n  END IF;"
                    % (sql, want, bd.quote_literal("REVERT_UNEXPECTED_STATE %s: %s (found %%, expected %d)" % (label, what, want))))

        body.append(check("SELECT count(*) INTO n FROM %s;" % t, int(r["table_rows"]),
                          "the table no longer holds the baseline's row count"))
        body.append(check("SELECT count(*) INTO n FROM %s WHERE %s;" % (t, where), int(r["rows"]),
                          "the predicate does not select the baseline's rows"))
        body.append(check("SELECT count(*) INTO n FROM %s WHERE %s AND %s IS NOT DISTINCT FROM %s;"
                          % (t, where, c, r["variant_value"]), int(r["rows"]),
                          "the rows do not hold the variant value %s" % r["variant_value"]))
        body.append(check("UPDATE %s SET %s = %s WHERE %s;\n  GET DIAGNOSTICS n = ROW_COUNT;"
                          % (t, c, r["baseline_value"], where), int(r["rows"]),
                          "the revert did not update exactly the baseline's rows"))
        body.append(check("SELECT count(*) INTO n FROM %s WHERE %s AND %s IS NOT DISTINCT FROM %s;"
                          % (t, where, c, r["baseline_value"]), int(r["rows"]),
                          "the rows do not hold the baseline value %s after the revert" % r["baseline_value"]))
    return ("-- revert of a fixture variant (%s): found in the variant state, restored to the baseline,\n"
            "-- or nothing changes\nDO $revert$\nDECLARE n bigint;\nBEGIN\n%s\nEND $revert$;\n"
            % (STRATEGY, "\n".join(body)))


def observation_gaps(plan: dict[str, Any], before: dict[int, dict[str, int]], after: dict[int, dict[str, int]]) -> list[str]:
    """The same judgement as ``revert_sql`` over query results, for a test
    without a database: ``before[i]`` holds ``table_rows``, ``selected`` and
    ``variant`` counts for row i, ``after[i]`` holds ``updated`` and
    ``baseline``. [] when the revert holds."""
    out: list[str] = []
    for i, r in enumerate(plan.get("rows") or []):
        b, a = before.get(i) or {}, after.get(i) or {}
        want = int(r["rows"])
        for name, got, exp in (("table_rows", b.get("table_rows"), int(r["table_rows"])), ("selected", b.get("selected"), want),
                               ("variant", b.get("variant"), want), ("updated", a.get("updated"), want),
                               ("baseline", a.get("baseline"), want)):
            if got != exp:
                out.append("REVERT_UNEXPECTED_STATE %s.%s: %s %s, expected %s" % (r["table"], r["column"], name, got, exp))
                break
    return out


if __name__ == "__main__":
    sys.exit("a library; see reset-parity-db.sh --revert-variant")
