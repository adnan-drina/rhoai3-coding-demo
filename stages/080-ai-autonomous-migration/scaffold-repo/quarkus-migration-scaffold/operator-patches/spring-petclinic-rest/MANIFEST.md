# ADR-014 patch set — the source's security switch, in both modes

One bounded Operator step. Nothing here has been applied.

## The baseline this binds to

| | |
|---|---|
| destination | `wksp-ai-developer/workspace804b8343fd894fb9-574cc7495d-6db94:/projects/modernized` |
| baseline commit | **`06c51a49f4e6ff94c122f12929097e8cec3dc60e`** (v9 HEAD), *harness: install golden 4018da9a (project d2f438e2) over cdfd6a3b* |
| on top of | `a01d352` *m4: generated product tests (corpus d55f314d23e9, generator 1.1.0)* |
| read on | 2026-09-16 |

Every file below is a **complete file** as it lands in the product tree, produced
by transforming that commit's own content. Nothing was copied from the isolated
experiment (`/Users/adrina/Sandbox/rgctl-experiment/app`); the two trees have
diverged and the experiment's content would silently revert v9's repairs.

**What this step preserves, unchanged, in the files it does touch:**

- the ADR-012 Spring Data fragment adapters (the seven `*RepositoryOverride` /
  `*RepositoryImpl` types) — not touched at all;
- the root-path fix and `RootRestController` — not touched at all;
- `@Valid` on request bodies with `@Context UriInfo` for `Location`, which is
  v9's shape and *not* the experiment's explicit-validator shape — preserved
  verbatim in all seven controllers, where only the `@PreAuthorize` line differs;
- the generated product tests under `src/test/` and the generated parity tests
  under `src/parity-test/` — not touched at all;
- the `m4-parity` build profile in `pom.xml` — preserved; the only pom change is
  one added dependency;
- `src/main/java/.../security/Roles.java`, the frozen source's own file — not
  touched at all. Its members stay instance `public final String`, because
  `@PreAuthorize("hasRole(@roles.OWNER_ADMIN)")` resolves them as bean
  properties; making them `static` would change how all 33 expressions resolve.

`src/test/java/.../model/ValidatorTests.java` sits in this directory as an older
**ADR-008** patch and is **not** part of this step.

## Files

16 files. The clause column is the architect's approval of ADR-014 and its four
amendments.

| # | destination path | clause |
|---|---|---|
| 1 | `src/main/java/.../security/SecurityMode.java` | the single reader of `petclinic.security.enable`; first term of every method-security expression |
| 2 | `src/main/java/.../rest/OwnerRestController.java` | method authorization, 6 sites |
| 3 | `src/main/java/.../rest/PetRestController.java` | method authorization, 6 sites |
| 4 | `src/main/java/.../rest/PetTypeRestController.java` | method authorization, 5 sites |
| 5 | `src/main/java/.../rest/SpecialtyRestController.java` | method authorization, 5 sites |
| 6 | `src/main/java/.../rest/VetRestController.java` | method authorization, 5 sites |
| 7 | `src/main/java/.../rest/VisitRestController.java` | method authorization, 5 sites |
| 8 | `src/main/java/.../rest/UserRestController.java` | method authorization, 1 site |
| 9 | `src/main/java/.../model/User.java` | identity store: `@UserDefinition` entity mapping |
| 10 | `src/main/java/.../model/Role.java` | identity store: role mapping |
| 11 | `src/main/java/.../security/PrefixedPlainTextPasswordProvider.java` | credential format, `{noop}` preserved |
| 12 | `src/main/java/.../security/SourceBasicAuthenticationMechanism.java` | the source's HTTP Basic challenge |
| 13 | `src/main/java/.../security/HttpSecuritySwitch.java` | **amendment 1** — request-level policy and mechanism, both off one switch |
| 14 | `src/main/java/.../security/DisabledAccountAugmentor.java` | **amendment 2** — `users.enabled` enforced within authentication |
| 15 | `pom.xml` | one added dependency |
| 16 | `src/main/resources/application.properties` | configuration |

