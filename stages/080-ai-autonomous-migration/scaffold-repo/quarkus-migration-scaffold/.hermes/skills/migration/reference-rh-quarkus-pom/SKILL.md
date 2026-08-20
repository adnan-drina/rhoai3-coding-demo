---
name: reference-rh-quarkus-pom
description: Before authoring a destination Quarkus pom.xml — assemble the Red Hat platform structure (properties, BOM import, quarkus-maven-plugin executions, native profile) from official fragments with pins-only GAV; foundation Jacoco plus the pom-writer identity.extensions_apply union; use when foundation stories hand-author the POM
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; Maven
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - quarkus
    - pom
    category: migration
    kind: guidance
---
# Reference Red Hat Quarkus POM structure (T-1)

Guidance only (R-SK.14). **Structure reference**, not a shipped template file
and not a create-app path. Platform GAV values live only in
`.hermes/pins.json` — never paste pin versions into this
skill.

Consumers: skill `bootstrap-quarkus-project` (authors the destination POM);
extensions via `manage-quarkus-extensions` (T-3). Coverage wiring is carried
from `../bootstrap-quarkus-project/references/foundation-jacoco-wiring.md`
(A-3 / H-3), not invented here.

Annotated fragments: `references/pom-structure.md`. Repository resolution:
`references/maven-repos.md`.

## When to Use

- Foundation / first destination `pom.xml` authoring (DD1 create path
  retired).
- Reminding an agent of the official `<build>` execution goals or native
  Maven profile shape without regenerating from memory.
- **Not** for adding later-story extensions — those stay on
  `identity.extensions_declared`; the sole pom writer applies
  `identity.extensions_apply` via `manage-quarkus-extensions`.
- **Not** for Spring→Quarkus form mapping — `spring-to-quarkus-patterns`.
- **Not** to invoke `quarkus create app` / `quarkus-maven-plugin:create`.

## Procedure

1. Open `.hermes/pins.json` — take
   `quarkus.platform.group-id` / `artifact-id` / `version`, compiler release,
   surefire pin. Do not hard-code versions from memory or docs examples.
2. Assemble `pom.xml` from `references/pom-structure.md`:
   - properties feed both BOM import and plugin version via
     `${quarkus.platform.*}`
   - `dependencyManagement` imports the BOM (`type=pom`, `scope=import`)
   - story `<dependencies>` carry foundation Jacoco test-scope wiring
     (see foundation-jacoco reference) plus the sole pom-writer
     `identity.extensions_apply` union (DD3). Later stories do not
     write `pom.xml`.
   - `<build>` declares
     `${quarkus.platform.group-id}:quarkus-maven-plugin` with
     `<extensions>true</extensions>` and explicit goals `build` /
     `generate-code` / `generate-code-tests` — **never**
     `io.quarkus` / `io.quarkus.platform` plugin GAV (H-1)
   - include the Maven `native` profile (property activation `-Dnative`)
3. Prefer factory/UDI `settings.xml` for Red Hat GA repos
   (`references/maven-repos.md`); in-POM `<repositories>` only as documented
   fallback when settings are absent.
4. Hand off to `bootstrap-quarkus-project` verification
   (`check-pom-platform-pins.py`, `check-pom-jacoco-wiring.py`).

## Pitfalls

- Reconstructing the POM from memory (S-001 burned ~half its reasoning
  budget on this) — load this skill + pins instead.
- Community `io.quarkus.platform` plugin GAV — registry and RHBQ docs
  publish the plugin under `com.redhat.quarkus.platform` with the BOM.
- Pasting doc-example platform versions into the POM — pins only.
- Filling `<dependencies>` with a fixed extension menu on foundation —
  evidence-driven per story (DD3 / T-3).
- Confusing Maven `-Dnative` profile with Quarkus `%profile.` config
  profiles (different mechanisms).

## Verification

- `quarkus.platform.group-id` resolves to `com.redhat.quarkus.platform`.
- Plugin groupId equals the BOM groupId property (same stream).
- Story extension deps = foundation Jacoco plus `identity.extensions_apply`
  on the sole pom.xml writer (later stories do not write the POM).
- `check-pom-platform-pins.py <root>` → OK once authored.
- `scripts/verify-maven-settings.py <root>` → OK when `.mvn/maven.config`
  has `-s` / `.mvn/settings.xml` and the RH GA profile is present. Maven 3
  does not auto-read `.mvn/settings.xml`.
