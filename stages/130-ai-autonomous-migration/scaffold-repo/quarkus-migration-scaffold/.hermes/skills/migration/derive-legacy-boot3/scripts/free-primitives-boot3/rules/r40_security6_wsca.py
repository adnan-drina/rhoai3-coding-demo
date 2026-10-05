"""Replace WebSecurityConfigurerAdapter with SecurityFilterChain (Security 6).

Behavioral: Y — G-4 must validate security-off and security-on. Compile ≠ proof.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib import file_digest, iter_files, record_rule, repo_root  # noqa: E402

RULE_ID = "security6-wsca"
CITE = (
    "https://docs.spring.io/spring-security/reference/migration/index.html "
    "(WebSecurityConfigurerAdapter removed in Spring Security 6)"
)


def _ensure_import(text: str, import_line: str) -> str:
    if import_line in text:
        return text
    # After package declaration block
    m = re.search(r"(package\s+[\w.]+;\s*\n)", text)
    if m:
        return text[: m.end()] + "\n" + import_line + "\n" + text[m.end() :]
    return import_line + "\n" + text


def _transform(text: str) -> str | None:
    if "WebSecurityConfigurerAdapter" not in text:
        return None

    text = text.replace(
        "import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;\n",
        "",
    )
    text = text.replace(
        "import org.springframework.security.config.annotation.method.configuration.EnableGlobalMethodSecurity;\n",
        "import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;\n",
    )
    text = text.replace("@EnableGlobalMethodSecurity", "@EnableMethodSecurity")
    text = re.sub(
        r"(public\s+class\s+\w+)\s+extends\s+WebSecurityConfigurerAdapter\s*\{",
        r"\1 {",
        text,
    )
    text = _ensure_import(text, "import org.springframework.context.annotation.Bean;")
    text = _ensure_import(
        text, "import org.springframework.security.web.SecurityFilterChain;"
    )
    text = _ensure_import(
        text, "import org.springframework.security.config.Customizer;"
    )

    text = re.sub(
        r"@Override\s+protected\s+void\s+configure\s*\(\s*HttpSecurity\s+http\s*\)\s*throws\s+Exception\s*\{",
        "@Bean\n    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {",
        text,
    )

    # Normalize the common specimen shapes into Sec6 lambdas.
    # permitAll variant
    text = re.sub(
        r"http\s*\n\s*\.authorizeRequests\(\)\s*\n\s*\.anyRequest\(\)\.permitAll\(\)\s*\n\s*\.and\(\)\s*\n\s*\.csrf\(\)\s*\n\s*\.disable\(\)\s*;",
        "http\n            .authorizeHttpRequests(auth -> auth.anyRequest().permitAll())\n"
        "            .csrf(csrf -> csrf.disable());",
        text,
    )
    # authenticated + httpBasic variant
    text = re.sub(
        r"http\s*\n\s*\.authorizeRequests\(\)\s*\n\s*\.anyRequest\(\)\s*\n\s*\.authenticated\(\)\s*\n\s*\.and\(\)\s*\n\s*\.httpBasic\(\)\s*\n\s*\.and\(\)\s*\n\s*\.csrf\(\)\s*\n\s*\.disable\(\)\s*;",
        "http\n            .authorizeHttpRequests(auth -> auth.anyRequest().authenticated())\n"
        "            .httpBasic(Customizer.withDefaults())\n"
        "            .csrf(csrf -> csrf.disable());",
        text,
    )
    # Generic leftovers
    text = text.replace(".authorizeRequests()", ".authorizeHttpRequests(auth -> auth")
    text = re.sub(r"\.csrf\(\)\s*\n\s*\.disable\(\)", ".csrf(csrf -> csrf.disable())", text)
    text = text.replace(".csrf().disable()", ".csrf(csrf -> csrf.disable())")
    text = re.sub(
        r"\.httpBasic\(\)\s*\n\s*\.and\(\)",
        ".httpBasic(Customizer.withDefaults())",
        text,
    )

    if "filterChain(HttpSecurity" in text and "return http.build()" not in text:
        text = re.sub(
            r"(public SecurityFilterChain filterChain\(HttpSecurity http\) throws Exception \{)"
            r"(.*?)"
            r"(\n    \})",
            lambda m: m.group(1)
            + m.group(2).rstrip()
            + "\n        return http.build();\n    }",
            text,
            count=1,
            flags=re.S,
        )

    # jdbc AuthenticationManagerBuilder → JdbcUserDetailsManager
    m = re.search(
        r"@Autowired\s+public\s+void\s+configureGlobal\s*\(\s*AuthenticationManagerBuilder\s+auth\s*\)\s*throws\s+Exception\s*\{"
        r"(.*?)"
        r"\n    \}",
        text,
        flags=re.S,
    )
    if m:
        body = m.group(1)
        uq = re.search(r'\.usersByUsernameQuery\(\s*"([^"]+)"\s*\)', body)
        aq = re.search(r'\.authoritiesByUsernameQuery\(\s*"([^"]+)"\s*\)', body)
        if uq and aq:
            replacement = f'''@Bean
    public UserDetailsService userDetailsService() {{
        JdbcUserDetailsManager users = new JdbcUserDetailsManager(dataSource);
        users.setUsersByUsernameQuery("{uq.group(1)}");
        users.setAuthoritiesByUsernameQuery("{aq.group(1)}");
        return users;
    }}

    @Bean
    public PasswordEncoder passwordEncoder() {{
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
    }}'''
            text = text[: m.start()] + replacement + text[m.end() :]
            text = text.replace(
                "import org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder;\n",
                "",
            )
            text = _ensure_import(
                text,
                "import org.springframework.security.core.userdetails.UserDetailsService;",
            )
            text = _ensure_import(
                text,
                "import org.springframework.security.provisioning.JdbcUserDetailsManager;",
            )
            if "PasswordEncoder" in text and "import org.springframework.security.crypto.password.PasswordEncoder;" not in text:
                text = _ensure_import(
                    text,
                    "import org.springframework.security.crypto.password.PasswordEncoder;",
                )

    if "@Autowired" not in text:
        text = text.replace(
            "import org.springframework.beans.factory.annotation.Autowired;\n",
            "",
        )

    if "WebSecurityConfigurerAdapter" in text:
        return None
    return text


def main() -> int:
    root = repo_root()
    changed: list[str] = []
    digests_pre: list[str] = []
    digests_post: list[str] = []
    for path in iter_files(root, (".java",)):
        original = path.read_text(encoding="utf-8", errors="replace")
        if "WebSecurityConfigurerAdapter" not in original:
            continue
        digests_pre.append(file_digest(path))
        new = _transform(original)
        if new is None or new == original:
            print(f"[{RULE_ID}] warn: could not transform {path}", file=sys.stderr)
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
