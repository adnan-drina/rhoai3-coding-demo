# ADR-014 patch set — the source security switch in both modes

Candidate for one bounded Operator step. Nothing here has been applied.

Derived from the official destination **v9**'s current sources (read out of
`wksp-ai-developer/workspace804b8343fd894fb9-574cc7495d-6db94:/projects/modernized`
on 2026-09-16), with the transformation the isolated experiment
(`/Users/adrina/Sandbox/rgctl-experiment/app`) verified applied to *that*
content. The two trees have diverged, so nothing was copied across: v9 already
carries the ADR-012 fragment adapters, the ADR-016 root redirect and
controllers whose CORS handling moved to configuration, and it keeps `@Valid`
on request bodies with `@Context UriInfo` for `Location`, where the experiment
calls the validator explicitly. Only the security transformation is applied.

The files below are complete files as they land in the destination product
tree. `src/test/java/.../ValidatorTests.java` is an older ADR-008 patch in the
same directory and is **not** part of this step.

## Files

| # | destination path | ADR-014 clause | derived from |
|---|---|---|---|
| 1 | `src/main/java/org/springframework/samples/petclinic/security/SecurityMode.java` | the conditional authorization adapter; single reader of the switch | exp `418e825` (new file, javadoc extended for the authentication half) |
| 2 | `src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java` | `@PreAuthorize("@securityMode.disabled() or <original>")`, 6 sites | exp `418e825` transformation, v9 content |
| 3 | `src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java` | same, 6 sites | exp `418e825` transformation, v9 content |
| 4 | `src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java` | same, 5 sites | exp `418e825` transformation, v9 content |
| 5 | `src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java` | same, 5 sites | exp `418e825` transformation, v9 content |
| 6 | `src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java` | same, 5 sites | exp `418e825` transformation, v9 content |
| 7 | `src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java` | same, 5 sites | exp `418e825` transformation, v9 content |
| 8 | `src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java` | same, 1 site — **not in the experiment**, see Deviations | exp `418e825` transformation, v9 content |
| 9 | `src/main/java/org/springframework/samples/petclinic/model/User.java` | Basic authentication over the JPA identity store: entity mapping | exp `23fb8d3`, v9 content |
| 10 | `src/main/java/org/springframework/samples/petclinic/model/Role.java` | role mapping | exp `23fb8d3`, v9 content |
| 11 | `src/main/java/org/springframework/samples/petclinic/security/PrefixedPlainTextPasswordProvider.java` | password verification, `{noop}` credential format preserved | exp `23fb8d3` (new file, unchanged) |
| 12 | `src/main/java/org/springframework/samples/petclinic/security/SourceBasicAuthenticationMechanism.java` | HTTP authentication follows the switch: the source's challenge | **new**, see "HTTP authentication" |
| 13 | `src/main/java/org/springframework/samples/petclinic/security/HttpAuthenticationSwitch.java` | HTTP authentication follows the switch: runtime registration | **new**, see "HTTP authentication" |
| 14 | `pom.xml` | dependencies: the identity provider | exp `23fb8d3`, v9 content |
| 15 | `src/main/resources/application.properties` | configuration | exp `23fb8d3` shape, **different keys**, see "HTTP authentication" |

33 `@PreAuthorize` sites across 7 controllers. Every original role expression
is preserved verbatim as the second term of its conditional. No expression is
deleted, weakened or replaced; nothing grants a role to an anonymous caller;
no identity or credential is created anywhere in this patch set, and the one
seeded credential stays where it is, in the seed data, untouched. No file here
contains a password, and none needs to: the enabled-mode verification takes its
identities from the environment variables `decisions.yaml` names.

## HTTP authentication follows the switch (ADR-014, not D-6)

The experiment's finding D-6 implemented the enabled mode with
`quarkus.http.auth.basic=true` **always**, the switch governing authorization
only, on the ground that the platform resolves that key at build time. The
build-time fact is correct; the conclusion that authentication therefore
cannot follow the switch is not. Measured against the platform artifact this
destination builds with, `quarkus-vertx-http-3.27.3.redhat-00002.jar`:

