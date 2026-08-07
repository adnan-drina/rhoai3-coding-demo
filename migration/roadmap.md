# Modernization roadmap

<!-- O-M2COMPOSE-SKELETON -->
# O-M2COMPOSE — mechanical partition / kind / deploy / seat-budget / K3 rows.
# Model fills JUDGMENT (rationale, quotes, adopt/defer reasons, §7 contracts;
# may refine kind with mixed justification).
# O-DEPCHAIN: depends are real inter-story edges (not forced S_n ← S_n-1).

## S01: Domain model foundation
- scope: src/main/java/com/demo/model/Bar.java
- findings: demo-entity-00001, springboot-parent-pom-to-quarkus-00000
- depends: -
- deploy: false
- done: <!-- JUDGMENT: checkable done-criterion -->
- rationale: ADR-34 model.stories[] id=S01 slug=domain-model layer=model units=1 roles HARVEST=1 REDESIGN=0 (F-story-rendered out-half; staging scope supplement only)
- kind: rename
- seat-budget: 1

## S02: REST surface and configuration
- scope: src/main/java/com/demo/rest/Foo.java
- findings: -
- depends: -
- deploy: true
- done: <!-- JUDGMENT: checkable done-criterion -->
- rationale: ADR-34 model.stories[] id=S02 slug=rest-surface layer=surface units=1 roles HARVEST=0 REDESIGN=1 (F-story-rendered out-half; staging scope supplement only)
- kind: reimplement
- seat-budget: 5

## Non-mandatory decisions

- (none)
