# Stage 100 Validation

Stage 100 proves that the governed developer entry path works before any
AI-assisted code change begins.

## Green Bar

Stage 100 is green only when all of these checks pass:

- Developer Hub is reachable.
- The Coolstore system and both Coolstore components are visible in the catalog.
- Each Coolstore component shows only `Source Repo`, `Dev Spaces`, and
  `Getting Started`.
- The `Getting Started` link opens this TechDocs site.
- The `Dev Spaces` link opens the controlled workspace.
- The workspace contains `mca-coolstore` and `coolstore-inventory-service`.
- `~/.continue/config.yaml` is configured in the workspace only.
- `~/.opencode/opencode.json` is configured in the workspace only.
- Continue completes a harmless prompt against `nemotron-3-nano-30b-a3b`
  through MaaS.
- OpenCode completes a harmless prompt against `nemotron-3-nano-30b-a3b`
  through MaaS.
- No route hostnames, API keys, kubeconfigs, model tokens, or provider keys are
  committed as evidence.

## Safe Verification Prompt

Use the same harmless prompt for both clients:

```text
Reply with the configured model name and a one-sentence description of what data
boundary this model path represents. Do not include endpoint URLs, keys, or
source code.
```

Record only:

- the client name;
- the selected model ID;
- whether the prompt succeeded;
- the date of the check;
- any blocker that prevented completion.

## Stage 110 Handoff

Stage 110 can start only after Stage 100 has a working Developer Hub entry
point, a running Dev Spaces workspace, and verified MaaS connectivity from both
Continue and OpenCode.
