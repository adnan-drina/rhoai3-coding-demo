# Architecture profile (corpus fixture)

## Domain boundaries

Repository layer only — JDBC / Spring Data → Quarkus persistence.
Bounded context: data-access adapters; no REST surface in this story.
