# V6 acceptance gate design freeze

Frozen 2026-07-29 for Phase B implementation. Authority:
[`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md) P0 / Phase B.

**Goal:** a correction round cannot fabricate a green ship the way run-4 did.

**Non-goals:** OpenRewrite; Spring compat; changing factory Sonar bars;
digest-pin / path-filter (Phase F).

---

## Rules (R1–R7)

| ID | Rule | Enforcement locus | Run-4 failure mode |
|----|------|-------------------|--------------------|
| **R1** | `migration.yaml` `acceptance.path` is **immutable** after template stamp (no correction/deploy session may change it) | Sensor on git diff / supervisor reject if path changes in deployfix commits | `14d9e83`: `/api/cart/...` → `/cart/...` |
| **R2** | Acceptance HTTP body must prove a **live catalog fetch** | Supervisor probe + SHIPPING contract | Handler never called `CatalogService` |
| **R3** | **No fail-open** on the acceptance handler: `catch` → `Response.ok(...)` (or always-200 empty) is forbidden | Static/preflight sensor | `catch (Exception e) { return Response.ok(...cartCount:0) }` |
| **R4** | Gate success requires HTTP 200 **and** a JSON **array** of products with `length > 0` (or top-level object with `products` array length > 0). A bare object must **not** count as 1 item | `supervisor.sh` acceptance probe | `products=1` on `{status,cartCount}` |
| **R5** | For `deploy=true` stories: `CATALOG_ENDPOINT` must be present under `k8s/` Deployment `env` before ship success | `preserved_integrations` / preflight when deploy; SHIPPING correction checklist | Props-only “ALREADY COMPLETE”; no k8s env |
| **R6** | `ServiceExceptionMapper` must **not** implement `ExceptionMapper<Exception>`; must not remap `NotFoundException` → 503. Catalog/service failures only | Static sensor + SHIPPING mandatory correction item | 404 masked as 503 on first ship |
| **R7** | plan-lint must see `acceptance.path` even when comments sit between `acceptance:` and `path:`; deploy stories must **task** that exact path (substance: Java `@Path` / resource) | `plan-lint.py` + instruments; optional static “handler exists” before push | S05 `PLAN OK` with path untasked (comment bypass) |

---

## R2 / R4 — concrete probe semantics

**Pass** when all hold:

1. `GET /` → 200 (minimal index; unchanged).  
2. `GET {acceptance.path}` → 200.  
3. Parsed JSON is either:  
   - a **JSON array** with `len >= 1`, each element looking like a product object, **or**  
   - a JSON object with a `products` key that is an array with `len >= 1`.  
4. (Preferred, if cheap) array length matches a direct curl to the configured
   catalog `/api/products` within tolerance — optional v1; **minimum v1 is
   non-empty products array from the app acceptance URL**.

**Fail** examples that must not pass:

- `{"status":"ok","cartCount":0}`  
- `{"status":"ok"}`  
- HTTP 200 with empty array `[]`  
- HTTP 503/404  

---

## R3 — fail-open patterns (v1)

Flag RED (static) if the file that serves `acceptance.path` contains a
catch-all that returns 200 OK with a constant/empty success body, e.g.:

- `catch (` … `Response.ok(` within the acceptance method (heuristic), or  
- documented forbid list in sensors aligned with SHIPPING.

Prefer precise AST later; v1 heuristic + SHIPPING text is enough to catch
run-4.

---

## R1 — path immutability

Compare `acceptance.path` at story start (or M5 evaluate) to path at ship.
If a deployfix / acceptance-correction commit changes that line → RED /
reject commit (same class as scope_enforce).

---

## R5 / R6 — correction checklist (SHIPPING.md)

Acceptance-correction session **must** before claiming done:

1. Ensure handler at **unchanged** `acceptance.path` returns catalog-backed
   products array.  
2. Set `CATALOG_ENDPOINT` in `k8s/` Deployment env to in-cluster catalog.  
3. Narrow mapper away from `ExceptionMapper<Exception>`.  
4. Preflight GREEN; do **not** edit `acceptance.path`.

Supervisor ship success additionally enforces R4/R5 mechanically.

---

## R7 — plan-lint

Parse `acceptance.path` with comment/blank tolerance, e.g. match:

```text
^acceptance:\s*\n(?:\s*#.*\n|\s*\n)*\s*path:\s*(\S+)
```

Instrument: scaffold-shaped `migration.yaml` (comment between keys) + tasks
without the path → `LINT:acceptance`.

---

## Blast radius

| Concern | Mitigation |
|---------|------------|
| Non-deploy stories | R4/R5 only when `STORY_DEPLOY=true` / ship acceptance path |
| Apps without catalog | Document N/A: preserve list empty or different acceptance shape — cart remains the proving app |
| Flaky catalog | Readiness wait (P4.2) before probe; empty catalog is a real fail |

---

## Implementation order

1. PR-B0 — R7 plan-lint + instrument — **done**  
2. PR-P0a — R4 (+ optional readiness) — **done**  
3. PR-P0b — R1, R3, R5, R6 sensors + SHIPPING — **done**  
4. PR-P0c — R7 task substance / handler-before-deploy — **done**  

**Exit:** `instruments.sh` GREEN (**89/89**); sync into next V6 project when provisioning.

---

## Sign-off

| Role | Status | Date |
|------|--------|------|
| V6 lead | Design frozen for implement | 2026-07-29 |
| Operator | Phase B authorized via “let’s start” | 2026-07-29 |
