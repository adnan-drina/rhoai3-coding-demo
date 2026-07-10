# Continue Plugin Prompts for Demo

## Module 1: Generate code with intentional smells

**Prompt (one-shot to Continue):**

> Create a new JAX-RS endpoint at /api/claims/stats that returns claim statistics
> including total count, breakdown by category, and breakdown by status.
> Inject ClaimsResource and use its getAllClaims() method.
> Return a Map<String, Object> as JSON.

**Expected output:** The code in `ClaimsStatsResource-with-smells.java` — the model
will likely produce code with System.out.println and possibly an empty catch block.
If it produces clean code, manually add the code smells to set up the pipeline failure.

**Alternative (copy-paste approach):** If the model produces clean code, use the
pre-prepared version from `ClaimsStatsResource-with-smells.java` and explain to the
audience that "for demo purposes, our developer took some shortcuts."

---

## Module 2: Fix code smells after SonarQube failure (Stage 080)

**Tool: OpenCode (not Continue) — by Stage 080 the audience has seen agentic tools**

Using OpenCode reinforces the maturity ladder ("we don't go back down the rungs").

**Prompt (to OpenCode in the terminal after pipeline fails):**

> The pipeline's SonarQube gate failed on ClaimsStatsResource.java. It found
> System.out.println usage, field injection, and an empty catch block. Fix all
> three issues following project conventions. Use Logger for output, constructor
> injection, and proper error logging in the catch block.

**Expected fixes:**
1. `System.out.println` → `Logger.info()` (using `org.jboss.logging.Logger`)
2. `@Inject` field injection → constructor injection
3. Empty `catch (Exception e) {}` → `LOG.error("...", e)`

**Reference:** See `ClaimsStatsResource-fixed.java` for the expected result.

**Talk track note:** "By Stage 080 the developer has OpenCode and project
skills. They don't go back to one-shot prompting — the agent understands the
project's coding standards and applies the fix in context."
