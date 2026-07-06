# Stage 080: AI in Trusted Delivery

**Theme:** Trust for AI-generated software
**Concept:** After Stage 070's agents produce code, the Trusted Software Factory proves what was built and how — provenance, signatures, and SBOMs for AI-generated changes.

> **Status:** base setup. This stage currently installs the trusted-delivery
> operators through GitOps; the Securesign instance, Trusted Profile
> Analyzer, and the pipeline for the Stage 070 migrated application are the
> implementation phase tracked in [BACKLOG.md](../../BACKLOG.md).
> Anchor article: [Trusted software factory: Building trust in the agentic AI era](https://developers.redhat.com/articles/2026/05/13/trusted-software-factory-building-trust-agentic-ai-era).

## Why This Matters

Stages 050–070 progressively hand more of the software lifecycle to AI:
assisted edits, skill-guided tasks, autonomous multi-agent migration. Every
step multiplies output — and multiplies the question auditors and platform
teams ask: *who built this artifact, from what, and can we prove it?*

The Trusted Software Factory pattern answers with supply-chain evidence
rather than trust-me claims: tamper-proof SLSA provenance for the build
process, sigstore-based signatures and attestations, software bills of
materials, and vulnerability intelligence that separates real exploitability
from noise. Applied to this demo: the Quarkus service that agents migrated
in Stage 070 does not reach a cluster because an agent says it is fine — it
reaches a cluster because the pipeline proves where it came from.

## What This Stage Adds (base setup)

- Red Hat OpenShift Pipelines operator (`pipelines-1.22`): Tekton pipelines
  and Pipelines-as-Code for the delivery path (the
  coolstore-inventory-service repository already carries a `.tekton/`
  PipelineRun from its delivery exercises).
- Red Hat Trusted Artifact Signer operator (`stable-v1.4`): the sigstore
  stack (Fulcio, Rekor) that will sign and attest artifacts.

## Implementation Phase (tracked in BACKLOG)

- Securesign instance with Fulcio OIDC wired to the Stage 070 Keycloak
  (needs live validation before it lands in GitOps).
- Trusted Profile Analyzer for SBOM and vulnerability analysis.
- A pipeline for the Stage 070 migrated application: build, sign, attest,
  SLSA provenance, SBOM, and deploy — with the attestation evidence shown
  next to the agentic-migration evidence.
- Optional: Red Hat Trusted Software Supply Chain (Konflux-based) once a
  sandbox-deployable path exists.

## Demo Script (base setup)

**Know.** Stage 070 ends with agents producing code faster than humans can
hand-verify provenance. Auditors do not accept "the agent said it was fine".
The Trusted Software Factory answer: prove what was built and how — SLSA
provenance, signatures, SBOMs — on the same pipelines the platform already
runs.

**Show (today, base setup).**
- OpenShift console → Pipelines: the Tekton stack is operator-managed and
  ready; the coolstore-inventory-service repository already carries a
  Pipelines-as-Code PipelineRun from its delivery exercises.
- Operators view: Trusted Artifact Signer installed — the sigstore stack
  (Fulcio, Rekor) awaiting the Securesign instance.
- Talk track for the implementation phase (tracked in BACKLOG, recipe from
  the platform showroom modules 5-6): the Stage 070 migrated application
  goes through build → sign (TAS) → SLSA attestation (Tekton Chains) →
  SBOM → TPA analysis, and the attestation evidence lands next to the
  agentic-migration evidence. "The same platform that let agents write the
  code proves what was built from it."

## Deploy And Validate

```bash
./stages/080-ai-trusted-delivery/deploy.sh
./stages/080-ai-trusted-delivery/validate.sh
```

Manifests: [`gitops/stages/080-ai-trusted-delivery/base/`](../../gitops/stages/080-ai-trusted-delivery/base/)

## References

- [Trusted software factory: Building trust in the agentic AI era](https://developers.redhat.com/articles/2026/05/13/trusted-software-factory-building-trust-agentic-ai-era)
- [Red Hat Trusted Software Supply Chain](https://www.redhat.com/en/products/trusted-software-supply-chain)
- [Red Hat Trusted Artifact Signer](https://access.redhat.com/products/red-hat-trusted-artifact-signer)
- [SLSA — Supply-chain Levels for Software Artifacts](https://slsa.dev/)
- [Sigstore](https://www.sigstore.dev/)

## Next Stage

[Stage 090: AI Self-Service Portal](../090-ai-self-service-portal/README.md)
wraps the whole arc into one discoverable self-service experience.
