"""mysql:mysql-connector-java → com.mysql:mysql-connector-j."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, record_rule, repo_root  # noqa: E402

RULE_ID = "mysql-connector-j"
CITE = (
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(MySQL Connector/J coordinate: mysql:mysql-connector-java → com.mysql:mysql-connector-j)"
)


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        return 0
    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    if "mysql-connector-java" not in text and (
        "<groupId>mysql</groupId>" not in text
        or "mysql-connector" not in text
    ):
        if "mysql-connector-java" not in text:
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
    # Dependency block: groupId mysql + artifactId mysql-connector-java
    text = re.sub(
        r"(<dependency>\s*)<groupId>\s*mysql\s*</groupId>\s*"
        r"<artifactId>\s*mysql-connector-java\s*</artifactId>"
        r"(\s*(?:<version>[^<]*</version>)?\s*(?:<scope>[^<]*</scope>)?\s*</dependency>)",
        r"\1<groupId>com.mysql</groupId>\n            "
        r"<artifactId>mysql-connector-j</artifactId>\2",
        text,
        flags=re.S,
    )
    # Property / leftover artifact mentions
    text = text.replace("mysql-connector-java", "mysql-connector-j")
    # If groupId still mysql with connector-j, fix group
    text = re.sub(
        r"(<groupId>\s*)mysql(\s*</groupId>\s*<artifactId>\s*mysql-connector-j\s*</artifactId>)",
        r"\1com.mysql\2",
        text,
    )

    files: list[str] = []
    if text != original:
        # Drop explicit version when BOM-managed (optional cleanup of property)
        text = re.sub(
            r"(<artifactId>\s*mysql-connector-j\s*</artifactId>\s*)<version>[^<]*</version>\s*",
            r"\1",
            text,
        )
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
