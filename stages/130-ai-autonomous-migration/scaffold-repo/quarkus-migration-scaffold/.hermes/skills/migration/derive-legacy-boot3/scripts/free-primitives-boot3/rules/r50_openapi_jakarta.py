"""Enable OpenAPI Generator Jakarta EE mode when the plugin is present."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, record_rule, repo_root  # noqa: E402

RULE_ID = "openapi-jakarta-ee"
CITE = (
    "https://openapi-generator.tech/docs/generators/spring/ "
    "(configOptions.useJakartaEe — generator 6+ emits jakarta.* models)"
)
TARGET_PLUGIN = "6.6.0"


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        return 0
    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    if "openapi-generator-maven-plugin" not in text:
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="precondition false — no openapi-generator plugin",
        )
        print(f"[{RULE_ID}] skip")
        return 0

    original = text
    text = re.sub(
        r"(<openapi-generator-maven-plugin\.version>\s*)[^<]+(\s*</openapi-generator-maven-plugin\.version>)",
        rf"\g<1>{TARGET_PLUGIN}\g<2>",
        text,
    )
    text = re.sub(
        r"(<artifactId>\s*openapi-generator-maven-plugin\s*</artifactId>\s*"
        r"(?:<!--.*?-->\s*)*<version>\s*)[^<]+(\s*</version>)",
        rf"\g<1>{TARGET_PLUGIN}\g<2>",
        text,
        flags=re.S,
    )

    # Drop mistaken top-level <useJakartaEe> (not a plugin parameter)
    text = re.sub(
        r"\n\s*<useJakartaEe>\s*true\s*</useJakartaEe>\s*\n",
        "\n",
        text,
    )

    if "useJakartaEe" not in text:
        if "<configOptions>" in text:
            text = text.replace(
                "<configOptions>",
                "<configOptions>\n"
                "                                <useJakartaEe>true</useJakartaEe>",
                1,
            )
        else:
            # Insert configOptions inside the generate <configuration>
            text = re.sub(
                r"(<artifactId>\s*openapi-generator-maven-plugin\s*</artifactId>.*?"
                r"<configuration>)",
                r"\1\n"
                r"                            <configOptions>\n"
                r"                                <useJakartaEe>true</useJakartaEe>\n"
                r"                            </configOptions>",
                text,
                count=1,
                flags=re.S,
            )

    # Generator 6 emits Schema.requiredMode — needs swagger-annotations ≥ 2.2
    swagger_dep = """        <dependency>
            <groupId>io.swagger.core.v3</groupId>
            <artifactId>swagger-annotations</artifactId>
            <version>2.2.20</version>
        </dependency>
"""
    if "io.swagger.core.v3" not in text and "swagger-annotations" not in text:
        if "</dependencies>" in text:
            text = text.replace("</dependencies>", swagger_dep + "    </dependencies>", 1)

    files: list[str] = []
    if text != original:
        pom.write_text(text, encoding="utf-8")
        files = ["pom.xml"]
    post = file_digest(pom)
    record_rule(
        rule_id=RULE_ID,
        cite=CITE,
        files=files,
        pre_digest=pre,
        post_digest=post,
        skipped=not files,
        notes=f"plugin→{TARGET_PLUGIN}; configOptions.useJakartaEe; swagger-annotations 2.2.20",
    )
    print(f"[{RULE_ID}] {'done' if files else 'skip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
