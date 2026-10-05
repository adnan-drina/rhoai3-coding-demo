"""Bump Boot to 3.0.13 / Java 17 via starter-parent and/or property + BOM import.

Architect E-20260808T184742Z gap 1: property-managed apps (no starter-parent)
need spring-boot.version bump **and** spring-boot-dependencies BOM import
ahead of aggregator BOMs — property-only leaves classpath on Boot 2.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, record_rule, repo_root  # noqa: E402

RULE_ID = "bump-boot-parent"
CITE = (
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(Java 17+ / Spring Boot 3.0 system requirements + dependency management)"
)
TARGET_BOOT = "3.0.13"
TARGET_JAVA = "17"

BOOT_BOM = """            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-dependencies</artifactId>
                <version>${spring-boot.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
"""


def _major(ver: str) -> int:
    try:
        return int(ver.strip().split(".")[0])
    except ValueError:
        return 0


def _bump_java(text: str) -> str:
    jm = re.search(r"<java\.version>\s*([^<]+)\s*</java\.version>", text)
    if jm:
        if _major(jm.group(1)) < int(TARGET_JAVA):
            return text[: jm.start(1)] + TARGET_JAVA + text[jm.end(1) :]
        return text
    prop = f"        <java.version>{TARGET_JAVA}</java.version>\n"
    if "<properties>" in text:
        return text.replace("<properties>", "<properties>\n" + prop, 1)
    return text.replace(
        "</project>",
        f"    <properties>\n{prop}    </properties>\n</project>",
        1,
    )


def _ensure_boot_version_property(text: str) -> str:
    pm = re.search(
        r"(<spring-boot\.version>\s*)([^<]+)(\s*</spring-boot\.version>)", text
    )
    if pm:
        if _major(pm.group(2)) < 3:
            return text[: pm.start(2)] + TARGET_BOOT + text[pm.end(2) :]
        return text
    # Insert property when we will add a BOM import and none exists.
    prop = f"        <spring-boot.version>{TARGET_BOOT}</spring-boot.version>\n"
    if "<properties>" in text:
        return text.replace("<properties>", "<properties>\n" + prop, 1)
    return text


def _ensure_boot_bom_import(text: str) -> str:
    if re.search(
        r"<artifactId>\s*spring-boot-dependencies\s*</artifactId>", text
    ):
        return text
    # Insert before the first dependencyManagement import BOM.
    m = re.search(
        r"(<dependencyManagement>\s*<dependencies>\s*)",
        text,
        re.S,
    )
    if not m:
        # Create dependencyManagement before <dependencies> or before </project>
        block = (
            "    <dependencyManagement>\n"
            "        <dependencies>\n"
            f"{BOOT_BOM}"
            "        </dependencies>\n"
            "    </dependencyManagement>\n\n"
        )
        deps = re.search(r"\n    <dependencies>", text)
        if deps:
            return text[: deps.start()] + "\n" + block + text[deps.start() + 1 :]
        return text.replace("</project>", block + "</project>", 1)
    return text[: m.end()] + BOOT_BOM + text[m.end() :]


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        print(f"[{RULE_ID}] error: no pom.xml", file=sys.stderr)
        return 1
    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    original = text
    notes: list[str] = []

    # Path A — spring-boot-starter-parent
    m = re.search(
        r"(<artifactId>\s*spring-boot-starter-parent\s*</artifactId>"
        r"(?:\s|<!--.*?-->)*"
        r"<version>\s*)([^<]+)(\s*</version>)",
        text,
        re.S,
    )
    has_parent = m is not None
    if has_parent:
        cur = m.group(2).strip()
        if _major(cur) < 3:
            text = text[: m.start(2)] + TARGET_BOOT + text[m.end(2) :]
            notes.append(f"parent {cur}→{TARGET_BOOT}")
        else:
            notes.append(f"parent already {cur}")

    # Path B — existing spring-boot.version property (never invent one).
    has_prop = bool(
        re.search(r"<spring-boot\.version>\s*[^<]+\s*</spring-boot\.version>", text)
    )
    if not has_parent and not has_prop:
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="no spring-boot-starter-parent and no spring-boot.version",
        )
        print(f"[{RULE_ID}] skip — no Boot parent/property")
        return 0

    if has_prop:
        before = text
        text = _ensure_boot_version_property(text)
        if text != before:
            notes.append(f"spring-boot.version→{TARGET_BOOT}")
        # Without starter-parent, property-only leaves aggregator BOM on Boot 2
        # (measured on jhipster-sample-app). Import Boot BOM first.
        if not has_parent:
            before = text
            text = _ensure_boot_bom_import(text)
            if text != before:
                notes.append("import spring-boot-dependencies BOM")

    before = text
    text = _bump_java(text)
    if text != before:
        notes.append(f"java.version≥{TARGET_JAVA}")

    files: list[str] = []
    if text != original:
        pom.write_text(text, encoding="utf-8")
        files.append("pom.xml")
    post = file_digest(pom)
    record_rule(
        rule_id=RULE_ID,
        cite=CITE,
        files=files,
        pre_digest=pre,
        post_digest=post,
        skipped=not files,
        notes="; ".join(notes) if notes else "already satisfied",
    )
    print(f"[{RULE_ID}] {'done' if files else 'skip'} {'; '.join(notes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
