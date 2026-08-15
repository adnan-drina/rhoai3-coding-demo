# Golden — basic authz (R-HX.13 / security A-bar)

Neutral (non-ReferenceApp) example for `references/security-config.md`.

## Expected runtime

| Request | Expect |
|---------|--------|
| `GET /api/admin` anonymous | 401 |
| `GET /api/admin` Basic user/user | 403 |
| `GET /api/admin` Basic admin/admin | 200 |

## Files

- `src/main/resources/application.properties` — basic + permissions + JDBC identity  
- `src/main/java/com/example/auth/Roles.java` — role constants  
- `src/main/java/com/example/auth/AdminResource.java` — protected resource  
- `src/test/java/com/example/auth/SecurityAuthzIT.java` — 401/403/200  

Copy into a Quarkus product module (or adapt packages). Tip tree is the
**teaching + structure** golden; full `mvn test` runs on the product after copy.
Negative twin: `.hermes/skills/harness/validate-contracts/fixtures/runnable-db-security/bad-placeholder-security/`.
