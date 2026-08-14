# Pom pin + Jacoco lint after authoring

After foundation authors `pom.xml` (DD1 — no create path):

```bash
python3 ../manage-quarkus-extensions/scripts/check-pom-platform-pins.py <root>
python3 ../manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py <root>
python3 ../manage-quarkus-extensions/scripts/assert-extension-tooling.py
```

Plugin GAV must be `com.redhat.quarkus.platform:quarkus-maven-plugin`
(from pins) — never community `io.quarkus` / `io.quarkus.platform` (H-1).

Shared BOM / Jacoco policy:
`../manage-quarkus-extensions/references/rh-bom-and-mandatory-deps.md`.
Foundation fragments: `foundation-jacoco-wiring.md`.

Platform GAV: `.hermes/pins.yaml` (do not restate versions
here).
