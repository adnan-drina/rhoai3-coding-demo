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
Verify: `mvn help:effective-settings`.

Factory / UDI / CI should provision this profile so destination POMs stay
free of infrastructure declarations.

## Fallback — in-POM repositories

Documented when settings.xml is unavailable (e.g. a seat that never
received factory Maven settings). Prefer fixing the environment over
baking `<repositories>` / `<pluginRepositories>` into the delivered POM.

## Self-contained builds

"Self-contained" means the **build environment** can resolve artifacts
(JDK, Maven, settings profile) — not that every POM must embed Red Hat
repository XML. Pipeline agents that already reach
`maven.repository.redhat.com/ga` carry settings; the POM cites pins only.
