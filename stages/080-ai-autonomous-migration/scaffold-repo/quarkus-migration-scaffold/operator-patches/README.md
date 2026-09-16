# Operator patches (specimen-scoped, ADR-authorized)

Not harness code and not applied by any tool. Each subdirectory is one
specimen; each file mirrors its path in the destination product tree. An
Operator copies a file in, has it reviewed by a second seat, and records the
change with `fix-until-green/scripts/operator-step.py --operator ... --reviewer
... --adr ADR-nnn`, which re-measures the tree and refuses if the measure is
not fully known afterwards. A patch under `src/test/` refuses without a
reviewer distinct from the operator.

**Fresh runs do not use this directory as a patch set** (ADR-019). The files
that are portable -- the reviewed new security classes and the reviewed
`ValidatorTests` port -- are consumed BY DIGEST from here by the bootstrap's
decided-repair manifest (`decided-repairs/<specimen>/manifest.json`); the
controllers, `pom.xml` and `application.properties` here are bound to one
run's baseline and are never copied into another run. Their decided changes
enter a fresh run as structural transformations instead. Editing a file the
manifest pins refuses the next bootstrap (`REPAIR_CONTENT_DIGEST`) until the
manifest, its review record and `decisions.yaml` are updated together.

Workers never write test sources; that prohibition is enforced at the
pre-tool-call hook and is not relaxed by anything here.

A subdirectory may carry a `MANIFEST.md` beside its files when one Operator
step applies several of them together: what each file implements, what it
derives from, and the exact verification the step must run.

| specimen | path | ADR |
|---|---|---|
| spring-petclinic-rest | `src/test/java/org/springframework/samples/petclinic/model/ValidatorTests.java` | ADR-008 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/SecurityMode.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/SourceBasicAuthenticationMechanism.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/HttpSecuritySwitch.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/DisabledAccountAugmentor.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/PrefixedPlainTextPasswordProvider.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/model/User.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/model/Role.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java` | ADR-014 |
| spring-petclinic-rest | `pom.xml` | ADR-014 |
| spring-petclinic-rest | `src/main/resources/application.properties` | ADR-014 |

The ADR-014 rows are one Operator step, bound to destination v9
(`06c51a49f4e6ff94c122f12929097e8cec3dc60e`); `spring-petclinic-rest/MANIFEST.md`
holds its clause map, the baseline it applies to, its verification and its
prerequisites.
