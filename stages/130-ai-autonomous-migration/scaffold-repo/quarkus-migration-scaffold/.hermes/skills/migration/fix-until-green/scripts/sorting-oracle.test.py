#!/usr/bin/env python3
"""compat-mapping objective_families.collection-sorting action, against Spring.

Spring's own PropertyComparator.sort (spring-beans 5.3.14, the legacy
build's version, from the local Maven repository) and the catalog's plain-Java
translation sort the same list -- null keys, mixed case, equal keys (stability)
-- for every (ignoreCase, ascending) combination; the orders must be
identical. Negative control: the translation without .reversed() for a
descending sort, and a nullsFirst ascending variant, must differ from Spring.
SKIP with the reason when the jars or the JDK are absent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLDEN = HERE.parents[4]
M2 = Path.home() / ".m2" / "repository" / "org" / "springframework"
V = "5.3.14"
JARS = [M2 / a / V / ("%s-%s.jar" % (a, V)) for a in ("spring-beans", "spring-core", "spring-jcl")]

ORACLE = r"""
import java.util.*;
import org.springframework.beans.support.*;
public class Oracle {
  public static class Row {
    final String name; final int seq;
    Row(String n, int s) { name = n; seq = s; }
    public String getName() { return name; }
    public String toString() { return name + "#" + seq; }
  }
  static List<Row> data() {
    String[] names = {"beta", null, "Alpha", "alpha", "Beta", null, "gamma", "alpha"};
    List<Row> l = new ArrayList<>();
    for (int i = 0; i < names.length; i++) l.add(new Row(names[i], i));
    return l;
  }
  static Comparator<Row> translated(boolean ignoreCase, boolean ascending, boolean control) {
    Comparator<Row> c = ignoreCase
        ? Comparator.comparing((Row x) -> x.getName() == null ? null : x.getName().toLowerCase(), Comparator.nullsLast(Comparator.<String>naturalOrder()))
        : Comparator.comparing(Row::getName, Comparator.nullsLast(Comparator.<String>naturalOrder()));
    if (control) return ascending ? Comparator.comparing(Row::getName, Comparator.nullsFirst(Comparator.<String>naturalOrder())) : c;
    return ascending ? c : c.reversed();
  }
  public static void main(String[] a) {
    for (boolean ic : new boolean[]{false, true}) for (boolean asc : new boolean[]{true, false}) {
      List<Row> s = data(); PropertyComparator.sort(s, new MutableSortDefinition("name", ic, asc));
      List<Row> t = data(); t.sort(translated(ic, asc, false));
      List<Row> n = data(); n.sort(translated(ic, asc, true));
      System.out.println(ic + " " + asc + " | " + s + " | " + t + " | " + n);
    }
  }
}
"""


def main() -> int:
    fam = json.loads((GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text())["objective_families"]["families"]["collection-sorting"]
    act = fam.get("action") or ""
    for token in ("Comparator.nullsLast(Comparator.naturalOrder())", ".reversed()", "toLowerCase()", "never add spring-beans"):
        if token not in act:
            print("FAIL: the collection-sorting action names %r" % token, file=sys.stderr)
            return 1
    if not (shutil.which("javac") and shutil.which("java")):
        print("SKIP: sorting-oracle: javac/java not on PATH (catalog row checked)")
        return 0
    missing = [str(j) for j in JARS if not j.is_file()]
    if missing:
        print("SKIP: sorting-oracle: not in the local Maven repository: %s (catalog row checked)" % ", ".join(missing))
        return 0
    cp = ":".join(str(j) for j in JARS)
    with tempfile.TemporaryDirectory(prefix="sort-oracle-") as td:
        (Path(td) / "Oracle.java").write_text(ORACLE, encoding="utf-8")
        c = subprocess.run(["javac", "-cp", cp, "-d", td, str(Path(td) / "Oracle.java")], capture_output=True, text=True)
        if c.returncode != 0:
            print("FAIL: the oracle does not compile: %s" % c.stderr[-500:], file=sys.stderr)
            return 1
        r = subprocess.run(["java", "-cp", "%s:%s" % (cp, td), "Oracle"], capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL: the oracle does not run: %s" % r.stderr[-500:], file=sys.stderr)
        return 1
    lines = r.stdout.strip().splitlines()
    rows = [[p.strip() for p in ln.split("|")] for ln in lines]
    if len(rows) != 4 or any(s != t for _k, s, t, _n in rows):
        print("FAIL: Spring's PropertyComparator and the translation disagree:\n%s" % r.stdout, file=sys.stderr)
        return 1
    if all(s == n for _k, s, _t, n in rows):
        print("FAIL: the negative controls (nullsFirst ascending, no .reversed() descending) must differ from Spring", file=sys.stderr)
        return 1
    for ln in lines:
        print("  " + ln)
    print("OK: sorting-oracle (spring-beans %s PropertyComparator == the catalog translation for ignoreCase x ascending over nulls, "
          "case and ties; the controls differ)" % V)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
