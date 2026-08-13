# Fixtures — AR-2.1 / AR-2.2 (runnable DB + real security)

Use with the check-release-readiness checkers:

```bash
# Idle on empty scaffold (no DB / security intent)
python3 .hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py .
python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py .

# Refuse known-bad fragments (copy under a temp tree that includes pom intent)
python3 .hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py \
  governance/fixtures/runnable-db-security/bad-db-kind-mismatch
# Tip-bank B7 — destination HSQLDB must REFUSE (not only mismatched pairs)
python3 .hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py \
  governance/fixtures/runnable-db-security/bad-hsqldb-destination
python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py \
  governance/fixtures/runnable-db-security/bad-placeholder-security
```

Live proving evidence (v10 workspace): `SecurityAuthzIT` 401 anonymous / 200 admin
after Flyway V1/V2 + JDBC clear-password mapper + MapStruct 1.6.3 (`jakarta.inject`).
