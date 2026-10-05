"""Ensure jakarta.xml.bind-api; remove javax.xml.bind:jaxb-api."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, iter_files, record_rule, repo_root  # noqa: E402

RULE_ID = "jaxb-api-jakarta"
CITE = (
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(Jakarta EE / JAXB no longer on the default classpath)"
)

JAKARTA_DEP = """        <dependency>
            <groupId>jakarta.xml.bind</groupId>
            <artifactId>jakarta.xml.bind-api</artifactId>
        </dependency>
"""


def _refs_jaxb(root: Path) -> bool:
    for path in iter_files(root, (".java",)):
        t = path.read_text(encoding="utf-8", errors="replace")
        if "javax.xml.bind" in t or "jakarta.xml.bind" in t:
            return True
    return False


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        return 0
    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    has_javax = bool(
        re.search(
            r"<groupId>\s*javax\.xml\.bind\s*</groupId>\s*"
            r"<artifactId>\s*jaxb-api\s*</artifactId>",
            text,
            re.S,
        )
    )
    has_jakarta = "jakarta.xml.bind-api" in text
    # Stale ${jaxb-api.version} on jakarta artifact pins an invalid 2.x coord.
    stale_ver = bool(
        re.search(
            r"<artifactId>\s*jakarta\.xml\.bind-api\s*</artifactId>\s*"
            r"<version>\s*\$\{jaxb-api\.version\}\s*</version>",
            text,
            re.S,
        )
    ) or ("jaxb-api.version" in text and has_jakarta)
    needs = has_javax or stale_ver or (_refs_jaxb(root) and not has_jakarta)
    if not needs:
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="precondition false",
        )
        print(f"[{RULE_ID}] skip")
        return 0

    original = text
    # Remove javax.xml.bind:jaxb-api dependency block
    text = re.sub(
        r"\s*<dependency>\s*<groupId>\s*javax\.xml\.bind\s*</groupId>\s*"
        r"<artifactId>\s*jaxb-api\s*</artifactId>"
        r"(?:\s*<version>[^<]*</version>)?\s*</dependency>\s*",
        "\n",
        text,
        flags=re.S,
    )
    # Drop version pin on jakarta.xml.bind-api — Boot BOM manages it
    text = re.sub(
        r"(<artifactId>\s*jakarta\.xml\.bind-api\s*</artifactId>\s*)"
        r"<version>[^<]*</version>\s*",
        r"\1",
        text,
    )
    # Drop obsolete property if present
    text = re.sub(
        r"\s*<jaxb-api\.version>[^<]*</jaxb-api\.version>\s*",
        "\n",
        text,
    )
    if "jakarta.xml.bind-api" not in text:
        if "</dependencies>" in text:
            text = text.replace("</dependencies>", JAKARTA_DEP + "    </dependencies>", 1)
        else:
            text = text.replace(
                "</project>",
                f"    <dependencies>\n{JAKARTA_DEP}    </dependencies>\n</project>",
                1,
            )

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
    )
    print(f"[{RULE_ID}] {'done' if files else 'skip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
