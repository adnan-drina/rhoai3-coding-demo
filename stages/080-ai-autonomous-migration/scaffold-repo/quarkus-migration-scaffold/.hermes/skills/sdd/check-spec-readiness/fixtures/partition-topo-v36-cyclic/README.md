# v36 cyclic partition fixture (A2)

Reconstructed from dest-cite `143e7357` / register H1: `ClinicService` lived on
**foundational** and imported entity types owned by **US\*** children.

This is dest-read harvest shape, not a dest patch. `source` in
`evidence/briefs/partition.json` is `reconstructed-from-143e7357` until a live
dest copy of `evidence/briefs/partition.json` replaces it.

Must-refuse: `assert-partition-topological-order.py` on this tree.
Report-only: the same script `--report-only` over all 11 story cards.
Relocate: `relocate-descendant-import-writesets.py --write` moves the
facade onto polish; topological order then passes.

Live dest-read 2026-08-20 (petclinic-rest-v36-refac, harvest only, no dest
patch): 11 stories `setup, foundational, US1–US8, polish`. ClinicService
is on foundational. Foundational `dependencies[]` are Owner→US1 Pet→US2
PetType→US2 Specialty→US4 Vet→US5 Visit→US6. Dest also listed
ClinicService on US1–US6 write-sets (overlap). This fixture keeps the
foundational owner that creates the cycle **and** US1's overlapping claim
so relocate unique-owns the path onto polish (coverage does not refuse
serial non-pom overlap).