33 `@PreAuthorize` sites across 7 controllers, every original role expression
preserved verbatim as the second term of its conditional. No expression is
deleted, weakened or replaced; nothing grants a role to an anonymous caller; no
identity or credential is created anywhere in this patch set; no file here
contains a password.

## Amendment 1 — the request-level policy

The source's enabled configuration was two statements, not one:

```java
// BasicAuthenticationConfig, @ConditionalOnProperty(petclinic.security.enable=true)
http.authorizeRequests().anyRequest().authenticated()
    .and().httpBasic()
    .and().csrf().disable();
```

and its disabled configuration was the mirror:

```java
// DisableSecurityConfig, @ConditionalOnProperty(petclinic.security.enable=false)
http.authorizeRequests().anyRequest().permitAll().and().csrf().disable();
```

`anyRequest()` covers routes that carry no `@PreAuthorize` at all — in this
tree, `RootRestController`'s redirect at the application root. Method security
alone cannot express that, so `HttpSecuritySwitch` (file 13) registers the
policy as well as the mechanism, from **one observer**, off **one value**, so
the two halves cannot drift apart:

```java
void configure(@Observes HttpSecurity httpSecurity) {
    if (this.securityMode.isEnabled()) {
        httpSecurity.mechanism(new SourceBasicAuthenticationMechanism())
                    .path("*").authenticated();
    } else {
        httpSecurity.path("*").permit();
    }
}
```

**Why the path has no leading slash.** `ImmutablePathMatcher.ImmutablePathMatcherBuilder#addPath`
(measured in `quarkus-vertx-http-3.27.3.redhat-00002.jar`) prepends the
configured root path to any permission path that does not already start with
`/`; the same behaviour is documented for `quarkus.http.auth.permission.*.paths`.
So `"*"` is `quarkus.http.root-path` + `*` — here `/petclinic/*` — and the same
source text stays correct if the root path is ever reconfigured. `addWildcardPath`
reduces a trailing `/*` to the prefix `/petclinic`, so the permission covers the
application root itself (`/petclinic/`, the redirect) and everything under it.

**What is deliberately outside it.** `quarkus.http.non-application-root-path`
is `/q` by default and absolute, so it is not under the application root and
keeps the platform's own defaults — health, metrics and the OpenAPI document
answer as Quarkus ships them, in both modes. That surface has no counterpart in
the source. One consequence to know: v9's root redirect points at
`/swagger-ui/index.html`, which is likewise outside the application root, so the
redirect *target* is not covered by the policy even though the redirect itself
is. That boundary comes from where the destination serves its UI, not from this
step.

**Why the policy is registered programmatically rather than in properties.**
`quarkus.http.auth.permission.*` would have to hold one of the two modes. The
switch is a runtime value; the registration has to be too.

## Amendment 1, second half — why authentication is registered at runtime

The experiment's finding D-6 set `quarkus.http.auth.basic=true` **always**, on
the ground that the platform resolves that key at build time. The build-time
fact is correct; the conclusion that authentication therefore cannot follow the
switch is not. Measured against the platform artifact this destination builds
with, `quarkus-vertx-http-3.27.3.redhat-00002.jar`:

- `io.quarkus.vertx.http.runtime.AuthConfig` (from `VertxHttpBuildTimeConfig.auth()`)
  declares `basic()`, `form()`, `proactive()` — build time, as D-6 says.
- `io.quarkus.vertx.http.security.HttpSecurity` exists and carries
  `mechanism(HttpAuthenticationMechanism)`, `path(String...)` →
  `HttpPermission`, and on that `authenticated()`, `permit()`, `roles(String...)`,
  `policy(HttpSecurityPolicy)`. Verified with `javap` against the jar.
