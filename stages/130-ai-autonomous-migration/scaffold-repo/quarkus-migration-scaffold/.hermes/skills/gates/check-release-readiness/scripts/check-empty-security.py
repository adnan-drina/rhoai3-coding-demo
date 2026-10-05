#!/usr/bin/env python3
"""AD-H §16.6 / AR-2.2 — refuse empty/placeholder security as completion.

Scans `<root>/src/main/java` for `*Security*.java` / `*Authentication*.java`
types plus `<root>/src/main/resources/application*.properties` and
`<root>/pom.xml`. Idle when no security types exist and security is not
enabled.

Usage:
  python3 check-empty-security.py .
  python3 check-empty-security.py /projects/modernized
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EXIT_CODES = """Exit codes:
  0  pass — functional security surface present, or gate idle (no security
     types, no method-security annotations, and security not enabled)
  1  BLOCK — method security with no identity provider, security enabled
     with no identity provider and no security extension, no security types
     while security is enabled, a role expression that resolves to nothing,
     or empty / placeholder / javadoc-only security classes
     (AR-2.2, R-M3.39, ADR-014)
  2  usage / harness defect (bad or unknown argument)
"""

# Method security: the annotations that make an endpoint refuse an
# unauthenticated caller. They are matched as annotations by simple name, so
# the rule holds whatever the package, the type or the specimen is called.
METHOD_SECURITY = ("PreAuthorize", "RolesAllowed", "Secured", "DenyAll")
METHOD_SECURITY_RE = re.compile(r"@(%s)\b" % "|".join(METHOD_SECURITY))

# The extensions that turn method security ON ...
SECURITY_EXTENSIONS = ("quarkus-spring-security", "quarkus-security")
# ... and the ones that give it somebody to authenticate AGAINST. Without one
# of these there is no IdentityProvider, so every annotated member denies an
# anonymous caller: the augmentation succeeds, the application starts, and
# every call answers 403. Measured on destination v9 (2026-09-15): 403 on
# every read while this gate passed as idle, because the annotations live on
# controllers and the gate only ever looked at *Security*.java.
IDENTITY_PROVIDERS = (
    "quarkus-security-jpa",
    "quarkus-security-jdbc",
    "quarkus-elytron-security-properties-file",
    "quarkus-elytron-security-jdbc",
    "quarkus-oidc",
    "quarkus-elytron-security-ldap",
)
# Every extension above brings the security runtime with it, so any one of them
# is enough to make the method-security annotations mean something.
SECURITY_RUNTIME = set(SECURITY_EXTENSIONS) | set(IDENTITY_PROVIDERS)
# A configured identity is a provider too: embedded users, or an HTTP auth
# policy/mechanism the application declares for itself. The VALUE is part of the
# question: `quarkus.http.auth.basic=false` turns a mechanism OFF, and reading
# it as a configured identity would pass a tree that has none (ADR-014, where
# the destination sets exactly that key to false and registers its mechanism at
# runtime instead).
IDENTITY_PROPERTY_RE = re.compile(
    r"(?m)^\s*(?:%[\w.-]+\.)?quarkus\.(?:security\.users|http\.auth)\.[\w.\"-]*\s*=\s*(?!false\s*$)(\S.*)$"
)

# quarkus-security-jpa is the one provider in the tuple that provides nothing on
# its own: it generates an IdentityProvider from an ENTITY, and with no entity
# mapped it contributes no identity at all -- the same 403-on-everything the
# rule below exists to catch. Presence of the extension is therefore not the
# question; the mapped entity is. The entity mapping is matched by annotation
# simple name, so it holds whatever the entity, its package or the specimen is
# called.
JPA_IDENTITY_EXTENSION = "quarkus-security-jpa"
JPA_USER_DEFINITION_RE = re.compile(r"@UserDefinition\b")
JPA_USERNAME_RE = re.compile(r"@Username\b")
JPA_PASSWORD_RE = re.compile(r"@Password\b")

# Role expressions. These are what an annotated member actually decides with,
# and they take two shapes the destination must preserve:
#   a call over role names     @PreAuthorize("hasRole('X')"), hasAnyRole, ...
#   a reference to a constant  @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
# The second shape is a BEAN PROPERTY reference, resolved by bean name and
# member name at runtime; the member's modifiers are not part of that
# resolution, so nothing here may demand `static final`. What it may demand is
# that the member exists: an expression naming a constant no type declares is a
# role expression that has been silently emptied.
ROLE_CALL_RE = re.compile(r"\b(hasRole|hasAnyRole|hasAuthority|hasAnyAuthority)\s*\(")
# `(?![\w$])` pins the member name to its full extent before the second
# lookahead: without it `@mode.disabled()` backtracks to `disable` and
# reads a method call as a constant reference.
BEAN_MEMBER_RE = re.compile(r"@(\w+)\.([A-Za-z_$][\w$]*)(?![\w$])(?!\s*\()")
QUOTED_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"//.*?$", re.M)


def strip_comments(text: str) -> str:
    """A javadoc mentioning an annotation is documentation, not an access rule."""
    return _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", text))


def artifact_ids(pom: str) -> set[str]:
    """Every <artifactId> the pom names, matched whole.

    Substring matching cannot answer this question: "quarkus-security" is a
    substring of "quarkus-security-jpa", so a tree whose only security
    dependency IS the identity provider would read as if it had the umbrella
    extension and no provider."""
    return {m.strip() for m in re.findall(r"<artifactId>([^<]+)</artifactId>", pom)}


def java_sources(src: Path) -> list[tuple[Path, str]]:
    """Every java source under the tree, comments already stripped."""
    if not src.is_dir():
        return []
    return [
        (path, strip_comments(path.read_text(encoding="utf-8", errors="replace")))
        for path in sorted(src.rglob("*.java"))
    ]


def method_security_sites(sources: list[tuple[Path, str]]) -> dict[str, list[str]]:
    """{annotation: [file, ...]} for every method-security annotation in the
    tree."""
    found: dict[str, list[str]] = {}
    for path, text in sources:
        for name in sorted(set(METHOD_SECURITY_RE.findall(text))):
            found.setdefault(name, []).append(path.as_posix())
    return found


def jpa_identity_entity(sources: list[tuple[Path, str]]) -> Path | None:
    """The entity quarkus-security-jpa generates its provider from, if the tree
    maps one: a type carrying the user definition plus the two members the
    generated provider reads."""
    for path, text in sources:
        if (JPA_USER_DEFINITION_RE.search(text)
                and JPA_USERNAME_RE.search(text)
                and JPA_PASSWORD_RE.search(text)):
            return path
    return None


def identity_provider(artifacts: set[str], props_blob: str,
                      sources: list[tuple[Path, str]]) -> str | None:
    """What this tree can authenticate against, named, or None.

    An extension in the tuple, an identity configured in properties, or -- for
    the JPA provider, which generates itself from an entity -- the mapped
    entity. The provider is what makes an annotated member answerable; without
    one every annotated member denies an anonymous caller."""
    for extension in sorted(artifacts & set(IDENTITY_PROVIDERS)):
        if extension != JPA_IDENTITY_EXTENSION:
            return extension
    if JPA_IDENTITY_EXTENSION in artifacts:
        entity = jpa_identity_entity(sources)
        if entity is not None:
            return "%s over the @UserDefinition entity %s" % (JPA_IDENTITY_EXTENSION, entity.name)
    configured = IDENTITY_PROPERTY_RE.search(props_blob)
    if configured is not None:
        return "a configured identity (%s)" % configured.group(0).strip()
    return None


def annotation_payloads(text: str) -> list[str]:
    """The argument text of every method-security annotation in one source."""
    payloads: list[str] = []
    for match in METHOD_SECURITY_RE.finditer(text):
        cursor = match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "(":
            continue  # a bare @DenyAll / @PreAuthorize carries no expression
        depth = 0
        for end in range(cursor, len(text)):
            if text[end] == "(":
                depth += 1
            elif text[end] == ")":
                depth -= 1
                if depth == 0:
                    payloads.append(text[cursor + 1:end])
                    break
    return payloads


def role_expressions(sources: list[tuple[Path, str]]) -> tuple[int, dict[str, list[str]]]:
    """(how many role expressions the tree carries, {member: [file, ...]} for
    every bean-property role constant they reference)."""
    count = 0
    references: dict[str, list[str]] = {}
    for path, text in sources:
        for payload in annotation_payloads(text):
            members = BEAN_MEMBER_RE.findall(payload)
            literal = [g for pair in QUOTED_RE.findall(payload) for g in pair if g]
            if ROLE_CALL_RE.search(payload) or members or literal:
                count += 1
            for _bean, member in members:
                references.setdefault(member, []).append(path.as_posix())
    return count, references


def declares(sources: list[tuple[Path, str]], member: str) -> bool:
    """Whether some type in the tree declares a member of that name, with any
    modifiers. A `@roles.OWNER_ADMIN` reference is resolved by name at runtime,
    and a Spring bean-property reference needs an INSTANCE member, so demanding
    `static final` here would refuse the very shape the source uses."""
    declaration = re.compile(r"\b%s\b\s*(?:=|;)" % re.escape(member))
    return any(declaration.search(text) for _path, text in sources)

PLACEHOLDER_MARKERS = (
    "structural placeholder",
    "this bean is inert",
    "exists solely as a documentation anchor",
    "until then this bean is inert",
    # R-M3.39 / v11 S-005 javadoc-only shells (Review E-20260811T054056Z)
    "security configuration is declarative",
    "no java-based filter chain",
    "no java class needed to express",
    "security is disabled by default in quarkus",
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EXIT_CODES,
    )
    ap.add_argument(
        "root",
        nargs="?",
        default=".",
        help="product root containing src/ and pom.xml (default: .)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    sec = root / "src/main/java"
    props_blob = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((root / "src/main/resources").glob("application*.properties"))
        if p.is_file()
    )
    pom = (root / "pom.xml").read_text(encoding="utf-8") if (root / "pom.xml").is_file() else ""

    java_files: list[Path] = []
    if sec.is_dir():
        java_files = list(sec.rglob("*Security*.java")) + list(
            sec.rglob("*Authentication*.java")
        )

    # Method security without an identity provider. This is checked BEFORE the
    # idle rule: the annotations live on the resources, not on a *Security*
    # type, so a tree that denies every anonymous caller used to reach the idle
    # return and pass. An annotated endpoint is a security surface whether or
    # not anything in the tree is named after security.
    sources = java_sources(sec)
    sites = method_security_sites(sources)
    artifacts = artifact_ids(pom)
    provider = identity_provider(artifacts, props_blob, sources)
    if sites and (artifacts & SECURITY_RUNTIME) and provider is None:
        named = ", ".join(
            "@%s (%d site%s, e.g. %s)"
            % (a, len(f), "" if len(f) == 1 else "s", Path(f[0]).relative_to(root).as_posix())
            for a, f in sorted(sites.items())
        )
        jpa_without_entity = (
            " The pom does carry %s, but no type in the tree carries @UserDefinition with @Username and "
            "@Password, and that extension generates its provider FROM the entity: with none mapped it "
            "contributes no identity at all." % JPA_IDENTITY_EXTENSION
            if JPA_IDENTITY_EXTENSION in artifacts else ""
        )
        print(
            "FAIL: AR-2.2 method security with no identity provider: %s; the pom has %s, but nothing in the tree "
            "gives those annotations an identity to check -- none of %s is usable here, and no "
            "quarkus.security.users.* / quarkus.http.auth.* key configures one.%s With nothing to "
            "authenticate against there is no IdentityProvider, so every annotated endpoint denies an anonymous "
            "caller: the application starts and answers 403 on every call. Add the identity provider the decided "
            "design calls for, or remove the annotations the design does not."
            % (named, ", ".join(sorted(artifacts & SECURITY_RUNTIME)), ", ".join(IDENTITY_PROVIDERS),
               jpa_without_entity),
            file=sys.stderr,
        )
        print("AR-2.2 empty-security checks FAILED", file=sys.stderr)
        return 1

    # POM-only security deps (foundation / S-001 handoff) are NOT "enabled".
    # Enabled requires properties or security Java types; else gate stays idle
    # so later stories can land config/types without false-failing compile-only cards.
    security_enabled = bool(
        # R-SK.5: match any <app>.security.enable=true, not one specimen's
        # property name. A legacy app names this after itself; hardcoding
        # one made the gate blind to every other codebase.
        re.search(r"(?m)^[\w.-]+\.security\.enable\s*=\s*true\s*$", props_blob)
        or re.search(r"(?m)^quarkus\.security\.jdbc\.enabled\s*=\s*true\s*$", props_blob)
        or (
            "quarkus-elytron-security-jdbc" in pom
            and (
                bool(re.search(r"(?m)^quarkus\.security\.", props_blob))
                or bool(java_files)
            )
        )
        or bool(java_files)
    )

    if not java_files and not security_enabled:
        print("OK: AR-2.2 idle (no security types / security not enabled)")
        return 0

    bad = 0
    # Which extension brings the security runtime is the design's decision, not
    # this gate's: every member of SECURITY_RUNTIME depends on quarkus-security,
    # and artifactIds are matched whole so the umbrella is not read out of a
    # provider's name.
    if not (artifacts & SECURITY_RUNTIME):
        print(
            "FAIL: AR-2.2 pom declares no security extension (one of %s)"
            % ", ".join(sorted(SECURITY_RUNTIME)),
            file=sys.stderr,
        )
        bad = 1
    # An identity provider, whichever one the design decided. Naming a single
    # extension here was a defect: it refused every other provider the tuple
    # above already lists, and ADR-014 decided the JPA one.
    if security_enabled and provider is None:
        print(
            "FAIL: AR-2.2 security enabled with no identity provider: none of %s is declared, no "
            "quarkus.security.users.* / quarkus.http.auth.* key configures an identity, and no type carries "
            "@UserDefinition with @Username and @Password for %s to generate one from"
            % (", ".join(IDENTITY_PROVIDERS), JPA_IDENTITY_EXTENSION),
            file=sys.stderr,
        )
        bad = 1

    if not java_files and security_enabled:
        print(
            "FAIL: AR-2.2 security enabled but no *Security*/*Authentication* types",
            file=sys.stderr,
        )
        bad = 1

    for path in java_files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root)
        low = text.lower()
        if any(m in low for m in PLACEHOLDER_MARKERS):
            print(f"FAIL: AR-2.2 placeholder security class {rel}", file=sys.stderr)
            bad = 1
            continue
        if re.search(r"class\s+\w+[^{]*\{\s*\}", text, re.S):
            print(f"FAIL: AR-2.2 empty security class {rel}", file=sys.stderr)
            bad = 1
            continue
        # Brace body with only comments/whitespace → javadoc-only shell (R-M3.39)
        m = re.search(r"class\s+\w+[^{]*\{(.*)\}\s*\Z", text, re.S)
        if m is not None:
            body = m.group(1)
            stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
            stripped = re.sub(r"//.*?$", "", stripped, flags=re.M)
            if stripped.strip() == "":
                print(f"FAIL: AR-2.2 javadoc-only security class {rel}", file=sys.stderr)
                bad = 1

    # AR-3.1: the role expressions must still resolve to something. A
    # `@roles.OWNER_ADMIN` reference is a bean-property lookup by name, so the
    # member's modifiers are not the question -- its existence is. An expression
    # naming a constant no type declares is an expression that has been emptied.
    expressions, references = role_expressions(sources)
    for member, users in sorted(references.items()):
        if not declares(sources, member):
            print(
                "FAIL: AR-2.2/AR-3.1 role expression references .%s (e.g. %s) but no type in the tree declares "
                "%s; the expression resolves to nothing at runtime"
                % (member, Path(users[0]).relative_to(root).as_posix(), member),
                file=sys.stderr,
            )
            bad = 1

    if bad:
        print("AR-2.2 empty-security checks FAILED", file=sys.stderr)
        return 1
    print(
        "OK: AR-2.2 security surface (%d class(es), %d role expression(s)%s)"
        % (len(java_files), expressions, ", provider: %s" % provider if provider else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
