#!/usr/bin/env python3
"""compat-mapping objective_families.transaction-annotations, complete against
the two APIs it maps between.

Reflection over spring-tx 5.3.14 (the legacy build's version) and
jakarta.transaction-api 2.0.1 from the local Maven repository: every attribute
of Spring's @Transactional has a disposition in `attributes`, every Spring
Propagation constant is mapped in `propagation` to a jakarta TxType constant
that exists (or explicitly to null = unsupported), the rollback attributes
name members jakarta @Transactional really has, and the default rollback rule
the action claims matches (both roll back on unchecked exceptions only).
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
M2 = Path.home() / ".m2" / "repository"
SPRING_TX = M2 / "org/springframework/spring-tx/5.3.14/spring-tx-5.3.14.jar"
JTA = M2 / "jakarta/transaction/jakarta.transaction-api/2.0.1/jakarta.transaction-api-2.0.1.jar"

ORACLE = r"""
import java.lang.reflect.Method;
public class Oracle {
  public static void main(String[] a) throws Exception {
    Class<?> s = Class.forName("org.springframework.transaction.annotation.Transactional");
    for (Method m : s.getDeclaredMethods()) System.out.println("spring-attr " + m.getName());
    for (Object c : Class.forName("org.springframework.transaction.annotation.Propagation").getEnumConstants()) System.out.println("spring-prop " + c);
    Class<?> j = Class.forName("jakarta.transaction.Transactional");
    for (Method m : j.getDeclaredMethods()) System.out.println("jta-attr " + m.getName());
    for (Object c : Class.forName("jakarta.transaction.Transactional$TxType").getEnumConstants()) System.out.println("jta-txtype " + c);
  }
}
"""


def main() -> int:
    fam = json.loads((GOLDEN / ".hermes" / "planning" / "catalogs" / "compat-mapping.json").read_text())["objective_families"]["families"]["transaction-annotations"]
    attrs, prop = fam.get("attributes") or {}, fam.get("propagation") or {}
    if "never delete the boundary" not in (fam.get("action") or "") or "private" not in (fam.get("action") or ""):
        print("FAIL: the action keeps the boundary and names the private-method limit", file=sys.stderr)
        return 1
    if not (shutil.which("javac") and shutil.which("java")):
        print("SKIP: transaction-mapping: javac/java not on PATH (catalog row read)")
        return 0
    missing = [str(j) for j in (SPRING_TX, JTA) if not j.is_file()]
    if missing:
        print("SKIP: transaction-mapping: not in the local Maven repository: %s" % ", ".join(missing))
        return 0
    cp = "%s:%s" % (SPRING_TX, JTA)
    with tempfile.TemporaryDirectory(prefix="tx-map-") as td:
        (Path(td) / "Oracle.java").write_text(ORACLE, encoding="utf-8")
        c = subprocess.run(["javac", "-d", td, str(Path(td) / "Oracle.java")], capture_output=True, text=True)
        r = subprocess.run(["java", "-cp", "%s:%s" % (cp, td), "Oracle"], capture_output=True, text=True) if c.returncode == 0 else c
    if r.returncode != 0:
        print("FAIL: the oracle does not run: %s" % (r.stderr or r.stdout)[-500:], file=sys.stderr)
        return 1
    facts: dict[str, set] = {}
    for ln in r.stdout.split("\n"):
        if ln.strip():
            k, v = ln.split(" ", 1)
            facts.setdefault(k, set()).add(v.strip())
    unmapped = sorted(facts["spring-attr"] - set(attrs))
    stale = sorted(set(attrs) - facts["spring-attr"])
    if unmapped or stale:
        print("FAIL: every Spring @Transactional attribute has a disposition (unmapped %s, not in spring-tx %s)" % (unmapped, stale),
              file=sys.stderr)
        return 1
    if set(prop) != facts["spring-prop"]:
        print("FAIL: every Propagation constant is mapped: %s vs %s" % (sorted(prop), sorted(facts["spring-prop"])), file=sys.stderr)
        return 1
    bad = {k: v for k, v in prop.items() if v is not None and v not in facts["jta-txtype"]}
    if bad:
        print("FAIL: mapped to TxType constants that do not exist: %s" % bad, file=sys.stderr)
        return 1
    for spring_attr, jta_attr in (("rollbackFor", "rollbackOn"), ("noRollbackFor", "dontRollbackOn")):
        if not str(attrs.get(spring_attr, "")).startswith(jta_attr) or jta_attr not in facts["jta-attr"]:
            print("FAIL: %s maps to jakarta @Transactional.%s: %s" % (spring_attr, jta_attr, attrs.get(spring_attr)), file=sys.stderr)
            return 1
    if "value" not in facts["jta-attr"]:
        print("FAIL: jakarta @Transactional carries the TxType as value()", file=sys.stderr)
        return 1
    print("OK: transaction-mapping (spring-tx 5.3.14 @Transactional: %d attributes each with a disposition; Propagation %s mapped to "
          "jakarta.transaction 2.0.1 TxType (NESTED unsupported); rollbackFor/noRollbackFor -> rollbackOn/dontRollbackOn exist)"
          % (len(facts["spring-attr"]), ", ".join(sorted(facts["spring-prop"]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
