#!/usr/bin/env python3
"""check-empty-security: method security with nothing to authenticate against.

Measured on destination v9 (2026-09-15): every read answered 403 while this
gate passed as idle. The annotations were on the resources -- @PreAuthorize,
@RolesAllowed -- the pom carried quarkus-spring-security, and no extension or
property gave the application an identity to check them against. The gate only
ever opened *Security*.java, found none, and called the phase idle.

The decisions here are about the SHAPE of the tree, never about a specimen:
the last case renames every package and type and must decide identically.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "check-empty-security.py"


def _fail(msg: str) -> int:
    print("FAIL: " + msg, file=sys.stderr)
    return 1


def pom(*artifacts: str) -> str:
    deps = "\n".join(
        "    <dependency>\n      <groupId>io.quarkus</groupId>\n"
        "      <artifactId>%s</artifactId>\n    </dependency>" % a
        for a in artifacts
    )
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<project>\n  <modelVersion>4.0.0</modelVersion>\n"
            "  <groupId>demo</groupId>\n  <artifactId>demo</artifactId>\n  <version>1.0</version>\n"
            "  <dependencies>\n%s\n  </dependencies>\n</project>\n" % deps)


def resource(pkg: str, name: str, annotations: str) -> str:
    return ("package %s;\n\nimport jakarta.ws.rs.GET;\n\npublic class %s {\n"
            "%s    @GET\n    public String list() { return \"[]\"; }\n}\n" % (pkg, name, annotations))


def build(td: Path, *, java: dict[str, str] | None = None, artifacts: tuple[str, ...] = (),
          props: str = "") -> Path:
    root = td
    for rel, text in (java or {}).items():
        p = root / "src/main/java" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    (root / "src/main/resources").mkdir(parents=True, exist_ok=True)
    (root / "src/main/resources/application.properties").write_text(props, encoding="utf-8")
    (root / "pom.xml").write_text(pom(*artifacts), encoding="utf-8")
    return root


def run(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), str(root)], text=True, capture_output=True)


def case(label: str, expect_rc: int, needles: tuple[str, ...] = (), **kw) -> int:
    with tempfile.TemporaryDirectory(prefix="empty-security-") as td:
        root = build(Path(td), **kw)
        proc = run(root)
        blob = proc.stdout + proc.stderr
        if proc.returncode != expect_rc:
            return _fail("%s: rc=%d, expected %d\n%s" % (label, proc.returncode, expect_rc, blob))
        for n in needles:
            if n not in blob:
                return _fail("%s: the message must name %r\n%s" % (label, n, blob))
    return 0


ANNOTATED = {"org/acme/api/OwnerResource.java": resource("org.acme.api", "OwnerResource", "    @PreAuthorize(\"hasRole('USER')\")\n"),
             "org/acme/api/VetResource.java": resource("org.acme.api", "VetResource", "    @RolesAllowed({\"USER\"})\n")}
# The same shape with every name changed: a different package root, different
# type names, a different annotation of the same family.
RENAMED = {"com/example/web/BookEndpoint.java": resource("com.example.web", "BookEndpoint", "    @Secured(\"ROLE_READER\")\n"),
           "com/example/web/AdminEndpoint.java": resource("com.example.web", "AdminEndpoint", "    @DenyAll\n")}
PLAIN = {"org/acme/api/OwnerResource.java": resource("org.acme.api", "OwnerResource", "")}


def main() -> int:
    checks = [
        # annotations, security extension, no provider anywhere → BLOCK, and
        # the message says what was found, what is missing, and what it costs
        ("annotations + no provider", 1,
         ("@PreAuthorize", "@RolesAllowed", "quarkus-spring-security", "quarkus-security-jpa", "403"),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security", "quarkus-resteasy-reactive")}),
        # the umbrella extension alone is no better: it enables the annotations
        ("annotations + quarkus-security only", 1, ("no identity provider",),
         {"java": ANNOTATED, "artifacts": ("quarkus-security",)}),
        # an identity provider is what makes the annotations answerable
        ("annotations + quarkus-security-jpa", 0, ("idle",),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa")}),
        ("annotations + quarkus-oidc", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-security", "quarkus-oidc")}),
        # a configured identity counts as one, profile prefix included
        ("annotations + configured users", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-security",),
          "props": "%prod.quarkus.security.users.embedded.enabled=true\n"}),
        ("annotations + http auth policy", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security",),
          "props": "quarkus.http.auth.basic=true\n"}),
        # no annotations, security not enabled → the gate stays idle
        ("no annotations, security off", 0, ("idle",),
         {"java": PLAIN, "artifacts": ("quarkus-resteasy-reactive",)}),
        ("no annotations, security extension present", 0, ("idle",),
         {"java": PLAIN, "artifacts": ("quarkus-security",)}),
        # the same decisions under different names
        ("renamed package/types, no provider", 1, ("@Secured", "@DenyAll", "403"),
         {"java": RENAMED, "artifacts": ("quarkus-security",)}),
        ("renamed package/types + provider", 0, (),
         {"java": RENAMED, "artifacts": ("quarkus-security", "quarkus-elytron-security-properties-file")}),
        # a substring is not an artifactId: the provider alone must not read as
        # "quarkus-security present, provider missing"
        ("provider only, no umbrella extension", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-security-jdbc",)}),
        # a javadoc that mentions the annotation is documentation, not a rule
        ("annotation only in a comment", 0, ("idle",),
         {"java": {"org/acme/api/Doc.java": "package org.acme.api;\n/** Use @RolesAllowed when this lands. */\npublic class Doc { }\n"},
          "artifacts": ("quarkus-security",)}),
    ]
    for label, rc, needles, kw in checks:
        if case(label, rc, needles, **kw):
            return 1
    print("OK: check-empty-security (method security with no identity provider BLOCKs and names the annotations, "
          "the missing provider and the 403; an extension or a configured identity passes; no annotations stays "
          "idle; artifactIds are matched whole; comments are not rules; renamed packages decide the same)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