- `HttpSecurityConfiguration#prepareHttpSecurity` fires `HttpSecurity` as a CDI
  event at **runtime** — `Arc.container().beanManager().getEvent().select(HttpSecurity.class).fire(...)`
  — from `initializeHttpSecurityConfiguration`, which resolves its configuration
  through `ConfigProvider`. An observer therefore runs after runtime
  configuration is available.
- `initializeHttpSecurityConfiguration` then **promotes** the build-time value:
  when `auth().basic()` is empty or false and the programmatically supplied
  mechanism list contains a `BasicAuthenticationMechanism`, it replaces the
  value with `Optional.of(TRUE)`. A build-time `false` does not veto a runtime
  registration.
- `addBasicAuthMechanismIfImplicitlyRequired` adds an implicit mechanism only
  when the system property
  `io.quarkus.security.http.test-if-basic-auth-implicitly-required` is set
  (`HttpSecurityProcessor#detectBasicAuthImplicitlyRequired`) **and**
  `isBasicAuthNotRequired()` is false, which needs a `@BasicAuthentication`
  annotation or an HTTP permission whose `auth-mechanism` is `basic`. This
  specimen has neither — the disabled-mode `permit()` names no mechanism — so
  with the switch off the application ends up with
  `HttpAuthenticator.NoAuthenticationMechanism`: no mechanism at all, which is
  the source's state under `DisableSecurityConfig`.

Two further measured facts shaped file 12:

- `io.quarkus.vertx.http.security.Basic.realm(r)` constructs
  `new BasicAuthenticationMechanism(r, /* silent */ true)`, and in silent mode
  `getChallenge` returns **no** `WWW-Authenticate` when the request carried no
  `Authorization` header. Forty enabled-mode source captures assert that header,
  so `Basic.realm(...)` cannot be used; the mechanism is constructed non-silent.
- The platform builds its challenge from the constant `basic` in lower case —
  the concatenation recipe in `BasicAuthenticationMechanism`'s constructor is
  `basic realm=""` — while the source captured
  `WWW-Authenticate: Basic realm="Realm"` (Spring's
  `BasicAuthenticationEntryPoint`, default realm name `Realm`). File 12 delegates
  everything except the challenge line, which it writes with the source's exact
  bytes. Credential reading, decoding and the identity request are the platform's.
