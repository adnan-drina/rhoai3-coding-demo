# Kilo Code Prompts for Demo

Target application: `coolstore-inventory-service` (the stage 060 catalog
entry point — the developer opens it in Dev Spaces from the component page).

## Module 0: First interaction — prove the governed model path

**Prompt (default Nemotron model, right after opening the Kilo Code panel):**

> Look at src/main/java/com/redhat/coolstore/inventory/InventoryResource.java
> and summarize each REST endpoint this service exposes in one line each.

**Expected output:** three one-liners — list all items, item by `itemId`,
availability by `itemId`. A code-grounded question beats a plain "hello":
the answer is verifiable against the source, and a streamed response proves
the whole chain (workspace → MaaS gateway → local GPU) before the audience
invests in the big generation prompt.

---

## Module 1: Generate code with intentional smells

**Prompt (Act mode in Kilo Code — select a governed model from the four-provider picker: Nemotron default, local Qwen, qwen3-235b 16K-context, or minimax-m2 196K-context):**

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

**Model picker beat:** before running the prompt, briefly show the model
picker in Kilo Code. Four governed models are available — two local (Nemotron,
Qwen) and two external (qwen3-235b, minimax-m2 with 196K context). All four
route through the same MaaS gateway with the same API key; the developer
chooses by task, not by credential.

Verify with hot reload: `curl localhost:8080/api/inventory/stats` answers
immediately — Quarkus dev mode picks the new class up without a restart.

---

## Module 2: Fix code smells after SonarQube failure

**Prompt (Act mode in Kilo Code after the coolstore-dev pipeline's gate fails):**

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

**Talk track note:** the fix loop stays in Kilo Code at this stage — one-shot
in, gate out. Stage 070 is where the agent (OpenCode + skills) internalizes
the standards so the smells never ship in the first place.
