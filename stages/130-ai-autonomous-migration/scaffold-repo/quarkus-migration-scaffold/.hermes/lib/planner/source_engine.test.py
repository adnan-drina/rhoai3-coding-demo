#!/usr/bin/env python3
"""D-1: the source capture engine and its seed, one rule for the derivation and the destination baseline.

Run: PYTHONDONTWRITEBYTECODE=1 python3 .hermes/lib/planner/source_engine.test.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.source_engine import CAPTURE_SCHEMA, capture_engine, seed, sequence_starts, serial_sequence, server_capture, source_profile_for  # noqa: E402


def source(td: Path, engines, profiles) -> Path:
    for e in engines:
        d = td / "src" / "main" / "resources" / "db" / e
        d.mkdir(parents=True, exist_ok=True)
        (d / "populateDB.sql").write_text("INSERT INTO t VALUES (1);\n")
    for e, suf in profiles:
        (td / "src" / "main" / "resources" / ("application-%s%s" % (e, suf))).write_text("x=1\n")
    return td


class Engine(unittest.TestCase):
    def check(self, dest, declared):
        with tempfile.TemporaryDirectory() as t:
            copy = source(Path(t), [declared, dest], [(dest, ".properties")])
            ds = {"db_kind": dest, "source_baseline_db_kind": declared}
            got = capture_engine(ds, copy)
            self.assertEqual((got["engine"], got["mode"]), (declared, "declared"))           # the default: ADR-017
            got = capture_engine(dict(ds, source_capture_engine="destination"), copy)
            self.assertEqual((got["engine"], got["mode"], got["profile"]), (dest, "destination", dest))
            self.assertEqual(got["profile_file"], "src/main/resources/application-%s.properties" % dest)
            self.assertEqual(seed(copy, got["engine"])[1], dest)                            # the seed follows the engine
        with tempfile.TemporaryDirectory() as t:
            copy = source(Path(t), [declared], [])                                          # no profile for the destination
            got = capture_engine({"db_kind": dest, "source_baseline_db_kind": declared, "source_capture_engine": "destination"}, copy)
            self.assertEqual((got["engine"], got["mode"]), (declared, "declared"))
            self.assertIn("ships no profile for the destination engine %s" % dest, got["why"])
            self.assertEqual(source_profile_for(copy, dest), "")

    def test_postgresql_over_hsqldb(self):
        self.check("postgresql", "hsqldb")

    def test_a_renamed_engine_pair(self):
        self.check("mariadb", "h2")

    def test_an_unknown_mode_is_the_declared_engine(self):
        self.assertEqual(capture_engine({"db_kind": "x", "source_baseline_db_kind": "y", "source_capture_engine": "both"})["engine"], "y")


class ServerCapture(unittest.TestCase):
    """D-1 increment 2: the plan for capturing the frozen source on the destination's server engine."""

    def tree(self, t: Path, active: str, engine_profile: str, other: str, schema_name: str, schema_locations: str = "") -> Path:
        res = t / "src" / "main" / "resources"
        (res / "db" / "postgresql").mkdir(parents=True)
        (t / "pom.xml").write_text("<project><parent><artifactId>spring-boot-starter-parent</artifactId></parent></project>")
        (res / "application.properties").write_text("# active profiles\nspring.profiles.active=%s\n" % active)
        (res / ("application-%s.properties" % engine_profile)).write_text("x=1\n")
        (res / "application-postgresql.properties").write_text(
            ("%s=%s\n" % ("spring.sql.init.schema-locations", schema_locations) if schema_locations else "")
            + "#spring.sql.init.schema-locations=classpath*:db/postgresql/ignored.sql\n")
        (res / "db" / "postgresql" / schema_name).write_text("CREATE TABLE a (id INT);\n")
        (res / "db" / "postgresql" / "populateDB.sql").write_text("INSERT INTO a VALUES (1);\n")
        return t

    DS = {"db_kind": "postgresql", "source_baseline_db_kind": "hsqldb", "source_capture_engine": "destination",
          "jdbc_url_env": "RUN_DB_URL", "username_env": "RUN_DB_USER", "password_env": "RUN_DB_PASSWORD"}
    ENV = {"RUN_DB_URL": "jdbc:postgresql://db.ns:5432/parity?sslmode=disable&currentSchema=public",
           "RUN_DB_USER": "u", "RUN_DB_PASSWORD": "secret-value"}

    def plan_of(self, active, engine_profile, other, schema_name, **kw):
        with tempfile.TemporaryDirectory() as t:
            copy = self.tree(Path(t), active, engine_profile, other, schema_name, **kw)
            return server_capture(self.DS, copy, dict(self.ENV))

    def assert_plan(self, plan, profiles, schema_sql):
        self.assertNotIn("refused", plan, plan)
        self.assertEqual(plan["profiles"], profiles)                      # the engine profile replaced, the rest kept in order
        self.assertEqual(plan["schema_sql"], schema_sql)
        self.assertEqual(plan["seed_sql"], "src/main/resources/db/postgresql/populateDB.sql")
        url = plan["env"]["SPRING_DATASOURCE_URL"]
        self.assertTrue(url.startswith("jdbc:postgresql://db.ns:5432/parity?"))
        self.assertIn("sslmode=disable", url)
        self.assertEqual(url.count("currentSchema="), 1)                  # an existing schema selector is replaced
        self.assertTrue(url.endswith("currentSchema=%s" % CAPTURE_SCHEMA))
        self.assertEqual(plan["env"]["SPRING_PROFILES_ACTIVE"], ",".join(profiles))
        recorded = {k: v for k, v in plan.items() if k != "env"}
        self.assertNotIn("secret-value", repr(recorded))                  # credentials never leave the env map
        self.assertEqual(plan["env_names"], sorted(plan["env"]))

    def test_petclinic_shape(self):
        self.assert_plan(self.plan_of("hsqldb,spring-data-jpa", "hsqldb", "", "initDB.sql"),
                         ["postgresql", "spring-data-jpa"], "src/main/resources/db/postgresql/initDB.sql")

    def test_renamed_twin(self):
        # another engine profile name, another selection profile, another schema script name, declared location
        self.assert_plan(self.plan_of("ledger-store,h2", "h2", "", "tables.sql",
                                      schema_locations="classpath:db/postgresql/tables.sql"),
                         ["postgresql", "ledger-store"], "src/main/resources/db/postgresql/tables.sql")

    def test_refusals_are_named(self):
        with tempfile.TemporaryDirectory() as t:
            copy = self.tree(Path(t), "hsqldb", "hsqldb", "", "initDB.sql")
            (copy / "src/main/resources/db/postgresql/second.sql").write_text("create table b (id int);\n")
            self.assertIn("not decidable", server_capture(self.DS, copy, dict(self.ENV))["refused"])
        with tempfile.TemporaryDirectory() as t:
            copy = self.tree(Path(t), "hsqldb", "hsqldb", "", "initDB.sql")
            self.assertIn("RUN_DB_PASSWORD", server_capture(self.DS, copy, {"RUN_DB_URL": "jdbc:postgresql://h/d", "RUN_DB_USER": "u"})["refused"])
            self.assertIn("not a postgresql JDBC URL", server_capture(self.DS, copy, dict(self.ENV, RUN_DB_URL="jdbc:mysql://h/d"))["refused"])
            (copy / "pom.xml").write_text("<project/>")
            self.assertIn("not a Spring Boot build", server_capture(self.DS, copy, dict(self.ENV))["refused"])
            declared = dict(self.DS, source_capture_engine="declared")
            self.assertIn("declared engine", server_capture(declared, copy, dict(self.ENV))["refused"])


class SequenceStarts(unittest.TestCase):
    """L-3: the identity the capture engine generates next is where its schema (re)starts the serial sequence."""

    def test_restart_positions_by_serial_name(self):
        for table, column in (("vets", "id"), ("ledger_entries", "entry_no")):
            text = ("CREATE TABLE %s (%s SERIAL);\nALTER SEQUENCE %s RESTART WITH 100;\n"
                    "alter sequence if exists \"other_seq\" start with 7;\n" % (table, column, serial_sequence(table, column)))
            got = sequence_starts(text)
            self.assertEqual(got[serial_sequence(table, column)], 100)
            self.assertEqual(got["other_seq"], 7)
        self.assertEqual(sequence_starts("CREATE TABLE t (id INTEGER IDENTITY PRIMARY KEY);"), {})   # an engine that continues


if __name__ == "__main__":
    unittest.main()
