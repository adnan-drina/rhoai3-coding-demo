#!/usr/bin/env python3
"""check-empty-security: method security with nothing to authenticate against.

Measured on destination v9 (2026-09-15): every read answered 403 while this
gate passed as idle. The annotations were on the resources -- @PreAuthorize,
@RolesAllowed -- the pom carried quarkus-spring-security, and no extension or
property gave the application an identity to check them against. The gate only
ever opened *Security*.java, found none, and called the phase idle.

ADR-014 added the other half: which provider is "the" provider is the migration
design's decision, not this gate's. The gate used to name one extension
(quarkus-elytron-security-jdbc) and one shape of role constant (`static final`)
and refuse everything else -- it refused the JPA provider the ADR decided, and
it refused the bean-property role constants the source itself uses. What it may
still refuse is a provider that provides nothing: quarkus-security-jpa
generates its IdentityProvider FROM an @UserDefinition entity, so the extension
without the entity is the same 403-on-everything with an extra dependency.

The decisions here are about the SHAPE of the tree, never about a specimen:
every case is repeated under renamed packages and types and must decide
identically.
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


def user_entity(pkg: str, name: str) -> str:
    """The entity quarkus-security-jpa generates its identity provider from."""
    return ("package %s;\n\n"
            "import io.quarkus.security.jpa.Password;\n"
            "import io.quarkus.security.jpa.Roles;\n"
            "import io.quarkus.security.jpa.UserDefinition;\n"
            "import io.quarkus.security.jpa.Username;\n\n"
            "@UserDefinition\npublic class %s {\n"
            "    @Username\n    private String login;\n"
            "    @Password\n    private String secret;\n"
            "    @Roles\n    private String grants;\n}\n" % (pkg, name))


def security_type(pkg: str, name: str, body: str) -> str:
    return ("package %s;\n\npublic class %s {\n%s}\n" % (pkg, name, body))


def role_holder(pkg: str, name: str, *, static: bool, members=("OWNER_ADMIN", "VET_ADMIN")) -> str:
    modifier = "public static final String" if static else "public final String"
    fields = "".join("    %s %s = \"ROLE_%s\";\n" % (modifier, m, m) for m in members)
    return "package %s;\n\npublic class %s {\n%s}\n" % (pkg, name, fields)


# The source's own shape: role expressions that reference a bean property, over
# a holder whose members are INSTANCE fields because that is what a
# `@roles.OWNER_ADMIN` bean-property lookup resolves against.
BEAN_ROLE_TREE = {
    "org/acme/api/OwnerResource.java": resource(
        "org.acme.api", "OwnerResource",
        "    @PreAuthorize(\"@mode.disabled() or hasRole(@roles.OWNER_ADMIN)\")\n"),
    "org/acme/api/VetResource.java": resource(
        "org.acme.api", "VetResource",
        "    @PreAuthorize(\"hasAnyRole(@roles.OWNER_ADMIN, @roles.VET_ADMIN)\")\n"),
    "org/acme/security/Roles.java": role_holder("org.acme.security", "Roles", static=False),
    "org/acme/security/SecurityMode.java": security_type(
        "org.acme.security", "SecurityMode",
        "    public boolean disabled() { return true; }\n"),
    "org/acme/model/AppUser.java": user_entity("org.acme.model", "AppUser"),
}
# The same tree with the constants holder gone: every expression now names a
# member nothing declares.
BEAN_ROLE_TREE_NO_HOLDER = {k: v for k, v in BEAN_ROLE_TREE.items() if "Roles.java" not in k}
# The same decisions, every name changed and the constants made static.
RENAMED_BEAN_ROLE_TREE = {
    "com/example/web/BookEndpoint.java": resource(
        "com.example.web", "BookEndpoint",
        "    @PreAuthorize(\"hasRole(@grants.LIBRARIAN)\")\n"),
    "com/example/auth/Grants.java": role_holder("com.example.auth", "Grants", static=True,
                                                members=("LIBRARIAN",)),
    "com/example/auth/AuthenticationSetup.java": security_type(
        "com.example.auth", "AuthenticationSetup",
        "    public void install() { }\n"),
    "com/example/auth/Account.java": user_entity("com.example.auth", "Account"),
}
ENABLED_PROPS = "example.security.enable=true\n"


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
        # an identity provider is what makes the annotations answerable -- and
        # quarkus-security-jpa is a provider only once an entity is mapped for
        # it to generate from (ADR-014)
        ("annotations + quarkus-security-jpa, no entity", 1,
         ("@UserDefinition", "quarkus-security-jpa", "403"),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa")}),
        ("annotations + quarkus-security-jpa + @UserDefinition entity", 0, ("idle",),
         {"java": dict(ANNOTATED, **{"org/acme/model/AppUser.java": user_entity("org.acme.model", "AppUser")}),
          "artifacts": ("quarkus-spring-security", "quarkus-security-jpa")}),
        ("annotations + quarkus-oidc", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-security", "quarkus-oidc")}),
        # a configured identity counts as one, profile prefix included
        ("annotations + configured users", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-security",),
          "props": "%prod.quarkus.security.users.embedded.enabled=true\n"}),
        ("annotations + http auth policy", 0, (),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security",),
          "props": "quarkus.http.auth.basic=true\n"}),
        # ... but the value is part of the question: a key that turns a
        # mechanism OFF configures no identity (ADR-014).
        ("annotations + http auth mechanism switched off", 1, ("no identity provider", "403"),
         {"java": ANNOTATED, "artifacts": ("quarkus-spring-security",),
          "props": "quarkus.http.auth.basic=false\n"}),
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

        # --- ADR-014: which provider, and which shape of role constant ---
        # Security enabled, security types present, the JPA provider mapped over
        # an entity: this passes. It used to BLOCK, because the gate demanded
        # quarkus-elytron-security-jdbc by name whatever the design decided.
        ("enabled + JPA provider over a mapped entity", 0, ("role expression",),
         {"java": BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": ENABLED_PROPS}),
        # ... and the message may not name one provider as the only one.
        ("enabled + JPA provider: no JDBC-only wording", 0, (),
         {"java": BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": ENABLED_PROPS}),
        # Instance role constants pass: `@roles.OWNER_ADMIN` is a bean-property
        # lookup, and demanding `static final` refused the source's own shape.
        ("enabled + instance role constants", 0, ("2 role expression",),
         {"java": BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": ENABLED_PROPS}),
        # What is still refused: an expression naming a constant nothing declares.
        ("role expression with no constant behind it", 1, ("OWNER_ADMIN", "resolves to nothing"),
         {"java": BEAN_ROLE_TREE_NO_HOLDER,
          "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"), "props": ENABLED_PROPS}),
        # Security enabled with annotated endpoints and nothing to authenticate
        # against: still the ADR-014 BLOCK.
        ("enabled + annotated endpoints + no provider", 1, ("no identity provider", "403"),
         {"java": {k: v for k, v in BEAN_ROLE_TREE.items() if "AppUser" not in k},
          "artifacts": ("quarkus-spring-security",), "props": ENABLED_PROPS}),
        # Security enabled through a security type, no annotated endpoint to
        # trip the first rule: the second rule BLOCKs and names every way the
        # tree could carry an identity, the JPA entity included.
        ("enabled security type + no provider at all", 1,
         ("security enabled with no identity provider", "@UserDefinition"),
         {"java": {"org/acme/security/SecurityMode.java": security_type(
             "org.acme.security", "SecurityMode", "    public boolean disabled() { return true; }\n")},
          "artifacts": ("quarkus-spring-security",), "props": ENABLED_PROPS}),
        # The same decisions under every name changed, constants made static.
        ("renamed specimen: enabled + JPA provider + static constants", 0, ("role expression",),
         {"java": RENAMED_BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": "library.security.enable=true\n"}),
        ("renamed specimen: provider extension without its entity", 1, ("@UserDefinition",),
         {"java": {k: v for k, v in RENAMED_BEAN_ROLE_TREE.items() if "Account" not in k},
          "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": "library.security.enable=true\n"}),
    ]
    forbidden = (
        # The gate may no longer demand one named provider, nor one shape of
        # role constant. Both were refusals of a decision that was not the
        # gate's to make (ADR-014).
        ("security enabled without quarkus-elytron-security-jdbc",
         {"java": BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": ENABLED_PROPS}),
        ("lacks static final role constants",
         {"java": BEAN_ROLE_TREE, "artifacts": ("quarkus-spring-security", "quarkus-security-jpa"),
          "props": ENABLED_PROPS}),
    )
    for label, rc, needles, kw in checks:
        if case(label, rc, needles, **kw):
            return 1
    for wording, kw in forbidden:
        with tempfile.TemporaryDirectory(prefix="empty-security-") as td:
            proc = run(build(Path(td), **kw))
            if wording in proc.stdout + proc.stderr:
                return _fail("the gate still says %r; that demand is not the gate's to make" % wording)
    print("OK: check-empty-security (method security with no identity provider BLOCKs and names the annotations, "
          "the missing provider and the 403; an extension or a configured identity passes; quarkus-security-jpa "
          "counts only with the @UserDefinition entity it generates from; no provider is demanded by name and no "
          "role constant by modifier; a role expression whose constant nothing declares BLOCKs; no annotations "
          "stays idle; artifactIds are matched whole; comments are not rules; renamed packages decide the same)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
