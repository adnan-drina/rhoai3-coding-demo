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
decided-repair manifest (`decided-repairs/<specimen>/manifest.json`). Historical
v9 whole-file snapshots of controllers, entities, `pom.xml` and
`application.properties` were removed from the published scaffold; they were
bound to destination v9 baseline `06c51a49f4e6ff94c122f12929097e8cec3dc60e`
and are **not** a current recovery procedure. Recover those bytes from Git
history (table below), not by copying this directory onto a fresh run.
Decided controller/POM/property changes enter a fresh run as structural
transformations instead. Editing a file the manifest pins refuses the next
bootstrap (`REPAIR_CONTENT_DIGEST`) until the manifest, its review record and
`decisions.yaml` are updated together.

Workers never write test sources; that prohibition is enforced at the
pre-tool-call hook and is not relaxed by anything here.

A subdirectory may carry a `MANIFEST.md` beside its files when one Operator
step applies several of them together: what each file implements, what it
derives from, and the exact verification the step must run.
`spring-petclinic-rest/MANIFEST.md` is historical v9 ADR-014 evidence, not a
current recovery procedure.

## Current digest-bound payloads (keep in the published scaffold)

| specimen | path | ADR |
|---|---|---|
| spring-petclinic-rest | `src/test/java/org/springframework/samples/petclinic/model/ValidatorTests.java` | ADR-008 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/SecurityMode.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/SourceBasicAuthenticationMechanism.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/HttpSecuritySwitch.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/DisabledAccountAugmentor.java` | ADR-014 |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/security/PrefixedPlainTextPasswordProvider.java` | ADR-014 |

## Historical v9 whole-file snapshots (removed from the published scaffold)

These paths are Git-history provenance only. They are not present in the
published scaffold and must not be copied onto a fresh run. Added in
`ca3160b776464959671c830a4bce036a32ee1008`. Last recorded scaffold bytes are
the commit in the last-content column.

| specimen | historical path | last-content commit |
|---|---|---|
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/model/User.java` | `fa411a5f9ba7076cfce4e302c5f279154443704e` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/model/Role.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `pom.xml` | `ca3160b776464959671c830a4bce036a32ee1008` |
| spring-petclinic-rest | `src/main/resources/application.properties` | `fa411a5f9ba7076cfce4e302c5f279154443704e` |

The ADR-014 rows were one Operator step, bound to destination v9
(`06c51a49f4e6ff94c122f12929097e8cec3dc60e`). `decided-repairs/spring-petclinic-rest/manifest.json`
records that application history. `spring-petclinic-rest/MANIFEST.md` holds
the historical clause map, baseline, verification and prerequisites.
