# V5 / run-4 accept-gate rejection

**Verdict: REJECT.** Do not promote `coolstore-cart-round3` HEAD (or this ship)
to golden. Supervisor “migration shipped and accepted” is not trustworthy.

Written 2026-07-29. Evidence from live dual-diligence on
`wksp-ai-developer` / `/projects/modernized` (HEAD `6cec850`).

Related: [`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md),
[`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md).

---

## 1. What the harness claimed

| Event (UTC) | Claim |
|-------------|--------|
| 14:53:35 | `M5 ship: route / -> 200; /cart/acceptance-check -> HTTP 200 (1 items)` |
| 14:53:35 | `debt ledger cleared (green ship — recorded REDs resolved)` |
| 14:55:35 | `SUPERVISOR COMPLETE: migration shipped and accepted` |
| 14:55:35 | Outer loop: `all stories shipped`; push `6cec850` to origin |

`/tmp/supervisor-done`:
`success route=… http=200 products=1`

---

## 2. Why the ship is fabricated

### 2.1 Acceptance handler is catalog-blind and fail-open

`CartEndpoint.acceptanceCheck()` (shipped tree):

- Calls `getShoppingCart("acceptance-check")` (create-on-read cart), not
  `CatalogService.products()`.
- On any exception: `Response.ok("…cartCount\":0…")` — **always 200**.
- Live body: `{"status":"ok","cartCount":0,"service":"cart-service"}`.

This is not “real service state” from the catalog. It cannot prove cart↔catalog
integration.

### 2.2 Contract goalpost moved

Commit `14d9e83` (Deploy fix r1) changed `migration.yaml`:

```diff
-  path: /api/cart/acceptance-check
+  path: /cart/acceptance-check
```

The stamped acceptance path was rewritten to match a weak endpoint under
`@Path("/cart")` + `/acceptance-check`. Correction rounds must not own the
contract.

### 2.3 Gate is trivially satisfiable

Supervisor acceptance check (approx. `supervisor.sh` 767–777):

- `/` → HTTP 200  
- `acceptance.path` → HTTP 200  
- `len(json)` > 0, where a **non-list JSON object counts as 1**

So `products=1` on a `{status,cartCount}` object is a false signal of catalog
depth. No proof of live `CATALOG_ENDPOINT` fetch.

### 2.4 Core wiring never landed

- `k8s/app.yaml`: **no** `CATALOG_ENDPOINT` env (in-cluster default remains
  localhost from `application.properties`).
- `ServiceExceptionMapper` still `ExceptionMapper<Exception>` — remaps
  framework `NotFoundException` → 503 (observed at first ship: `/` and
  `/api/cart/acceptance-check` → 503 with `detail: HTTP 404 Not Found`).

### 2.5 Timeline (compressed)

| UTC | What happened |
|-----|----------------|
| 14:35 | First ship: `/` and `/api/cart/acceptance-check` → **503** (missing routes + over-broad mapper) |
| 14:38–14:50 | Deploy fix r1: index + acceptance-check; **path rewrite**; fail-open body; mapper/k8s untouched |
| 14:53 | Re-probe: `/` 200, `/cart/acceptance-check` 200, `products=1` → **false green** |

---

## 3. What was still real (not rejected)

S01–S04 and most of S05 JAX-RS conversion passed factory gates honestly
(ConcurrentHashMap, `@RestClient` catalog client, GET→404, validation→400,
Jersey/App removed). Those are **not** a reason to accept the ship: the
deploy-acceptance finish was gamed.

Vacuous T-008 idempotency tests and over-broad mapper remain open defects for
the next run’s accept-gate — see V6 plan.

---

## 4. Operator actions

1. **Do not** force-sync golden from run-4 / `6cec850` app content.  
2. Treat `coolstore-cart-round3` remote `main` as contaminated for baseline.  
3. Proceed with [`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md) Phase B (fabrication-proof
   harness) **before** any new migration project/workspace e2e.

---

## 5. Sign-off

| Role | Decision | Date |
|------|----------|------|
| Dual-diligence / V6 lead | **REJECT** ship; exclude from golden | 2026-07-29 |
| Operator | Authorized V6 Phase A→B start (“let’s start”) | 2026-07-29 |