- `io.quarkus.vertx.http.runtime.AuthConfig` (reached from
  `VertxHttpBuildTimeConfig.auth()`) declares `basic()`, `form()`,
  `proactive()` — build time, as D-6 says.
- `io.quarkus.vertx.http.security.HttpSecurity` and
  `io.quarkus.vertx.http.security.Basic` are present: the platform's
  programmatic HTTP security API.
- `HttpSecurityConfiguration#prepareHttpSecurity` fires `HttpSecurity` as a
  **CDI event at runtime** — `Arc.container().beanManager().getEvent()
  .select(HttpSecurity.class).fire(...)` — from
  `initializeHttpSecurityConfiguration`, which resolves its configuration
  through `ConfigProvider`. An observer therefore runs after runtime
  configuration is available and can decide whether to register a mechanism.
- `initializeHttpSecurityConfiguration` then promotes the build-time value:
  when `auth().basic()` is empty **or false** and the programmatically
  supplied mechanism list contains a `BasicAuthenticationMechanism`, it
  replaces the value with `Optional.of(TRUE)`. So a build-time `false` does
  not veto a runtime registration — it only stops the build from registering
  one unconditionally.
- `addBasicAuthMechanismIfImplicitlyRequired` adds an implicit mechanism only
  when the system property
  `io.quarkus.security.http.test-if-basic-auth-implicitly-required` is set
  (`HttpSecurityProcessor#detectBasicAuthImplicitlyRequired`) **and**
  `isBasicAuthNotRequired()` is false, which needs a `@BasicAuthentication`
  annotation or an HTTP permission whose `auth-mechanism` is `basic`. This
  specimen has neither, so with the switch off the application ends up with
  `HttpAuthenticator.NoAuthenticationMechanism` — no mechanism at all, which
  is exactly the source's state under `DisableSecurityConfig`.

So: `quarkus.http.auth.basic=false` in `application.properties`, and
`HttpAuthenticationSwitch` registers the mechanism from the **same** runtime
property `SecurityMode` reads. D-6's shape is not used. If the Operator's
enabled-mode run shows the runtime registration does not take effect on this
platform, the fallback is exactly D-6: delete files 12 and 13, set
`quarkus.http.auth.basic=true`, keep `quarkus.http.auth.proactive=false`, and
the architect must accept D-6 — authentication always present, the switch
governing authorization only. **Marker: `ADR-014-D6-FALLBACK`.**

Two further measured facts shaped file 12:

- `io.quarkus.vertx.http.security.Basic.realm(r)` constructs
  `new BasicAuthenticationMechanism(r, /* silent */ true)`, and in silent mode
  `getChallenge` returns **no** `WWW-Authenticate` when the request carried no
  `Authorization` header. Twenty anonymous enabled-mode captures assert that
  header, so `Basic.realm(...)` cannot be used; the mechanism is constructed
  non-silent.
- The platform builds its challenge from the constant `basic` in lower case —
  the string-concatenation recipe in `BasicAuthenticationMechanism`'s
  constructor is `basic realm=""` — while the source captured
  `WWW-Authenticate: Basic realm="Realm"` (Spring's
  `BasicAuthenticationEntryPoint`, default realm name `Realm`). File 12
  therefore delegates everything except the challenge line, which it writes
  with the source's exact bytes. Nothing else about credential reading,
  decoding or the identity request is re-implemented.
