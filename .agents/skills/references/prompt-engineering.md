# Prompt Engineering Reference

## Active Prompt Surfaces

The vendored UI has two prompt surfaces:

- The system prompt is user-editable in the chat page sidebar
  (`config.system_prompt`); there is no repo-pinned system prompt file.
- Direct mode wraps retrieval context in `build_rag_messages`
  (`page/playground/direct.py`):

```text
Please answer the following query using the context below. When your answer
draws on the context, name the source guide(s) it came from, e.g.
(Source: Working with AutoRAG).

CONTEXT:
[Source: <Guide Title> (topic: <topic>)]: <chunk text>
...

QUERY:
...
```

Keep the citation instruction aligned with the sources panel: the panel is
the deterministic attribution surface; the inline "(Source: ...)" naming is
best-effort model behavior on top of it.

## Private Model Traits To Revalidate

These traits came from earlier private-model (Nemotron) testing and should be
revalidated when changing prompts or agent/tool paths:

| Trait | Impact | Mitigation |
|-------|--------|------------|
| Ignores negative instructions | Negative prompts can be repeated or ignored | Prefer positive commands |
| Verbose prompts cause narration | Long prompts can make the model explain the task | Keep prompts short and direct |
| Single-tool preference | Too many tools can produce wrong calls | Scope MCP tool selection per question |
| Needs explicit tool hints | Tool names may not be discovered reliably | Name the tool family in the question ("use the openshift tools ...") |
| Retry on failure works | Short retry prompts can help tool flows | Use concise retry instruction only |

## RAG Guidelines

- Keep the system prompt short; the context wrapper already carries the
  citation instruction.
- Keep `top_k` bounded (sidebar slider; default 5) — every retrieved chunk
  lands in the prompt in Direct mode.
- Ask for source-guide names, but do not claim chunk-level citation
  precision; the sources panel carries the verifiable attribution.
- If retrieval returns nothing, prefer a clear "not enough private context"
  answer over a general-knowledge answer.

## Agent/MCP Guidelines

- Use positive action commands such as "Use the openshift tools to list the
  pods in the rhoai-mcp namespace."
- Keep questions bounded to what the read-only MCP server allows
  (namespace-scoped pod listing, known-pod status, node usage); the server
  denies Secrets, ConfigMaps, RBAC objects, and cluster-wide listings.
- Keep temperature low, typically `0.1` to `0.3`.
- A model-driven tool-use claim requires `mcp_list_tools`, `mcp_call`, and a
  final `message` in the Responses output; plain text is not proof.
- Budget context for file-search and MCP output before increasing completion
  tokens.
