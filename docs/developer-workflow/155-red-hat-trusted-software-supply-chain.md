# Stage 155: Red Hat Trusted Software Supply Chain

## Why This Matters

Agentic engineering cannot stop at generated source code or pipeline YAML. Enterprise teams also need evidence that the code, container images, AI artifacts, MCP servers, skills, and agent workloads moving through the pipeline came from trusted sources, were built through approved processes, and can be verified before deployment.

This planned stage extends Stage 150 from governed delivery into supply-chain evidence. The developer still works through the golden path, but the pipeline now captures the proof that the output is trustworthy enough to promote.

## Story Goal

Show how Red Hat Trusted Software Supply Chain concepts apply to AI-assisted development. The developer should see where SBOMs, provenance, signatures, vulnerability analysis, image scanning, registry policy, and deployment gates fit in the path from AI-assisted change to trusted runtime.

## Platform Capabilities Consumed

- Stage 090 provides Developer Hub as the future self-service and catalog surface.
- Stage 130 provides OpenCode agents, project rules, and review workflows.
- Stage 140 provides the demo-owned Coolstore Inventory Quarkus service target described in the [`Quarkus target service options`](quarkus-target-service-options.md) assessment.
- Stage 150 provides the pipeline and GitOps handoff pattern.

## What This Stage Adds

This planned stage adds the trusted software supply-chain checkpoint for the developer workflow.

- A supply-chain evidence model for AI-assisted code changes.
- SBOM and VEX review expectations.
- Artifact signing and provenance requirements.
- Image registry and scanning expectations.
- Policy gates before deployment or promotion.
- Extension points for models, MCP servers, skills, and agent containers.
- A Scribe MCP server supply-chain checkpoint if Scribe becomes a shared modernization tool.

## Developer Workflow

### Starting Point

The developer has a reviewed `coolstore-inventory-service` implementation from Stage 140 and a governed pipeline plan from Stage 150. The implementation has not yet been treated as promotable. The next step is to identify which supply-chain evidence must exist before the service image, pipeline, or related AI artifacts can move forward.

### AI-Assisted Task

Ask the agent to produce a supply-chain evidence plan for the service and any AI-specific artifacts introduced by the workflow. The task is review-oriented first. The agent should map required controls to existing or future pipeline steps rather than inventing unsupported tools.

The plan should cover:

- application dependency and container inventory for the Coolstore Inventory service;
- SBOM and VEX handling;
- artifact signature and verification points;
- provenance and SLSA-aligned build evidence;
- image storage and scanning;
- deployment policy gates;
- the single-repository evidence model in the renamed `coolstore-inventory-service` repo, including source evidence, pipeline evidence, app-local GitOps state, promotion notes, rollout notes, and rollback evidence;
- treatment of MCP servers, skills, model artifacts, and agent containers if they become shared platform assets.
- treatment of Scribe as a custom Quarkus MCP server image if it is deployed outside an individual workspace.

### Prompts Or Agent Instructions

Recommended planning instruction:

```text
Review the service and pipeline plan and identify the trusted software supply-chain evidence required before promotion. Map each requirement to a pipeline step, artifact, registry, policy gate, or human review point. Do not add tools or manifests until the evidence model is reviewed.
```

Recommended review instruction:

```text
Check whether the proposed supply-chain path creates SBOMs, verifies provenance, signs artifacts, scans images, stores artifacts in an approved registry, and blocks unsigned or non-compliant deployments.
```

### Expected Developer Actions

- Review the supply-chain evidence plan before implementation.
- Confirm which tools are available in the live environment.
- Confirm which artifacts are in scope: application image, model artifact, MCP server, skill bundle, or agent image.
- Keep signing keys, registry credentials, and scan tokens out of git.
- Decide which checks are advisory in the first implementation and which checks should block promotion.
- Capture static evidence now and live evidence only after the platform components exist.

### Review And Quality Gates

- SBOM or dependency inventory is generated or explicitly deferred.
- Signature and provenance requirements are documented.
- Image registry and scanning path is documented.
- Deployment gates are tied to an approved policy engine or manual review until automation exists.
- No credentials or private registry tokens are committed.
- AI-generated supply-chain changes are reviewed by a human before use.

### Evidence To Capture

- Supply-chain evidence plan.
- Artifact list and ownership.
- SBOM or planned SBOM location.
- Signature and provenance strategy.
- Image registry and scan result location.
- Policy gate decision: advisory, blocking, or deferred.
- Human approval notes.

## What To Notice And Why It Matters

The proof point is that AI-assisted development can produce auditable evidence, not only code. A generated service is still untrusted until the pipeline can show where it came from, what it contains, who or what built it, whether it was signed, where it was stored, and which policies allowed it to run.

This matters more in agentic workflows because the artifact set expands. The enterprise may eventually need to govern application images, model containers, MCP servers, reusable skills, and long-running agent workloads with the same discipline.

## How Red Hat And Open Source Make It Work

