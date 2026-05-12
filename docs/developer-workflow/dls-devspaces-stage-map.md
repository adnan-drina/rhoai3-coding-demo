# dls-devspaces Stage Map

## Source

The user-provided repository URL, <https://github.com/sshaaf/dls-devspaces>, currently redirects on GitHub to <https://github.com/rhpds/mca-devspaces>. The repository describes a Red Hat OpenShift Dev Spaces workspace for Developer Lightspeed for MTA.

The inspected repository contains:

- a `devfile.yaml` that creates an `MTA-workspace` DevWorkspace;
- a custom Dev Spaces image based on `quay.io/devfile/universal-developer-image:ubi9-latest`;
- preloaded Red Hat Java, Java Extension Pack, and MTA VS Code extension VSIX files;
- Che Code editor configuration under `config/che-editor`;
- Developer Lightspeed for MTA provider settings under `config/dls/provider-settings.yaml`;
- a Coolstore project reference that points to `https://github.com/rhpds/mca-coolstore.git`;
- script and Ansible automation for creating a DevWorkspace or generating a Dev Spaces factory URL;
- a GitHub Actions workflow that builds and pushes the custom workspace image to Quay.

## Summary Assessment

This project is not a replacement for the `rhoai3-coding-demo` stage flow. It is a useful implementation reference for the developer-workspace and modernization portions of the story.

The strongest fit is:

- Stage 070: concrete Dev Spaces workspace packaging pattern;
- Stage 080: concrete Developer Lightspeed for MTA IDE setup pattern;
- Stage 160: concrete planned modernization workspace candidate for Coolstore-style exercises;
- Stage 155: supply-chain checkpoint for the custom workspace image and preloaded VSIX artifacts.

It does not directly address Continue, OpenCode, AgentOps, MCP Gateway security, Developer Hub catalog integration, Tekton pipeline generation, or Red Hat Trusted Software Supply Chain. Those remain responsibilities of the `rhoai3-coding-demo` planned stages.

## Stage Mapping

| Demo stage | Mapping | How to use it |
|------------|---------|---------------|
| Stage 070: Controlled Developer Workspaces | Strong fit. The repository packages a Dev Spaces workspace through a devfile, custom UDI image, Che Code editor configuration, and DevWorkspace creation automation. | Use as a reference when refining the MTA-enabled workspace variant for the `ai-developer` persona. Do not import it wholesale until we decide whether the demo should own its own workspace image. |
| Stage 080: AI-Assisted Application Modernization | Strong fit. The repository preloads MTA VS Code extensions and injects Developer Lightspeed for MTA provider settings at workspace startup. | Use as a concrete reference for the IDE side of the MTA and Developer Lightspeed workflow. Keep server-side MTA, LLM proxy, model policy, and MaaS routing in our stage flow. |
| Stage 100: Governed Developer Entry Point | Partial fit. The factory URL flow can become a Developer Hub launch link later. | Treat Dev Spaces factory URL generation as a candidate portal action after Developer Hub catalog entities exist. |
| Stage 110: Enterprise Vibe Coding With Continue | Weak fit. The repository focuses on MTA and Java tooling, not Continue. | No direct adoption. Keep Continue examples in our own workspace guide. |
| Stage 120: Quality Bar Breakpoint | Weak fit. The repository does not define AI output review gates. | Use only as infrastructure context. The quality-bar exercise still needs our own review rubric and eval cases. |
| Stage 130: Agentic Engineering With OpenCode | Weak fit. The repository does not include OpenCode rules, agents, or skills. | No direct adoption. It can be a future target workspace where OpenCode is added beside MTA tooling. |
| Stage 140: Golden Path Quarkus Service | Weak to partial fit. It targets Coolstore modernization, not a new Quarkus golden path. | Use only if we choose Coolstore as the bridge between modernization and Quarkus reference output. |
| Stage 150: Governed Pipeline And Deployment | Partial fit. The GitHub Actions workflow builds and pushes the workspace image, but it is not a Tekton or OpenShift Pipelines path. | Treat as a source pattern to translate into OpenShift Pipelines later, not as the demo delivery implementation. |
| Stage 155: Red Hat Trusted Software Supply Chain | Partial fit. The custom image and downloaded VSIX files introduce supply-chain evidence needs. | Use as a supply-chain example: custom workspace image, base image, extension artifacts, image signing, SBOM, provenance, Quay scanning, and promotion policy. |
| Stage 160: Modernization At Scale With MTA And Developer Lightspeed | Strong fit. The workspace is aimed at Developer Lightspeed for MTA and a Coolstore modernization project. | Use as a candidate starting point for the Stage 160 live exercise if we adopt `rhpds/mca-coolstore` as the modernization repository. |
| Stage 170: Agent Mesh Modernization Pattern | Weak fit. The repository is a single-workspace implementation, not a multi-harness agent mesh. | Mention only as the local developer workspace that a future modernization harness could target. |

