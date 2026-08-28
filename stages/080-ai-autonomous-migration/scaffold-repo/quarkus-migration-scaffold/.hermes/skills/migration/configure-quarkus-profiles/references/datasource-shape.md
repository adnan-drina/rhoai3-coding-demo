# Datasource shape

Install **both** `quarkus-agroal` and a JDBC driver extension
(`quarkus-jdbc-h2`, `quarkus-jdbc-mysql`, `quarkus-jdbc-postgresql`, …).
The driver alone is incomplete.

| `quarkus.datasource.db-kind` | Extension |
|------------------------------|-----------|
| `h2` | `quarkus-jdbc-h2` |
| `mysql` | `quarkus-jdbc-mysql` |
| `postgresql` (aliases `pgsql`, `pg`) | `quarkus-jdbc-postgresql` |

Minimal shape:

```properties
quarkus.datasource.db-kind=postgresql
quarkus.datasource.username=<username>
quarkus.datasource.password=<password>
quarkus.datasource.jdbc.url=jdbc:postgresql://localhost:5432/<db>
quarkus.datasource.jdbc.max-size=16
```

Pool/URL keys live under `quarkus.datasource.jdbc.*`. Named datasources use
the `"name"` form when multiple units are required.

`db-kind` is typically **build-time-fixed** — a single artifact cannot honestly
swap driver families solely via runtime profile. Profile-scoped URLs/credentials
that are runtime-overridable still need the matching driver on the build
classpath if that profile must work.