Red Hat Trusted Software Supply Chain combines developer self-service, artifact signing, dependency analysis, registry controls, and runtime policy enforcement. Red Hat Developer Hub can expose trusted templates and workflow guidance. Red Hat Trusted Artifact Signer provides signing and verification using Sigstore-based patterns. Red Hat Trusted Profile Analyzer manages SBOM and vulnerability context. Red Hat Quay stores and scans images. Red Hat Advanced Cluster Security can enforce Kubernetes deployment policy.

Open source projects provide the building blocks: Sigstore, Rekor, Cosign, Tekton Chains, in-toto, SLSA, and OCI registries. For AI workloads, the same pattern can extend to ModelCar containers, MCP server containers, skill artifacts, and agent images.

## Trust Boundaries

Supply-chain evidence is a trust boundary. A model endpoint, coding agent, or generated pipeline does not make an artifact trustworthy by itself. The artifact must be traceable to reviewed source, built by an approved process, stored in an approved registry, signed or otherwise verifiable, and checked by policy before promotion.

## Red Hat Products Used

- **[Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)** provides the product framing for trusted code, build, deploy, and monitor workflows.
- **[Red Hat Trusted Artifact Signer](https://developers.redhat.com/products/trusted-artifact-signer)** provides artifact signing, verification, and provenance metadata.
- **[Red Hat Trusted Profile Analyzer](https://developers.redhat.com/products/trusted-profile-analyzer)** provides SBOM, VEX, vulnerability, and dependency risk analysis.
- **[Red Hat Quay](https://www.redhat.com/en/technologies/cloud-computing/quay)** provides image storage and scanning.
- **[Red Hat Advanced Cluster Security for Kubernetes](https://www.redhat.com/en/technologies/cloud-computing/openshift/advanced-cluster-security-kubernetes)** provides policy enforcement and runtime security.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides template and catalog surfaces for developer self-service.

## Open Source Projects To Know

- [Sigstore](https://www.sigstore.dev/) provides signing and verification patterns for software artifacts.
- [Cosign](https://docs.sigstore.dev/cosign/overview/) signs and verifies container images and other artifacts.
- [Rekor](https://docs.sigstore.dev/rekor/overview/) provides a transparency log.
- [Tekton Chains](https://tekton.dev/docs/chains/) captures provenance from Tekton pipelines.
- [SLSA](https://slsa.dev/) defines supply-chain integrity levels.
- [in-toto](https://in-toto.io/) provides a framework for supply-chain metadata and attestations.

## Future Implementation Notes

- Decide whether this stage remains a documentation checkpoint or becomes an executable stage with Trusted Software Supply Chain components.
- Treat the first artifact scope as the Coolstore Inventory Quarkus service image. Decide later whether to add one AI artifact, such as the Scribe MCP server image or a packaged agent runtime, to the same evidence bundle.
- Define the minimum evidence bundle for the demo: SBOM, signature, provenance, scan result, and policy decision.
- Decide whether Red Hat Trusted Artifact Signer and Red Hat Trusted Profile Analyzer are deployed in the demo environment or referenced as enterprise controls.
- Add pipeline examples only after the chosen Tekton or OpenShift Pipelines template is selected.
- Add policy-gate examples only after the target enforcement tool is selected.
- If the demo adopts the `rhpds/mca-devspaces` custom workspace image pattern, include the workspace image, base image, downloaded VSIX artifacts, and Quay promotion path in the supply-chain evidence bundle.
- If the demo adopts the `sshaaf/scribe` MCP server, include its Quarkus application image, UBI OpenJDK base image, Maven dependencies, generated SBOM, signature, provenance, scan result, and MCP Gateway exposure policy in the evidence bundle.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)
- [Strengthen security in your software supply chain](https://www.redhat.com/en/solutions/trusted-software-supply-chain)
- [Red Hat Trusted Software Supply Chain is now available](https://developers.redhat.com/articles/2024/04/18/red-hat-trusted-software-supply-chain-now-available)
- [Red Hat Trusted Artifact Signer](https://developers.redhat.com/products/trusted-artifact-signer)
- [Red Hat Trusted Profile Analyzer](https://developers.redhat.com/products/trusted-profile-analyzer)
- [Using containers to bring software engineering rigor to AI workloads](https://www.redhat.com/en/blog/using-containers-bring-software-engineering-rigor-ai-workloads)
- [Build more secure, optimized AI supply chains with Fromager](https://developers.redhat.com/articles/2026/04/13/build-more-secure-optimized-ai-supply-chains-fromager)
- [Quarkus target service options](quarkus-target-service-options.md)
- [coding-exercises application repository plan](coding-exercises-app-repo-plan.md)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)

## Next Stage

[Stage 160: Modernization At Scale With MTA And Developer Lightspeed](160-modernization-at-scale-with-mta-and-developer-lightspeed.md) shifts from trusted delivery of one application to brownfield modernization at application-portfolio scale.
