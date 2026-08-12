"""springfox → springdoc-openapi (Boot 3 / Jakarta) — W2 §12.2 admit.

Architect E-20260808T095454Z layer B. Specimen-agnostic library transform.
behavioral?=Y — named G-4 OpenAPI path subset required before DEMONSTRATED
(compile/boot alone insufficient for OpenAPI surface parity).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, iter_files, record_rule, repo_root  # noqa: E402

RULE_ID = "springfox-to-springdoc"
CITE = (
    "https://springdoc.org/#migrating-from-springfox "
    "(remove springfox / swagger2 deps; add org.springdoc:springdoc-openapi-starter-webmvc-ui); "
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(Jakarta EE — no javax.servlet on Boot 3 classpath)"
)
SPRINGDOC_DEP = """        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.3.0</version>
        </dependency>
"""


def strip_springfox_pom(text: str) -> str:
    text = re.sub(
        r"<dependency>\s*"
        r"(?:(?!</dependency>).)*?"
        r"<artifactId>\s*[^<]*springfox[^<]*</artifactId>"
        r"(?:(?!</dependency>).)*?"
        r"</dependency>\s*",
        "",
        text,
        flags=re.S | re.I,
    )
    text = re.sub(
        r"<[^>]*springfox[^>]*>\s*[^<]*\s*</[^>]*springfox[^>]*>\s*",
        "",
        text,
        flags=re.I,
    )
    return text


def main() -> int:
    root = repo_root()
    pom = root / "pom.xml"
    if not pom.is_file():
        return 0

    pre = file_digest(pom)
    text = pom.read_text(encoding="utf-8")
    java_hits = []
    for p in iter_files(root, (".java",)):
        body = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*import\s+springfox\.", body, re.M) or "io.springfox" in body:
            java_hits.append(p)

    if "springfox" not in text.lower() and not java_hits:
        record_rule(
            rule_id=RULE_ID,
            cite=CITE,
            files=[],
            pre_digest=pre,
            post_digest=pre,
            skipped=True,
            notes="precondition false — no springfox",
        )
        print(f"[{RULE_ID}] skip")
        return 0

    original = text
    text = strip_springfox_pom(text)
    if "springdoc-openapi-starter-webmvc-ui" not in text:
        if "</dependencies>" in text:
            text = text.replace("</dependencies>", SPRINGDOC_DEP + "    </dependencies>", 1)

    files: list[str] = []
    if text != original:
        pom.write_text(text, encoding="utf-8")
        files.append("pom.xml")

    for jp in java_hits:
        rel = str(jp.relative_to(root))
        jp.unlink()
        files.append(rel)

    post = file_digest(pom)
    record_rule(
        rule_id=RULE_ID,
        cite=CITE,
        files=files,
        pre_digest=pre,
        post_digest=post,
        skipped=not files,
        notes=(
            "behavioral=Y — G-4 OpenAPI subset before DEMONSTRATED "
            "(e.g. /v3/api-docs and/or /swagger-ui.html presence after Boot 3); "
            "Docket/config classes importing springfox removed; springdoc auto-config"
        ),
    )
    print(f"[{RULE_ID}] {'done' if files else 'skip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
