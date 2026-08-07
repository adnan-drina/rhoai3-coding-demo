# Skill: LLM integration via MaaS

How this team adds LLM-powered features. The MaaS gateway is the only valid
model access point — never call a provider endpoint directly and never embed
API keys in code or config files.

## Wiring (Quarkus LangChain4j)

Add the dependency:

```xml
<dependency>
  <groupId>io.quarkiverse.langchain4j</groupId>
  <artifactId>quarkus-langchain4j-openai</artifactId>
</dependency>
```

Configure only through platform-injected environment variables:

```properties
quarkus.langchain4j.openai.base-url=${MAAS_API_BASE_URL}
quarkus.langchain4j.openai.api-key=${MAAS_API_KEY}
quarkus.langchain4j.openai.chat-model.model-name=${MAAS_MODEL_NAME}
quarkus.langchain4j.openai.chat-model.temperature=0.1
quarkus.langchain4j.openai.timeout=60s
```

## Patterns

- Define AI services as `@RegisterAiService` interfaces with explicit
  `@SystemMessage`/`@UserMessage`; ask for JSON-only responses and parse
  defensively (strip code fences and reasoning tags before parsing).
- Every LLM call sits behind a deterministic fallback: if the call fails or
  returns an invalid result, degrade to a non-LLM code path and log a
  WARNING with the cause. The feature must remain functional when MaaS
  throttles or a key is revoked.
- Validate LLM outputs against an allowlist before acting on them.
- Never log prompts or responses containing customer data at INFO level.
- Data classification: this application's data goes to the private model the
  platform routes via MaaS — model choice is a platform decision, not code.