## Useful Patterns To Carry Forward

### DevWorkspace As A First-Class Artifact

The repository creates a Kubernetes `DevWorkspace` from a devfile instead of relying on manual IDE setup. This fits the demo principle that workspaces should be reproducible and platform-owned.

### Custom Workspace Image

The `containerfile` preloads Java and MTA extensions into a UDI-based image. This is useful for demos because it reduces startup friction, but it creates supply-chain responsibilities:

- verify base image source;
- pin and review VSIX versions;
- generate SBOM and provenance for the custom image;
- sign the image;
- scan it in Quay or another approved registry;
- document who owns image rebuilds.

### Che Code Editor Policy

The `config/che-editor` files show how a workspace can control editor behavior, allowed extensions, trusted extension auth access, telemetry, and workspace trust prompts. This is directly relevant to Stage 070 because the developer experience should be reproducible and policy-aware.

### Developer Lightspeed Provider Settings

The `devfile.yaml` downloads `config/dls/provider-settings.yaml` into the MTA extension settings directory on workspace start. This is useful for Stage 080 and Stage 160, but the placeholders in that file still need to be wired to our MaaS model path and secret handling before the pattern is adopted.

### Factory URL And Automation Paths

The project supports both:

- Dev Spaces factory URL creation from a raw devfile URL;
- local DevWorkspace creation through a shell script or Ansible playbook.

For `rhoai3-coding-demo`, the factory URL is most relevant to Developer Hub in Stage 100. The script and Ansible paths are useful references for implementation, but our executable stage flow should continue to prefer GitOps-managed platform resources where possible.

## Adoption Recommendation

Use this repository as a reference implementation, not as a direct dependency in this branch.

Recommended next iteration:

1. Use `rhpds/mca-coolstore` as the recommended Stage 160 brownfield modernization source, based on the [`mca-coolstore` candidate assessment](mca-coolstore-candidate-assessment.md).
2. Decide whether our Stage 070 workspace image should absorb the MTA/Java VSIX preload pattern.
3. Translate the Developer Lightspeed provider settings to our MaaS model endpoint and secret-management model.
4. Add a supply-chain checklist for any custom workspace image before promoting it into the demo.
5. Add a Developer Hub launch link only after catalog entities and Dev Spaces URLs are implemented.

## Open Questions

- Should the demo keep `konveyor-ecosystem/coolstore` as a secondary reference for Quarkus comparison material after standardizing Stage 160 on `rhpds/mca-coolstore`?
- Should the MTA workspace be a separate DevWorkspace from the Continue/OpenCode coding workspace, or should one workspace include all tools?
- Should the custom workspace image be built by our own pipeline so Stage 155 can capture SBOM, signing, provenance, and scan evidence?
- Should Developer Lightspeed provider settings be injected by workspace startup, a Secret, a ConfigMap, or the MTA server-side LLM proxy path?

## References

- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [sshaaf/dls-devspaces redirect](https://github.com/sshaaf/dls-devspaces)
- [Developer Lightspeed for MTA](https://developers.redhat.com/products/mta/developer-lightspeed)
- [Editor configurations for Microsoft Visual Studio Code in Eclipse Che](https://eclipse.dev/che/docs/stable/administration-guide/editor-configurations-for-microsoft-visual-studio-code/)
