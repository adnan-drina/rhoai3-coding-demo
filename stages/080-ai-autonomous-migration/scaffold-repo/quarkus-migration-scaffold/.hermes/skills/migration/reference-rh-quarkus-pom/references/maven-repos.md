# Maven repository resolution (T-1 / Q2)

Red Hat's stated recommendation: configure the Red Hat GA repository in the
user or pipeline `settings.xml`, **not** inside every project POM.

## Primary — settings.xml profile

```xml
<profile>
  <id>red-hat-enterprise-maven-repository</id>
  <repositories>
    <repository>
      <id>red-hat-enterprise-maven-repository</id>
      <url>https://maven.repository.redhat.com/ga/</url>
      <releases><enabled>true</enabled></releases>
      <snapshots><enabled>false</enabled></snapshots>
    </repository>
  </repositories>
  <pluginRepositories>
    <pluginRepository>
      <id>red-hat-enterprise-maven-repository</id>
      <url>https://maven.repository.redhat.com/ga/</url>
      <releases><enabled>true</enabled></releases>
      <snapshots><enabled>false</enabled></snapshots>
    </pluginRepository>
  </pluginRepositories>
</profile>
```

Activate with `<activeProfile>red-hat-enterprise-maven-repository</activeProfile>`.

Maven 3 does **not** auto-read `.mvn/settings.xml`. This scaffold ships:

- `.mvn/settings.xml` — the RH GA profile above
- `.mvn/maven.config` — `-s` / `.mvn/settings.xml` (one argument per line for Maven 3.9)

Do not write `~/.m2/settings.xml` from a story worker (write-fence, resolved path).
Do not embed `<repositories>` in the dest POM.

**Verify (refuse naming the gap):**

```bash
python3 .hermes/skills/migration/reference-rh-quarkus-pom/scripts/verify-maven-settings.py .
```

That script requires the two `.mvn/` files and, when `mvn` is on PATH,
`mvn help:effective-settings` must show `red-hat-enterprise-maven-repository`.

## Fallback — in-POM repositories

Documented when settings.xml is unavailable (e.g. a seat that never
received factory Maven settings). Prefer fixing the environment over
baking `<repositories>` / `<pluginRepositories>` into the delivered POM.

## Self-contained builds

"Self-contained" means the **build environment** can resolve artifacts
(JDK, Maven, settings profile) — not that every POM must embed Red Hat
repository XML. Pipeline agents that already reach
`maven.repository.redhat.com/ga` carry settings; the POM cites pins only.