- `quarkus.http.auth.realm` is **not** set: `HttpSecurityImpl#mechanism` throws
  `IllegalArgumentException` ("Cannot configure basic authentication
  programmatically because the authentication realm has already been configured
  in the 'application.properties' file") when it is. The realm travels with the
  mechanism instead.

**Fallback, if the enabled-mode run shows the runtime registration does not take
effect.** Delete file 12 and the `mechanism(...)` call in file 13, set
`quarkus.http.auth.basic=true`, keep the path policy and
`quarkus.http.auth.proactive=false`, and the architect must accept D-6 —
authentication always present, the switch governing authorization only. Marker:
**`ADR-014-D6-FALLBACK`**. The path policy does not depend on this: it is
registered from the same observer either way.

## Amendment 2 — account status, enforced within authentication

The source's identity query was
`select username,password,enabled from users where username=?`
(`BasicAuthenticationConfig#configureGlobal`, `jdbcAuthentication`), and Spring's
`JdbcDaoImpl` refuses a row whose `enabled` is false with `DisabledException` —
an `AuthenticationException`, so the caller is answered with the authentication
challenge: **401, never 403**.

quarkus-security-jpa 3.27 has no account-status member: `@UserDefinition`,
`@Username`, `@Password`, `@Roles`, `@RolesValue` plus `PasswordProvider` /
`PasswordType` are the whole annotation set in
`quarkus-security-jpa-common-3.27.3.redhat-00002.jar`. So the clause is supplied
beside the provider, by `DisabledAccountAugmentor` (file 14), a
`SecurityIdentityAugmentor` that:

- is inert for an anonymous identity and inert with the switch off;
- reads the `enabled` column of the one row that just authenticated
  (`select u.enabled from User u where u.username = :username`) and throws
  `io.quarkus.security.AuthenticationFailedException` when it is not true, or
  when the row has vanished — the source refuses an absent row for the same
  reason, `UsernameNotFoundException`, also an `AuthenticationException`;
- never widens an identity: the only outcomes are "the identity the provider
  built" and "authentication failed". It contributes no role, no identity and
  no credential, and names no identifier in its message.

**Why not `@SQLRestriction("enabled")` on the entity.** That is a global entity
filter: `UserRepositoryImpl#save` does `em.find(User.class, username)`, so the
restriction would also change what "this user already exists" means on
`POST /api/users` — user-management behaviour ADR-014 does not authorize. The
architect refused that, and this file does not do it.

**Session handling is the platform's own recipe**, taken from
`io.quarkus.security.jpa.runtime.JpaIdentityProvider` (read with `javap` from
`quarkus-security-jpa-3.27.3.redhat-00002.jar`): run under
`AuthenticationRequestContext#runBlocking`, `SessionFactory#openSession`,
`setDefaultReadOnly(true)`, `setHibernateFlushMode(FlushMode.MANUAL)`, close.
One short read-only session per authentication, off the request thread — the
cost the architect priced when approving the augmentor over the entity filter.

## Amendment 3 — the floor

Corrected in `.hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py`
(harness, not product; outside this Operator step, already landed):

- `quarkus-security-jpa` is recognised as a provider **when the tree maps the
  entity it generates from** — a type carrying `@UserDefinition` with
  `@Username` and `@Password`. The extension alone provides nothing, so
  presence of the dependency is not the question.
- The JDBC-only demand is gone: `security enabled without
  quarkus-elytron-security-jdbc` is replaced by *security enabled with no
  identity provider*, which accepts any provider in the tuple, a configured
  identity, or the JPA entity, and whose message names all of them.
- The `pom missing quarkus-security` substring rule is replaced by a whole-match
  test for any extension that brings the security runtime, so a tree whose only
  security dependency is a provider is read correctly.
- `quarkus.http.auth.*` set to `false` no longer counts as a configured
  identity — that key turns a mechanism **off**, and reading it as an identity
  would have passed this very patch set for the wrong reason.
- The `static final role constants` rule is gone. `@roles.OWNER_ADMIN` is a
  bean-property lookup by name; the member's modifiers are not part of that
  resolution, and the source's holder uses instance fields. What replaced it
  reads the role expressions and refuses one that resolves to nothing: an
  expression naming a constant no type in the tree declares — the shape a
  deleted role expression actually leaves behind.
- The ADR-014 BLOCK is unchanged: method-security annotations with no provider
  anywhere still fail, still naming the annotations, the providers and the 403.

## Dependencies added, and where each is used

One dependency, `io.quarkus:quarkus-security-jpa` (managed by the platform BOM,
no version in the pom).

| brought in | used by |
|---|---|
| `io.quarkus.security.jpa.{UserDefinition,Username,Password,PasswordType,Roles,RolesValue}` | files 9, 10 — the entity mapping the identity provider is generated from |
| `io.quarkus.security.jpa.PasswordProvider`, `org.wildfly.security.password.*` (transitive, via `quarkus-elytron-security-common`) | file 11 — reading the `{noop}` credential format |

Nothing else is added. In particular no dependency is added to satisfy the
floor: `io.quarkus.security.identity.*` and
`io.quarkus.vertx.http.{runtime.security,security}.*` (files 12, 13, 14) already
resolve through `quarkus-spring-security` and `quarkus-rest`, and
`org.hibernate.SessionFactory` (file 14) through `quarkus-hibernate-orm`, all of
which v9 already declares.

**The destination's local repository does not yet hold the new artifacts.**
Measured on the pod: `~/.m2/repository/io/quarkus/` has no `quarkus-security-jpa`,
no `quarkus-security-jpa-common`, no `quarkus-elytron-security-common`, and
`~/.m2/repository/org/wildfly/security/` has no `wildfly-elytron-credential`
or `wildfly-elytron-password-impl`; there is no `~/.m2/settings.xml`. **An
offline build (`mvn -o`) of the patched tree will fail to resolve, before any of
the verification below can run.** The Operator must resolve those artifacts —
an online build, or seeding them into the destination's local repository —
as the first action of the step. This is a prerequisite, not a defect in the
patch set.

## Measurements taken while preparing this set

| what | how | result |
|---|---|---|
| the patched tree compiles | `javac -proc:none` over v9's complete `src/main/java` (81 sources) plus `target/generated-sources` (the OpenAPI DTOs and the MapStruct implementations), with the 14 patched Java files swapped in, against the real dependency classpath resolved from `~/.m2` at platform `3.27.3.redhat-00002` | **exit 0, no errors**; only v9's own pre-existing warnings under `-Xlint:all` |
| every platform API used exists in 3.27 | `javap` against `quarkus-vertx-http`, `quarkus-security-jpa`, `quarkus-security-jpa-common` and `io.quarkus.security:quarkus-security:2.2.1.redhat-00001`, all at the versions this destination resolves | `HttpSecurity#{mechanism,path}`, `HttpPermission#{authenticated,permit,policy}`, `HttpSecurityPolicy`, `SecurityIdentityAugmentor#augment`, `AuthenticationRequestContext#runBlocking`, `AuthenticationFailedException`, the six security-jpa annotations — all present |
| the floor's ADR-014 rule on **unpatched v9** | `check-empty-security.py <v9 root>` | **BLOCK**: `AR-2.2 method security with no identity provider: @PreAuthorize (7 sites …)` — the floor this step must clear |
| the floor on the **patched tree** | same script, corrected as in amendment 3 | **OK: AR-2.2 security surface (3 class(es), 33 role expression(s), provider: quarkus-security-jpa over the @UserDefinition entity User.java)** — and no other rule in the script fails |
| the oracle corpora exist as cited | `ls` on the destination | 28 `sc_*.json` disabled, 34 `ep_*.json`, 60 `sc_*.json` enabled (20 `auth-allowed`, 20 `auth-anonymous`, 20 `auth-invalid`) |
| which oracle covers the application root | scan of every oracle's request path | `ep_…RootRestController_redirectToSwagger…json` and `scenarios/sc_read-root.json` — **both disabled-mode only** |

**No runtime measurement was taken, and none could be taken here.** Maven, the
RHBQ artifacts and the destination database are on the pod; this workstation
has no copy of the pod's tree it may build, and the patch set is files only.
Everything below is therefore a first measurement, deferred to the step.

## Verification the Operator step must run, on v9

Prerequisite: resolve the new dependencies (see above), then all of it on the
**packaged production artifact** built from the patched tree — **one artifact
for both modes**, restarted with the property flipped. That is the claim ADR-014
makes and the reason the mechanism and the policy are registered at runtime.
Credentials come from the environment variables `decisions.yaml` names
(`PETCLINIC_ADMIN_CREDENTIAL`, `PETCLINIC_INVALID_CREDENTIAL`); no credential is
written into any file.

1. **Build and the existing suite.** `mvn -B verify -Pm4-parity` on the
   destination root: clean, with the generated product tests and the generated
   parity tests under `src/parity-test` unchanged.
2. **Floor.**
   `python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py .`
   — expected OK, with the provider named. Record the line.
3. **Disabled mode** (`petclinic.security.enable=false`, the shipped default).
   All 28 `sc_*.json` in `verification/source-oracles/scenarios/` with
   `compare-scenario-parity.py --root . --scenario <id> --dest-url <url> --security-mode disabled`,
   and all 34 `ep_*.json` with
   `compare-runtime-parity.py --root . --entry-point <ep> --dest-url <url>`.
   Nothing that passed before this step may change. `sc_read-root.json` is the
   one that proves the new path policy permits in the disabled mode. A request
   that carries an `Authorization` header must also be unaffected: with no
   mechanism registered nothing reads it.
4. **Enabled mode** (`petclinic.security.enable=true`, same artifact, restarted).
   All 60 `sc_*.json` in `verification/source-oracles/scenarios-enabled/` with
   `compare-scenario-parity.py … --security-mode enabled`:
   - `sc:auth-allowed-*` (20) — the seeded `admin` identity authenticates over
     the JPA store, `{noop}` is read as plaintext, the roles map, and the
     original role expression authorizes: 2xx, same bodies and effects as the
     disabled mode.
   - `sc:auth-anonymous-*` (20) — 401 with `WWW-Authenticate: Basic realm="Realm"`,
     byte for byte. This is what file 12 exists for.
   - `sc:auth-invalid-*` (20) — 401 with the same challenge; the invalid
     credential is rejected, not ignored.
5. **The request policy, on a route with no `@PreAuthorize`** — amendment 1's
   distinguishing case, which **no oracle covers**: the root is captured in the
   disabled corpus only. In the enabled mode, an anonymous
   `GET <root-path>` must answer **401 with the source's challenge**, not the
   302 it answers in the disabled mode, because the source's
   `anyRequest().authenticated()` covered it. The expected answer is read from
   the source's code, not from a capture; record it as a first measurement and
   say so. Two more anonymous enabled-mode probes belong with it: `/q/health`
   must still answer as Quarkus ships it (the non-application root is outside
   the policy), and any unmapped path under the application root must answer
   401 rather than 404, because the policy runs before routing.
6. **Account status** — amendment 2's case, which **no oracle covers either**:
   `populateDB.sql` seeds exactly one user, `admin`, with `enabled = true`.
   With the application running in the enabled mode, set that row's `enabled`
   to false **in the destination database only** (`update users set enabled =
   false where username = 'admin'`), repeat one `sc:auth-allowed-*` request,
   and require **401 with the source's challenge** — not 403, and not 200.
   Restore the row (`… set enabled = true …`) and require the same request to
   answer 2xx again. Neither the seed file nor any product file is edited by
   this check. Record both answers.
7. **Both modes from one artifact.** The enabled run must use the same built
   artifact as the disabled run.

Recording:

```
python3 .hermes/skills/migration/fix-until-green/scripts/operator-step.py \
  --root . --operator <seat> --author <seat> --adr ADR-014 \
  --reason "ADR-014: the source's security switch in both modes -- conditional method authorization, the request-level policy, Basic authentication over the JPA identity store, and account status within authentication" \
  --verify-cmd <the command that runs steps 1-7>
```

No `--reviewer` is required by ADR-008 for this set — it touches no test source.
The Operator should still take one: files 12, 13 and 14 are platform-facing code
that has never run.

## Deviations from the experiment

1. **`UserRestController` is included.** The experiment's `418e825` left its one
   `@PreAuthorize("hasRole(@roles.ADMIN)")` unconditional, so on that tree
   `POST /api/users` answers 403 in the disabled mode. No captured scenario
   reaches that entry point in either corpus, which is why the experiment never
   saw it. The 33rd site is converted here.
2. **`application.properties` keys differ.** `quarkus.http.auth.basic=false`
   (not `true`), plus the runtime registration.
3. **Three new files (12, 13, 14)** that the experiment does not have; 13 and 14
   exist only because of the architect's amendments.
4. **Import style.** The experiment wrote the quarkus-security-jpa annotations
   fully qualified inline; here they are imported.
5. **`@PreAuthorize( "…" )` spacing** in `UserRestController` is normalised to
   `@PreAuthorize("…")`, matching the other six controllers.
6. **`JacksonCreatorPropertyCustomizer.java` is not here.** It rides in the same
   experiment commit but is the D-4 Jackson restoration, not security, and v9's
   lineage for it differs.
7. **Account status is closed, not recorded as open.** The earlier candidate
   left it unenforced and said so; the architect refused waiving it because
   today's seed cannot expose it. File 14 enforces it and step 6 exposes it.
