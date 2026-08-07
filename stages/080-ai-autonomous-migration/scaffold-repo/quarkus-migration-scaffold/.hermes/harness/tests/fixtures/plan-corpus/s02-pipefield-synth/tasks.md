# Tasks
UI surface: waived (API-only).

#### T-001: Harvest Foo model
|**Class**: rewrite
|**Shape**: create
|**Port**: rename
|**Owns**: src/main/java/com/demo/Foo.java
|**Oracle**: absent
|**Findings**: removed-javaee-modules-00020
|**Goal**: harvest Foo into target package
|**Target design**:
- → `src/main/java/com/demo/Foo.java`
|**Acceptance**: Foo.java exists under com.demo

#### T-002: Characterize Foo (O-PLANCOVERGATE)
|**Class**: infer
|**Shape**: create
|**Port**: rename
|**Owns**: src/test/java/com/demo/FooTest.java
|**Oracle**: absent
|**Goal**: characterization so ship coverage gate can pass
|**Acceptance**: FooTest pins layer contract for ship coverage
