# Continue Plugin Prompts for Demo

Target application: `coolstore-inventory-service` (the stage 060 catalog
entry point — the developer opens it in Dev Spaces from the component page).

## Module 1: Generate code with intentional smells

**Prompt (one-shot to Continue):**

> Create a new JAX-RS endpoint at /api/inventory/stats that returns inventory
> statistics including total item count, a breakdown by location, and
> in-stock vs out-of-stock counts. Inject InventoryRepository and use its
> list() method. Return a Map<String, Object> as JSON.

**Expected output:** The code in `InventoryStatsResource-with-smells.java` —
the model will likely produce code with System.out.println and possibly an
empty catch block. If it produces clean code, manually add the code smells to
set up the pipeline failure.

**Alternative (copy-paste approach):** If the model produces clean code, use
the pre-prepared version from `InventoryStatsResource-with-smells.java` and
explain to the audience that "for demo purposes, our developer took some
shortcuts."

Verify with hot reload: `curl localhost:8080/api/inventory/stats` answers
immediately — Quarkus dev mode picks the new class up without a restart.

---

## Module 2: Fix code smells after SonarQube failure

**Prompt (to Continue after the coolstore-dev pipeline's gate fails):**

> The pipeline's SonarQube gate failed on InventoryStatsResource.java. It
> found System.out.println usage, field injection, and an empty catch block.
> Fix all three issues following project conventions. Use Logger for output,
> constructor injection, and proper error logging in the catch block.

**Expected fixes:**
1. `System.out.println` → `Logger.info()` (using `org.jboss.logging.Logger`)
2. `@Inject` field injection → constructor injection
3. Empty `catch (Exception e) {}` → `LOG.error("...", e)`

**Reference:** See `InventoryStatsResource-fixed.java` for the expected
result.

**Talk track note:** the fix loop stays in Continue at this stage — one-shot
in, gate out. Stage 070 is where the agent (OpenCode + skills) internalizes
the standards so the smells never ship in the first place.
