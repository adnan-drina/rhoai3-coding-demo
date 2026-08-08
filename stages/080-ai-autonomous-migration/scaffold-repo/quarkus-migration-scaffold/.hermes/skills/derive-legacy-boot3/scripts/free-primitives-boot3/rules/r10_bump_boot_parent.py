"""Bump spring-boot-starter-parent to 3.0.13 and ensure java.version ≥ 17."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, record_rule, repo_root  # noqa: E402

RULE_ID = "bump-boot-parent"
CITE = (
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(Java 17+ / Spring Boot 3.0 system requirements)"
)
TARGET_BOOT = "3.0.13"
TARGET_JAVA = "17"


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        print(f"[{RULE_ID}] error: no pom.xml", file=sys.stderr)
        return 1
    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    files: list[str] = []

    # Allow comments/whitespace between artifactId and version (coolstore style).
    m = re.search(
        r"(<artifactId>\s*spring-boot-starter-parent\s*</artifactId>"
        r"(?:\s|<!--.*?-->)*"
        r"<version>\s*)([^<]+)(\s*</version>)",
        text,
        re.S,
    )
    if not m:
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="no spring-boot-starter-parent",
        )
        print(f"[{RULE_ID}] skip — no starter-parent")
        return 0

    cur = m.group(2).strip()
    major = cur.split(".")[0]
    original = text
    if not (major.isdigit() and int(major) >= 3):
        text = text[: m.start(2)] + TARGET_BOOT + text[m.end(2) :]

    jm = re.search(r"<java\.version>\s*([^<]+)\s*</java\.version>", text)
    if jm:
        try:
            java_major = int(jm.group(1).strip().split(".")[0])
        except ValueError:
            java_major = 0
        if java_major < int(TARGET_JAVA):
            text = (
                text[: jm.start(1)] + TARGET_JAVA + text[jm.end(1) :]
            )
    else:
        prop = f"        <java.version>{TARGET_JAVA}</java.version>\n"
        if "<properties>" in text:
            text = text.replace("<properties>", "<properties>\n" + prop, 1)
        else:
            text = text.replace(
                "</project>",
                f"    <properties>\n{prop}    </properties>\n</project>",
                1,
            )

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
        notes=f"parent {cur} → ≥{TARGET_BOOT}; java.version ≥ {TARGET_JAVA}",
    )
    print(f"[{RULE_ID}] {'done' if files else 'skip'} was={cur}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
