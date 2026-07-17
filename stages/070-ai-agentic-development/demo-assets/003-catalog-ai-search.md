# Brief 003 (optional): Coolstore catalog — AI product search via MaaS

Optional stretch spec for presenters with time. It gives the
`llm-integration` skill a purpose and lands the double-governance beat:
the application consumes the same governed MaaS gateway — same key
discipline, token limits, and usage telemetry — as the coding assistant
that built it.

## Goal

Shoppers describe what they want in natural language ("warm socks",
"something Red Hat themed under 20 bucks") and the catalog suggests
matching products, using the platform LLM with a deterministic fallback.

## Behavior

1. `POST /api/catalog/search` accepts `{ "query": string }` and returns
   `{ "query", "matches": [{itemId, name, reason}], "source" }`.
2. LLM-first via the MaaS gateway per the `llm-integration` skill: the
   model receives the query plus the product list (id, name,
   description, price) and returns matching itemIds with a one-line
   reason each. `source` is `llm`.
3. Fallback: if the LLM call fails, times out, or returns itemIds not in
   the catalog, fall back to case-insensitive substring matching on name
   and description; `source` is `fallback`; log a WARNING.
4. A blank query returns 400 with an RFC-7807-style body.
5. Model configuration (base URL, model name, key) comes from
   configuration/environment — never hardcoded.

## Non-goals

Embeddings or vector search, result ranking beyond the model's own
ordering, personalization, and conversation state.

## Acceptance

- `mvn -q test` passes without a live LLM: the fallback path and the
  request validation are tested with the LLM client mocked.
- With MaaS reachable, a query like "red hat fedora" returns `100000`
  with `source: llm`.
- Token usage for the service's calls is visible on the platform's
  usage dashboard under its own identity — governance beat verified.
