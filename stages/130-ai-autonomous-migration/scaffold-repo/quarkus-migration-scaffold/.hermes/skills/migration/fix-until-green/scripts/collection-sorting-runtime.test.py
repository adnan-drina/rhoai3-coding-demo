#!/usr/bin/env python3
"""compat-mapping objective_families.collection-sorting, on a destination package.

The SOURCE order is Spring's own PropertyComparator.sort(list, new
MutableSortDefinition("name", ignoreCase, ascending)) (spring-beans 5.3.14 from
the local Maven repository, sorting-oracle.test.py's oracle), for every
(ignoreCase, ascending) combination over null names, mixed case and equal keys
(stability). The DESTINATION order is served by fixtures/handler-location-package
packaged on the pinned platform with one more Spring Web controller that sorts
the same rows in place with the catalog's action:

  translated   Comparator.comparing(<key>, Comparator.nullsLast(Comparator.naturalOrder())),
               the key lower-cased when ignoreCase, .reversed() when descending
  no-reversed  negative control: the descending sort without .reversed()
  nulls-first  negative control: Comparator.nullsFirst for the ascending sort

The translated order must equal Spring's for all four combinations (so a null
sorts LAST ascending and FIRST descending, and ties keep their input order); each
control must differ from Spring on the combination it breaks. SKIP with the
reason when a prerequisite (mvn, java/javac, the spring jars, the pinned
artifacts offline, a loopback port) is missing; a SKIP is never a PASS.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_runtime_fixture as rt  # noqa: E402

_spec = importlib.util.spec_from_file_location("sorting_oracle", HERE / "sorting-oracle.test.py")
ORACLE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ORACLE)  # type: ignore[union-attr]

FIXTURE = rt.FIXTURES / "handler-location-package"
CONTROLLER = "src/main/java/org/acme/ledger/rest/RowRestController.java"
SOURCE = r"""package org.acme.ledger.rest;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/rows")
public class RowRestController {
    public static class Row {
        final String name; final int seq;
        Row(String n, int s) { name = n; seq = s; }
        public String getName() { return name; }
        public String toString() { return name + "#" + seq; }
    }

    // the same rows, in the same input order, as sorting-oracle's Spring oracle
    static List<Row> data() {
        String[] names = {"beta", null, "Alpha", "alpha", "Beta", null, "gamma", "alpha"};
        List<Row> l = new ArrayList<>();
        for (int i = 0; i < names.length; i++) l.add(new Row(names[i], i));
        return l;
    }

    @GetMapping(produces = "text/plain")
    public String sorted(@RequestParam("ignoreCase") boolean ignoreCase, @RequestParam("ascending") boolean ascending,
                         @RequestParam("variant") String variant) {
        List<Row> rows = data();
        // the catalog's action: PropertyComparator.sort(rows, new MutableSortDefinition("name", ignoreCase, ascending))
        Comparator<Row> c = ignoreCase
            ? Comparator.comparing((Row x) -> x.getName() == null ? null : x.getName().toLowerCase(), Comparator.nullsLast(Comparator.naturalOrder()))
            : Comparator.comparing(Row::getName, Comparator.nullsLast(Comparator.naturalOrder()));
        if ("no-reversed".equals(variant)) {
            rows.sort(c);
        } else if ("nulls-first".equals(variant)) {
            rows.sort(ascending ? Comparator.comparing(Row::getName, Comparator.nullsFirst(Comparator.naturalOrder())) : c.reversed());
        } else {
            rows.sort(ascending ? c : c.reversed());
        }
        return rows.toString();
    }
}
"""
COMBOS = [(ic, asc) for ic in (False, True) for asc in (True, False)]


def spring_orders(td: Path) -> dict:
    """{(ignoreCase, ascending): Spring PropertyComparator's order as List.toString()}."""
    missing = [str(j) for j in ORACLE.JARS if not j.is_file()]
    if missing:
        raise rt.Skip("not in the local Maven repository: %s" % ", ".join(missing))
    cp = ":".join(str(j) for j in ORACLE.JARS)
    (td / "Oracle.java").write_text(ORACLE.ORACLE, encoding="utf-8")
    c = subprocess.run(["javac", "-cp", cp, "-d", str(td), str(td / "Oracle.java")], capture_output=True, text=True)
    if c.returncode != 0:
        raise RuntimeError("the Spring oracle does not compile: %s" % c.stderr[-500:])
    r = subprocess.run(["java", "-cp", "%s:%s" % (cp, td), "Oracle"], capture_output=True, text=True, check=True)
    out = {}
    for ln in r.stdout.strip().splitlines():
        key, spring = [p.strip() for p in ln.split("|")][:2]
        ic, asc = key.split()
        out[(ic == "true", asc == "true")] = spring
    return out


def main() -> int:
    try:
        rt.need_tools("mvn", "java", "javac")
        with tempfile.TemporaryDirectory(prefix="sorting-rt-") as td:
            spring = spring_orders(Path(td))
            root = Path(td) / "app"
            shutil.copytree(FIXTURE, root)
            (root / CONTROLLER).write_text(SOURCE, encoding="utf-8")
            ok, out = rt.package(root)
            if not ok:
                print("FAIL: the destination packages: %s" % out[-900:], file=sys.stderr)
                return 1
            dest: dict = {}
            with rt.boot(root, "/") as base:
                for variant in ("translated", "no-reversed", "nulls-first"):
                    for ic, asc in COMBOS:
                        st, _h, body = rt.http("GET", base + "/ledger/api/rows?ignoreCase=%s&ascending=%s&variant=%s"
                                               % (str(ic).lower(), str(asc).lower(), variant))
                        dest[(variant, ic, asc)] = body if st == 200 else "HTTP %s" % st
    except rt.Skip as exc:
        print("SKIP: collection-sorting-runtime: %s" % exc)
        return 0
    for ic, asc in COMBOS:
        print("ignoreCase=%-5s ascending=%-5s spring %s" % (ic, asc, spring[(ic, asc)]))
        for variant in ("translated", "no-reversed", "nulls-first"):
            print("%38s %s" % (variant, dest[(variant, ic, asc)]))
    bad = [(ic, asc) for ic, asc in COMBOS if dest[("translated", ic, asc)] != spring[(ic, asc)]]
    if bad:
        print("FAIL: the destination's translated order differs from Spring's PropertyComparator for %s" % bad, file=sys.stderr)
        return 1
    if all(dest[("no-reversed", ic, False)] == spring[(ic, False)] for ic in (False, True)):
        print("FAIL: the no-reversed control must differ from Spring's descending order", file=sys.stderr)
        return 1
    if dest[("nulls-first", False, True)] == spring[(False, True)]:
        print("FAIL: the nulls-first control must differ from Spring's ascending order", file=sys.stderr)
        return 1
    print("OK: collection-sorting-runtime (pinned platform %s, packaged jar over HTTP: the catalog's Comparator translation "
          "serves spring-beans %s PropertyComparator's order for ignoreCase x ascending over nulls (last ascending, first "
          "descending), case and ties; the no-reversed and nulls-first controls differ)" % (rt.pin()["version"], ORACLE.V))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
