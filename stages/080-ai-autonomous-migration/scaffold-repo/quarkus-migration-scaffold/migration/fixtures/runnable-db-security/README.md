# Fixtures — AR-2.1 / AR-2.2 (runnable DB + real security)

Use with the validation-release-gates checkers:

```bash
# Idle on empty scaffold (no DB / security intent)
python3 .hermes/skills/gates/validation-release-gates/scripts/check-runnable-db-config.py .
python3 .hermes/skills/gates/validation-release-gates/scripts/check-empty-security.py .

# Refuse known-bad fragments (copy under a temp tree that includes pom intent)
python3 .hermes/skills/gates/validation-release-gates/scripts/check-runnable-db-config.py \
  migration/fixtures/runnable-db-security/bad-db-kind-mismatch
python3 .hermes/skills/gates/validation-release-gates/scripts/check-empty-security.py \
  migration/fixtures/runnable-db-security/bad-placeholder-security
```

Live proving evidence (v10 workspace): `SecurityAuthzIT` 401 anonymous / 200 admin
after Flyway V1/V2 + JDBC clear-password mapper + MapStruct 1.6.3 (`jakarta.inject`).
