# Stage 080: AI in Trusted Delivery

> **Status:** base setup. This stage currently installs the trusted-delivery
> operators through GitOps; the Securesign instance, Trusted Profile
> Analyzer, and the pipeline for the Stage 070 migrated application are the
> implementation phase tracked in [BACKLOG.md](../../BACKLOG.md).
> Anchor article: [Trusted software factory: Building trust in the agentic AI era](https://developers.redhat.com/articles/2026/05/13/trusted-software-factory-building-trust-agentic-ai-era).

## Why This Matters

Stages 050 through 070 progressively hand more of the software lifecycle to AI: assisted edits, skill-guided tasks, autonomous multi-agent migration. Every step multiplies output — and multiplies the question auditors and platform teams ask: *who built this artifact, from what, and can we prove it?*

The Trusted Software Factory pattern answers with supply-chain evidence rather than trust-me claims: tamper-proof SLSA provenance for the build process, sigstore-based signatures and attestations, software bills of materials, and vulnerability intelligence that separates real exploitability from noise. Applied to this demo: the Quarkus service that agents migrated in Stage 070 does not reach a cluster because an agent says it is fine — it reaches a cluster because the pipeline proves where it came from.

## Architecture

Stage 080 adds the trusted-delivery operator layer between the development stages (050 through 070) and production deployment. Red Hat OpenShift Pipelines provides the Tekton runtime for build pipelines and Pipelines-as-Code. Red Hat Trusted Artifact Signer provides the sigstore stack (Fulcio CA, Rekor transparency log) that will sign and attest artifacts once the Securesign instance is configured.

Both operators install into `openshift-operators` with `Automatic` approval. Because Stage 040 deploys Red Hat Connectivity Link subscriptions with `Manual` approval in the same namespace, OLM applies the most restrictive approval to shared InstallPlans — blocking the automatic intent. A Sync hook Job (`approve-installplans.yaml`) works around this by approving pending InstallPlans that carry the Pipelines or TAS CSVs.

## What This Stage Adds

This stage adds the trusted-delivery operator foundation (base setup).

- Red Hat OpenShift Pipelines operator (channel `pipelines-1.22`): Tekton pipelines and Pipelines-as-Code for the delivery path.
- Red Hat Trusted Artifact Signer operator (channel `stable-v1.4`): the sigstore stack (Fulcio, Rekor) that will sign and attest artifacts.
- An InstallPlan approval hook Job that handles the shared-namespace Manual-approval interaction with Stage 040 subscriptions.
- TektonConfig health validation; the Securesign instance is checked as a warning (not a failure) since it arrives with the implementation phase.

## What To Notice And Why It Matters

Stage 080 establishes the operator foundation for provenance-driven delivery.

- The Tekton stack is operator-managed and ready; existing repositories (such as `coolstore-inventory-service`) already carry `.tekton/` PipelineRun definitions from their delivery exercises.
- The Trusted Artifact Signer operator is installed and awaiting the Securesign instance — the sigstore stack (Fulcio CA, Rekor transparency log) will issue signing identities tied to the platform's Keycloak OIDC once configured.
- The InstallPlan workaround is a practical example of multi-stage operator co-tenancy on OpenShift: later stages must account for earlier stages' subscription approval policies.

This matters because AI-generated code needs the same supply-chain evidence as human-written code — and the pipeline that produces that evidence must be reproducible, operator-managed, and auditable.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Pipelines brings Tekton to OpenShift with operator lifecycle management, Pipelines-as-Code for Git-triggered builds, and Tekton Chains for automated SLSA provenance and in-toto attestation. Red Hat Trusted Artifact Signer packages the sigstore project (Fulcio, Rekor, Cosign) for enterprise use with OIDC-bound signing identities and a transparency log.

In the implementation phase, these components combine: the pipeline builds the Stage 070 migrated application, Tekton Chains records SLSA provenance, Trusted Artifact Signer signs the image and attestations, and Trusted Profile Analyzer scans the SBOM for vulnerabilities. The result is a chain of evidence from agent-authored source to deployed artifact.

## Trust Boundaries

Build pipelines execute in a controlled namespace with scoped RBAC. Signing identities are bound to the platform's OIDC issuer — no long-lived signing keys are stored in the cluster. The transparency log (Rekor) provides tamper-evident records. Production deployment policies should gate on attestation verification, not on pipeline success alone.

## Red Hat Products Used

- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** provides Tekton-based CI/CD pipelines, Pipelines-as-Code, and Tekton Chains for provenance.
- **[Red Hat Trusted Artifact Signer](https://access.redhat.com/products/red-hat-trusted-artifact-signer)** provides the sigstore stack (Fulcio, Rekor, Cosign) for signing and attestation.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the runtime, operator lifecycle, and namespace isolation.

## Open Source Projects To Know

- [Tekton](https://tekton.dev/) is the cloud-native CI/CD framework behind OpenShift Pipelines.
- [Tekton Chains](https://tekton.dev/docs/chains/) provides automated SLSA provenance and in-toto attestation for Tekton builds.
- [sigstore](https://www.sigstore.dev/) provides keyless code signing with transparency log guarantees (Cosign, Fulcio, Rekor).
- [SLSA](https://slsa.dev/) (Supply-chain Levels for Software Artifacts) is the framework for supply-chain integrity levels.
- [in-toto](https://in-toto.io/) defines the attestation format used by Tekton Chains and sigstore.

## Implementation Phase (tracked in BACKLOG)

- Securesign instance with Fulcio OIDC wired to the Stage 070 Keycloak (needs live validation before it lands in GitOps).
- Trusted Profile Analyzer for SBOM and vulnerability analysis.
- A pipeline for the Stage 070 migrated application: build, sign, attest, SLSA provenance, SBOM, and deploy — with the attestation evidence shown next to the agentic-migration evidence.
- Optional: Red Hat Trusted Software Supply Chain (Konflux-based) once a sandbox-deployable path exists.

## Demo Script

### Base setup talk track

**Know.** Stage 070 ends with agents producing code faster than humans can hand-verify provenance. Auditors do not accept "the agent said it was fine". The Trusted Software Factory answer: prove what was built and how — SLSA provenance, signatures, SBOMs — on the same pipelines the platform already runs.

**Show (today, base setup).**
- OpenShift console, Pipelines view: the Tekton stack is operator-managed and ready; the `coolstore-inventory-service` repository already carries a Pipelines-as-Code PipelineRun from its delivery exercises.
- Operators view: Trusted Artifact Signer installed — the sigstore stack (Fulcio, Rekor) awaiting the Securesign instance.
- Talk track for the implementation phase (tracked in BACKLOG, recipe from the platform showroom modules 5-6): the Stage 070 migrated application goes through build, sign (TAS), SLSA attestation (Tekton Chains), SBOM, TPA analysis, and the attestation evidence lands next to the agentic-migration evidence. "The same platform that let agents write the code proves what was built from it."

## Deploy And Validate

```bash
./stages/080-ai-trusted-delivery/deploy.sh
./stages/080-ai-trusted-delivery/validate.sh
```

Manifests: [`gitops/stages/080-ai-trusted-delivery/base/`](../../gitops/stages/080-ai-trusted-delivery/base/)

Flow dependency: Stage 070 (Autonomous Application Migration).

Validation note: `validate.sh` treats a missing Securesign instance as a warning, not a failure — the instance arrives with the implementation phase.

## References

| Topic | Link |
|-------|------|
| Trusted software factory article | https://developers.redhat.com/articles/2026/05/13/trusted-software-factory-building-trust-agentic-ai-era |
| Red Hat Trusted Software Supply Chain | https://www.redhat.com/en/products/trusted-software-supply-chain |
| Red Hat Trusted Artifact Signer | https://access.redhat.com/products/red-hat-trusted-artifact-signer |
| Red Hat OpenShift Pipelines documentation | https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/ |
| SLSA framework | https://slsa.dev/ |
| sigstore project | https://www.sigstore.dev/ |

## Next Stage

[Stage 090: AI Self-Service Portal](../090-ai-self-service-portal/README.md) wraps the whole arc into one discoverable self-service experience.