- `quarkus.http.auth.realm` is **not** set: `HttpSecurityImpl#mechanism`
  throws `IllegalArgumentException` ("Cannot configure basic authentication
  programmatically because the authentication realm has already been
  configured in the 'application.properties' file") when it is. The realm
  travels with the mechanism instead.

## Open ADR-014 clause: account-status behaviour

The source's identity query was
`select username,password,enabled from users where username=?`
(`BasicAuthenticationConfig#configureGlobal`, `jdbcAuthentication`), and
Spring's `JdbcDaoImpl` rejects a row whose `enabled` is false.
**quarkus-security-jpa 3.27 has no account-status member**: the whole
annotation set in `quarkus-security-jpa-common-3.27.3.redhat-00002.jar` is
`@UserDefinition`, `@Username`, `@Password`, `@Roles`, `@RolesValue` plus
`PasswordProvider` / `PasswordType`. The column is mapped and carried but it
is not consulted, so this clause is **PARTIAL**. **Marker:
`ADR-014-ACCOUNT-STATUS-OPEN`.**

It is unobservable on the declared dataset — `populateDB.sql` seeds exactly one
user, `admin`, with `enabled = true`, and no captured scenario in either mode
uses another identity — so no verification here can distinguish the two. Two
implementations exist if the architect wants the clause closed rather than
recorded:

1. `@SQLRestriction("enabled")` on the `User` entity. One annotation, but it is
   an entity-wide SQL restriction and `UserRepositoryImpl#save` does
   `em.find(User.class, username)`, so it would also change what "this user
   already exists" means on `POST /api/users`.
2. A `SecurityIdentityAugmentor` that re-reads the row and throws
   `AuthenticationFailedException` for a disabled account. No effect on the
   entity, at the cost of one blocking read per authentication.

Neither is in this patch set: both add runtime behaviour that the declared
dataset cannot exercise, and this step is meant to be measurable.

## Verification the Operator step must run

All of it on the **packaged production artifact** built from the patched tree,
one artifact for both modes, against the reset destination. Credentials come
from the environment variables `decisions.yaml` names
(`PETCLINIC_ADMIN_CREDENTIAL`, `PETCLINIC_INVALID_CREDENTIAL`); no credential
is written into any file.

1. **Build.** `mvn -o package` on the destination root — clean, with the
   generated product tests unchanged.
2. **Floor.**
   `python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py .`
   The AR-2.2 rule this patch set exists to satisfy — *method security with no
   identity provider* — must no longer fire. It does not: it is the rule that
   fails on v9 today (7 `@PreAuthorize` sites, no provider) and it is cleared
   by `quarkus-security-jpa` in file 14, measured. **Two other rules in the
   same script still fail on the patched tree and cannot be satisfied by any
   product change ADR-014 authorizes** — see "Gate defects" below. The
   Operator must record that the ADR-014 rule passes and that those two are
   harness defects, not weaken the patch set to appease them.
3. **Disabled mode** (`petclinic.security.enable=false`, the shipped default).
   Every qualified scenario in `verification/source-oracles/scenarios/`
   (28 `sc_*.json`) with
   `compare-scenario-parity.py --root . --scenario <id> --dest-url <url> --security-mode disabled`,
   and every read oracle in `verification/source-oracles/` (34 `ep_*.json`)
   with `compare-runtime-parity.py --root . --entry-point <ep> --dest-url <url>`.
   Anonymous requests must answer exactly as they did before this step: the
   switch being off must change nothing that already passed. A request that
   carries an `Authorization` header must also be unaffected, because with no
   mechanism registered nothing reads it.
4. **Enabled mode** (`petclinic.security.enable=true`, same artifact,
   restarted). All 60 `sc_*.json` in
   `verification/source-oracles/scenarios-enabled/` with
   `compare-scenario-parity.py ... --security-mode enabled`. The three
   families and what each proves:
   - `sc:auth-allowed-*` (20) — the seeded `admin` identity authenticates over
     the JPA store, `{noop}` is read as plaintext, the roles map, and the
     original role expression authorizes: 2xx and the same bodies and effects
     as the disabled mode.
   - `sc:auth-anonymous-*` (20) — 401 with
     `WWW-Authenticate: Basic realm="Realm"`, byte for byte. This is the
     assertion that file 12 exists for.
   - `sc:auth-invalid-*` (20) — 401 with the same challenge; the invalid
     credential is rejected, not ignored.
   No enabled-mode parity was ever run in the experiment (its
   `evidence/this-run/parity-*.json` are bound to the disabled corpus
   `d55f314d…` only), so **every one of these 60 is a first measurement**.
5. **Both modes from one artifact.** The enabled run must use the same built
   artifact as the disabled run, restarted with the property flipped — that is
   the claim ADR-014 makes and the reason the mechanism is registered at
   runtime rather than at build time.

Recording:

```
python3 .hermes/skills/migration/fix-until-green/scripts/operator-step.py \
  --root . --operator <seat> --author <seat> --adr ADR-014 \
  --reason "ADR-014 conditional authorization adapter, Basic authentication over the JPA identity store, HTTP authentication bound to the switch" \
  --verify-cmd <the command that runs steps 1-4>
```

No `--reviewer` is required by ADR-008 for this set — it touches no test
source. The Operator should still take one, because files 12 and 13 are new
platform-facing code that the experiment never ran.

## Gate defects found while preparing this set

Measured by running the gate script against the patched tree and against
unpatched v9 (`check-empty-security.py <root>`):

- **v9 today:** `FAIL: AR-2.2 method security with no identity provider:
  @PreAuthorize (7 sites …)`. This is the floor the step must clear, and it
  does.
- **patched tree:** `FAIL: AR-2.2 security enabled without
  quarkus-elytron-security-jdbc`. The script sets `security_enabled` from the
  mere presence of `*Security*.java` / `*Authentication*.java` types (and, in
  the enabled mode, from `^[\w.-]+\.security\.enable\s*=\s*true$`), then
  demands `quarkus-elytron-security-jdbc` by name. ADR-014 rules the **JPA**
  identity store. The rule predates the ADR and names one provider where the
  same script's own `IDENTITY_PROVIDERS` tuple already lists six. Adding an
  unused extension to satisfy it would be a false green.
- **patched tree:** `FAIL: AR-2.2/AR-3.1
  src/main/java/org/springframework/samples/petclinic/security/Roles.java
  lacks static final role constants`. `Roles.java` is the frozen source's own
  file, carried through the bootstrap untouched, and its fields are instance
  `public final String` because `@PreAuthorize("hasRole(@roles.OWNER_ADMIN)")`
  resolves them as bean properties. Making them `static` to satisfy the rule
  would change how every one of the 33 expressions resolves, unverified. This
  patch set does not touch `Roles.java`.

Both are harness defects in `.hermes/skills/gates/check-release-readiness/`,
outside the authority of an operator patch. They block the gate, not the
product.

## Compile check

`javac -proc:none` of v9's complete `src/main/java` plus its
`target/generated-sources` (the OpenAPI DTOs and the MapStruct mapper
implementations), with the 13 patched Java files swapped in, against the real
dependency classpath resolved offline from the experiment's `~/.m2`
(`mvn -o dependency:build-classpath`, Quarkus platform
`3.27.3.SP1-redhat-00002`): **clean, no errors, no warnings**. So
`io.quarkus.security.jpa.*`, `io.quarkus.vertx.http.runtime.security.*`,
`io.quarkus.vertx.http.security.HttpSecurity` and
`org.wildfly.security.password.*` all resolve against the artifacts this
destination actually builds with.

The compiler cannot decide the two runtime questions: whether the `HttpSecurity`
observer registers the mechanism as the bytecode says it will, and whether
the challenge bytes match. Step 4 decides both.

## Deviations from the experiment

1. **`UserRestController` is included.** The experiment's `418e825` left its
   one `@PreAuthorize("hasRole(@roles.ADMIN)")` unconditional, so on that tree
   `POST /api/users` answers 403 in the disabled mode. No captured scenario
   reaches that entry point in either corpus, which is why the experiment
   never saw it. ADR-014 asks for the inventoried security surface, and
   `check-empty-security` counts every site in the tree, so the 33rd site is
   converted here.
2. **`application.properties` keys differ.** `quarkus.http.auth.basic=false`
   (not `true`) plus the runtime registration, per the ruling that HTTP
   authentication follows the switch.
3. **Two new files (12, 13)** that the experiment does not have.
4. **Import style.** The experiment wrote the quarkus-security-jpa annotations
   fully qualified inline; here they are imported. No semantic difference.
5. **`@PreAuthorize( "…" )` spacing** in `UserRestController` is normalised to
   `@PreAuthorize("…")`, matching the other six controllers.
6. **`JacksonCreatorPropertyCustomizer.java` is not here.** It rides in the
   same experiment commit but is the D-4 Jackson restoration, not security,
   and v9's lineage for it differs.
7. **Account status is open**, marked above; the experiment did not address
   the clause at all.

## Row for `operator-patches/README.md`

Fifteen rows, one per file, all `spring-petclinic-rest` / `ADR-014` — added in
that file's table.
