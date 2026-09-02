"""Rewrite Thymeleaf Spring 5 integration package to Spring 6.

Architect E-20260808T184742Z gap 3: Boot 3 ships thymeleaf-spring6.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, iter_files, record_rule, repo_root  # noqa: E402

RULE_ID = "thymeleaf-spring6"
CITE = (
    "https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide "
    "(Thymeleaf spring5 → spring6 package)"
)
OLD = "org.thymeleaf.spring5"
NEW = "org.thymeleaf.spring6"


def main() -> int:
    root = repo_root()
    changed: list[str] = []
    digests_pre: list[str] = []
    digests_post: list[str] = []
    for path in iter_files(root, (".java",)):
        original = path.read_text(encoding="utf-8", errors="replace")
        if OLD not in original:
            continue
        digests_pre.append(file_digest(path))
        path.write_text(original.replace(OLD, NEW), encoding="utf-8")
        changed.append(str(path.relative_to(root)))
        digests_post.append(file_digest(path))

    pre = "|".join(digests_pre) if digests_pre else "none"
    post = "|".join(digests_post) if digests_post else pre
    record_rule(
        rule_id=RULE_ID,
        cite=CITE,
        files=changed,
        pre_digest=pre,
        post_digest=post,
        skipped=not changed,
        notes="package rewrite only",
    )
    print(f"[{RULE_ID}] {'done' if changed else 'skip'} files={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
