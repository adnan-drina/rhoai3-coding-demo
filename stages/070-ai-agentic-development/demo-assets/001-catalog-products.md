# Brief 001: Coolstore catalog — product listing

Paste this brief as the description for `/speckit.specify`. It is the Quarkus rebuild of the original coolstore `catalog-spring-boot` service — the spec captures observed behavior; the implementation is fresh.

## Goal

The Coolstore catalog service owns product information — what is for sale, what it costs, how it is described. It is a sibling of the existing `coolstore-inventory-service` (which owns stock levels) and uses the same `itemId` identifiers.

## Behavior

**The API base path is exactly `/api/catalog`** — named for the service (as `coolstore-inventory-service` exposes `/api/inventory`). Do **not** derive the path from the `Product` entity as `/api/products`; the resource is `@Path("catalog")`.

1. `GET /api/catalog` returns the full product list as a JSON array.
2. Each product has exactly: `itemId` (string), `name` (string), `description` (string), `price` (number, two-decimal currency).
3. `GET /api/catalog/{itemId}` returns a single product, or 404 with an RFC-7807-style body when the itemId is unknown.
4. Products live in an in-memory repository seeded at startup (no database). Seed with **exactly** these itemIds, names, and prices — they are the contract, not examples. Do not round, substitute, or invent values:

| itemId | name | price |
|--------|------|-------|
| 100000 | Red Fedora | 34.99 |
| 329299 | Quarkus T-shirt | 10.00 |
| 329199 | Pronounced Kubernetes | 9.00 |
| 165613 | Knit socks | 4.15 |

   (The `description` is the only field you may author freely — a short one-sentence marketing line per product. `329299`, `329199`, and `165613` deliberately match the inventory service's seed itemIds, so a later availability spec can join catalog and stock on the same key.)

## Non-goals

Persistence, create/update/delete, authentication, pagination, and any inventory/stock information (that arrives in a later spec).

## Acceptance

- `mvn -q test` passes; tests cover the list endpoint, the single-item endpoint, and the 404 path, using the project's test standards (RestAssured, given/when/then).
- `GET /api/catalog` returns all four seed products.
- `GET /api/catalog/329299` returns the Quarkus T-shirt at price `10.00` (spot-check that both the `/api/catalog/{itemId}` path and the seed values are faithful to this brief — not `/api/products`, not a substituted price).
- Code follows the project's REST conventions skill: constructor injection, proper logging, no `System.out`.
