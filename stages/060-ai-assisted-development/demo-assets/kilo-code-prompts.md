# Kilo Code Prompts for Demo

Target application: `coolstore-inventory-service` (the stage 060 catalog entry point — the developer opens it in Dev Spaces from the component page).

## Module 1: Generate code with intentional smells

**Prompt (Act mode in Kilo Code — select a governed model from the four-provider picker: Qwen3.6 default, local Nemotron, qwen3-235b 16K-context, or minimax-m2 196K-context):**

> Create a new REST endpoint /api/inventory/stats in this Quarkus service that
> returns inventory statistics as JSON: total item count, a count per location,
> and how many items are in stock vs out of stock. Use the existing
> InventoryRepository to read the data and inject it directly into a field.
> Return a Map<String, Object>. Print each request and the computed values to
> the console so we can follow what is happening, and if anything goes wrong
> just catch the exception and return an empty map so the endpoint never
> breaks. Also add unit tests for the new endpoint in
> InventoryResourceTest.java, following the existing test style, so the
> change meets our coverage requirement.

**Why the prompt is flawed on purpose:** the smells are *instructed*, not hoped for — "print to the console" (System.out.println), "catch the exception and return an empty map" (swallowed errors), "inject it directly into a field" (field injection). A disciplined model implements the flawed spec faithfully, which makes the gate failure deterministic and the lesson honest: humans specify things vaguely or wrongly — the model is not the weakest link, the specification is. (Earlier drafts used a clean prompt and relied on a small model to produce smells by accident; Qwen3.6 one-shots clean code, so the accident never happens.)

**If the generated code somehow avoids the smells:** the instructions were softened by the model — tighten them ("you MUST print with System.out.println") and regenerate; the spec drives the smells, so no pre-prepared file is needed.

**Model picker beat:** before running the prompt, briefly show the model picker in Kilo Code. Four governed models are available — two local (Nemotron, Qwen) and two external (qwen3-235b, minimax-m2 with 196K context). All four route through the same MaaS gateway with the same API key; the developer chooses by task, not by credential.

Verify with hot reload: `curl localhost:8080/api/inventory/stats` answers immediately — Quarkus dev mode picks the new class up without a restart.

---

## Module 2: Fix code smells after SonarQube failure

**Prompt (Act mode in Kilo Code after the coolstore-dev pipeline's gate fails — build it from the actual report; the gate judges every touched file, so list ALL new issues):**

> The pipeline's SonarQube quality gate failed. The report lists these new
> issues:
> - Replace System.out by a proper logger (three occurrences in
>   InventoryResource.java)
> - Remove the @Inject field injection and use constructor injection instead
>   (InventoryResource.java)
> - Define a constant instead of duplicating the "http://redhat.com" literal
>   (InventoryRepository.java)
> Fix all of them following project conventions. Keep behavior unchanged and
> make sure the existing tests — including the stats endpoint tests — still
> pass.

**Coverage note:** the gate also requires 80% coverage on new code, which is why the Module 1 prompt asks for unit tests up front — the generation and its tests land together, so the red gate is about the smells, and the fix round is about the smells only.

**Presenter beat:** the third issue is pre-existing debt in InventoryRepository that surfaced because the AI touched that file — the gate reviews everything you change, not just what you meant to write.

**Expected fixes:**
1. `System.out.println` → `Logger.info()` (using `org.jboss.logging.Logger`)
2. `@Inject` field injection → constructor injection
3. The duplicated URL literal → a single constant in `InventoryRepository`

**Expected result:** `System.out.println` replaced by `org.jboss.logging.Logger` calls, the repository injected via constructor, and the catch block logging the error instead of hiding it.

**Talk track note:** the fix loop stays in Kilo Code at this stage — one-shot in, gate out. Stage 070 is where the agent (OpenCode + skills) internalizes the standards so the smells never ship in the first place.
