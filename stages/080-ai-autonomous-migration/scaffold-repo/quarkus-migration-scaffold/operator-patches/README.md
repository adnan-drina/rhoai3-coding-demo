# Operator patches (specimen-scoped, ADR-authorized)

Not harness code and not applied by any tool. Each subdirectory is one
specimen; each file mirrors its path in the destination product tree. An
Operator copies a file in, has it reviewed by a second seat, and records the
change with `fix-until-green/scripts/operator-step.py --operator ... --reviewer
... --adr ADR-nnn`, which re-measures the tree and refuses if the measure is
not fully known afterwards. A patch under `src/test/` refuses without a
reviewer distinct from the operator.

Workers never write test sources; that prohibition is enforced at the
pre-tool-call hook and is not relaxed by anything here.

| specimen | path | ADR |
|---|---|---|
| spring-petclinic-rest | `src/test/java/org/springframework/samples/petclinic/model/ValidatorTests.java` | ADR-008 |
