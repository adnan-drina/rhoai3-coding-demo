# Pom pin lint after bootstrap

After CLI/Maven create + harness pom patch, run:

```bash
python3 ../manage-quarkus-extensions/scripts/check-pom-platform-pins.py <root>
```

Shared BOM / Jacoco policy:
`../manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md`.

Platform GAV: `governance/contracts/tooling-pins.md` (do not restate versions
here).
