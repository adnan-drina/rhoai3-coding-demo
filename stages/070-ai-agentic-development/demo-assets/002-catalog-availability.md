# Brief 002: Coolstore catalog — availability from the inventory service

Paste this brief as the description for a second `/speckit.specify` run,
after spec 001 is implemented and green. It evolves the same service —
this is spec-anchored development in practice.

## Goal

Shoppers need to know whether a product is in stock. Stock levels are
owned by the platform's existing `coolstore-inventory-service`
(deployed in `coolstore-dev`; it exposes
`GET /api/inventory/{itemId}/availability` returning
`{itemId, available, quantity}`). The catalog enriches its products
with that availability instead of duplicating stock data.

## Behavior

1. `GET /api/catalog` and `GET /api/catalog/{itemId}` gain two fields
   per product: `available` (boolean) and `quantity` (integer), fetched
   from the inventory service by `itemId`.
2. The inventory base URL comes from configuration
   (`catalog.inventory.url`), so dev, test, and cluster deployments can
   point at different instances. Default for in-cluster:
   `http://coolstore-inventory-service.coolstore-dev.svc:8080`.
3. Graceful degradation: if the inventory call fails, times out
   (>2 seconds), or the itemId is unknown to inventory, the product is
   still returned with `available: false`, `quantity: 0`, and a WARNING
   is logged. The catalog never fails because inventory is down.
4. Inventory responses are fetched per request (no caching in this
   spec).

## Non-goals

Caching, circuit breakers, bulk endpoints on the inventory side, and
write operations.

## Acceptance

- `mvn -q test` passes without any live inventory service: tests mock
  the inventory client (WireMock or a CDI alternative) and cover the
  happy path, the unknown-item path, and the degradation path.
- With both services running on the cluster, catalog products whose
  itemIds exist in inventory show real quantities; `100000` (unknown to
  inventory) degrades gracefully.
- Configuration, logging, and injection style follow the project skills.
