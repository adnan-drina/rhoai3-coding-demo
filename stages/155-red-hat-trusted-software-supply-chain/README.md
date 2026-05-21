# Stage 155: Red Hat Trusted Software Supply Chain

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Agentic engineering cannot stop at generated source or pipeline YAML. Enterprise teams also need evidence that code, container images, MCP servers, skills, and agent artifacts came from trusted sources, were built through approved processes, and can be verified before deployment.

Stage 155 extends the governed delivery path from Stage 150 into supply-chain evidence.

## What This Stage Adds

This planned stage adds a supply-chain evidence checkpoint.

- SBOM and VEX planning.
- Artifact signing and verification points.
- Provenance and SLSA-aligned build evidence.
- Image storage and scanning expectations.
- Policy-gate decisions.
- A single-repository evidence model for `coolstore-inventory-service`.
- Future treatment of MCP servers, skills, model artifacts, and agent containers if they become shared platform assets.

## Platform Capabilities Consumed

- Stage 090 provides Developer Hub as the future catalog and self-service surface.
- Stage 130 provides OpenCode agents, project rules, and review workflows.
- Stage 140 provides the service target.
- Stage 150 provides the `.tekton/` Pipelines-as-Code and app-local GitOps handoff pattern.

## Developer Workflow

The developer has a reviewed service implementation and delivery plan. The next task is to identify which supply-chain evidence must exist before a service image, pipeline, MCP server, skill bundle, or related AI artifact can move forward.

The first evidence scope is the Coolstore Inventory service image. The plan should map controls to pipeline steps, artifacts, registries, policy gates, or human review points rather than inventing unsupported tools.

## Starter Prompts

```text
Review the service and pipeline plan and identify the trusted software supply-chain evidence required before promotion. Map each requirement to a pipeline step, artifact, registry, policy gate, or human review point. Do not add tools or manifests until the evidence model is reviewed.
```

```text
Check whether the proposed supply-chain path creates SBOMs, verifies provenance, signs artifacts, scans images, stores artifacts in an approved registry, and blocks unsigned or non-compliant deployments.
```

## What To Notice And Why It Matters

The proof point is that AI-assisted development can produce auditable evidence, not only code. A generated service is still untrusted until the pipeline can show what was built, where it came from, who or what built it, whether it was signed, where it was stored, and which policy allowed it to run.

This matters more in agentic workflows because the artifact set expands from application images to model containers, MCP servers, skill bundles, and agent images.

## How Red Hat And Open Source Make It Work

Red Hat Trusted Software Supply Chain combines developer self-service, artifact signing, dependency analysis, registry controls, and runtime policy enforcement. Red Hat Trusted Artifact Signer provides signing and verification patterns. Red Hat Trusted Profile Analyzer manages SBOM, VEX, and vulnerability context. Red Hat Quay stores and scans images. Red Hat Advanced Cluster Security can enforce Kubernetes deployment policy.

Open source projects provide the building blocks: Sigstore, Rekor, Cosign, Tekton Chains, in-toto, SLSA, and OCI registries.

## Red Hat Products Used

- **[Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)** provides the product framing for trusted code, build, deploy, and monitor workflows.
- **[Red Hat Trusted Artifact Signer](https://developers.redhat.com/products/trusted-artifact-signer)** provides artifact signing, verification, and provenance metadata.
- **[Red Hat Trusted Profile Analyzer](https://developers.redhat.com/products/trusted-profile-analyzer)** provides SBOM, VEX, vulnerability, and dependency risk analysis.
- **[Red Hat Quay](https://www.redhat.com/en/technologies/cloud-computing/quay)** provides image storage and scanning.
- **[Red Hat Advanced Cluster Security for Kubernetes](https://www.redhat.com/en/technologies/cloud-computing/openshift/advanced-cluster-security-kubernetes)** provides policy enforcement and runtime security.
- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides template and catalog surfaces for developer self-service.

## Open Source Projects To Know

- [Sigstore](https://www.sigstore.dev/) provides signing and verification patterns.
- [Cosign](https://docs.sigstore.dev/cosign/overview/) signs and verifies container images and other artifacts.
- [Rekor](https://docs.sigstore.dev/rekor/overview/) provides a transparency log.
- [Tekton Chains](https://tekton.dev/docs/chains/) captures provenance from Tekton pipelines.
- [SLSA](https://slsa.dev/) defines supply-chain integrity levels.
- [in-toto](https://in-toto.io/) provides supply-chain metadata and attestations.

## TODOs

- TODO: Decide whether this stage remains a documentation checkpoint or becomes executable.
- TODO: Define the minimum evidence bundle: SBOM, signature, provenance, scan result, and policy decision.
- TODO: Decide whether Red Hat Trusted Artifact Signer and Red Hat Trusted Profile Analyzer are deployed in the demo or referenced as enterprise controls.
- TODO: Add policy-gate examples only after the enforcement tool is selected.
- TODO: Include workspace images, MCP server images, and skill bundles only after those artifacts exist.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)
- [Strengthen security in your software supply chain](https://www.redhat.com/en/solutions/trusted-software-supply-chain)
- [Red Hat Trusted Software Supply Chain is now available](https://developers.redhat.com/articles/2024/04/18/red-hat-trusted-software-supply-chain-now-available)
- [Red Hat Trusted Artifact Signer](https://developers.redhat.com/products/trusted-artifact-signer)
- [Red Hat Trusted Profile Analyzer](https://developers.redhat.com/products/trusted-profile-analyzer)
- [Using containers to bring software engineering rigor to AI workloads](https://www.redhat.com/en/blog/using-containers-bring-software-engineering-rigor-ai-workloads)
- [Build more secure, optimized AI supply chains with Fromager](https://developers.redhat.com/articles/2026/04/13/build-more-secure-optimized-ai-supply-chains-fromager)
- [Quarkus target service options](../140-golden-path-quarkus-service/quarkus-target-service-options.md)
- [coolstore-inventory-service application repository plan](../140-golden-path-quarkus-service/coolstore-inventory-service-app-repo-plan.md)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)

## Next Stage

[Stage 160: Modernization At Scale With MTA And Developer Lightspeed](../160-modernization-at-scale-with-mta-and-developer-lightspeed/README.md) shifts from trusted delivery of one application to brownfield modernization at portfolio scale.
