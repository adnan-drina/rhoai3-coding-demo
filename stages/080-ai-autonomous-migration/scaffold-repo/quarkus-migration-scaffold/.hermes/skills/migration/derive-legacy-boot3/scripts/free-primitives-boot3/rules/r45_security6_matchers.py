"""Migrate Security 6 request-matcher APIs on FilterChain-already apps.

Architect E-20260808T184742Z gap 2: WSCA rule skips when adapter already gone;
`antMatchers` / `authorizeRequests` / `ignoringAntMatchers` still break Sec 6.

behavioral=Y — G-4 security-off + security-on required before DEMONSTRATED.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, iter_files, record_rule, repo_root  # noqa: E402

RULE_ID = "security6-matchers"
CITE = (
    "https://docs.spring.io/spring-security/reference/migration/servlet/config.html "
    "(authorizeHttpRequests / requestMatchers; Spring Security 6)"
)

MARKERS = (
    "authorizeRequests(",
    ".antMatchers(",
    ".mvcMatchers(",
    ".antMatcher(",
    "ignoringAntMatchers(",
)


def _transform(text: str) -> str | None:
    if not any(m in text for m in MARKERS):
        return None
    new = text
    new = new.replace(".authorizeRequests()", ".authorizeHttpRequests()")
    new = new.replace(".authorizeRequests(", ".authorizeHttpRequests(")
    new = new.replace(".ignoringAntMatchers(", ".ignoringRequestMatchers(")
    new = new.replace(".antMatchers(", ".requestMatchers(")
    new = new.replace(".mvcMatchers(", ".requestMatchers(")
    # Singular antMatcher on HttpSecurity (rare)
    new = new.replace(".antMatcher(", ".securityMatcher(")
    if new == text:
        return None
    return new


def main() -> int:
    root = repo_root()
    changed: list[str] = []
    digests_pre: list[str] = []
    digests_post: list[str] = []
    for path in iter_files(root, (".java",)):
        original = path.read_text(encoding="utf-8", errors="replace")
        if not any(m in original for m in MARKERS):
            continue
        digests_pre.append(file_digest(path))
        new = _transform(original)
        if new is None:
            continue
        path.write_text(new, encoding="utf-8")
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
        notes="behavioral=Y — validate with G-4 security-off and security-on",
    )
    print(f"[{RULE_ID}] {'done' if changed else 'skip'} files={len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
