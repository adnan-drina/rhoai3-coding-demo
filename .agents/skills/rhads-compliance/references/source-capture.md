# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Red Hat Advanced Developer Suite - Software Supply Chain |
| Product version | 1.9 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Chapter or page title | Managing compliance |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_advanced_developer_suite_-_software_supply_chain/1.9/html-single/managing_compliance/index |
| Documentation category | Secure Your Software Supply Chain |
| Capture date | 2026-07-06 |

## Captured Sections

From "Managing compliance":

- Preface: Conforma purpose and artifact verification in CI/CD
- Chapter 1: Conforma for RHADS-SSC
  - Conforma purpose and SLSA provenance overview
  - Signed artifact security benefits
  - Sigstore, Cosign, and Red Hat Trusted Artifact Signer integration
  - Attestation and provenance concepts
  - Automatic promotion validation (dev → stage → production)
- Chapter 2: Installing the Conforma command line
  - Prerequisites (RHTAS on OCP 4.13+, cosign, oc)
  - Download, decompress, install ec binary
  - Verification with ec version
- Chapter 3: Creating a policy
  - Rego policy rule authoring with OPA
  - METADATA annotation block (title, description, short_name, failure_msg)
  - input.attestations object and SLSA provenance predicateType
  - Policy configuration YAML (sources, policy, data, config)
  - ec validate image with custom policy
  - Saving input object to JSON for debugging
  - 3.1 Configuring a policy
    - Include/exclude packages and rules
    - Wildcard matching
    - Rule collections with @ prefix
    - Skipping failed checks
    - package name:term and rule name:term selectors
- Chapter 4: Signing a container image
  - Red Hat Trusted Artifact Signer shell environment setup
  - Environment variables (FULCIO_URL, REKOR_URL, TUF_URL, OIDC_ISSUER_URL)
  - cosign sign with keyless signing via RHTAS
  - Jenkins Keycloak authentication
  - 4.1 Generating a signing key (cosign generate-key-pair)
  - 4.2 Validating container image signatures with Conforma and RHTAS
    - ec binary installation
    - TUF initialization
    - cosign sign with keyless identity
    - predicate.json creation (SLSA provenance)
    - cosign attest with slsaprovenance type
    - cosign tree verification
    - ec validate image with certificate identity and OIDC issuer
    - Success/failure report interpretation
- Chapter 5: Attesting and validating a container image
  - SLSA provenance predicate.json authoring
  - cosign attest with Fulcio, Rekor, OIDC
  - ec validate image with certificate regexp

## Source Boundaries

This skill captures:

- Conforma overview, architecture, and SLSA provenance concepts
- Conforma CLI (ec) installation and version verification
- Rego policy rule authoring with OPA (deny rules, METADATA blocks)
- Policy configuration (sources, include/exclude, collections, wildcards)
- Container image signing with Cosign (key-based and keyless via RHTAS)
- Cosign key generation (cosign generate-key-pair)
- SLSA provenance attestation with cosign attest
- cosign tree for attestation and signature verification
- ec validate image with policies, certificates, and OIDC issuers
- RHTAS environment variable configuration
- Success and violation report interpretation
- Policy input object export for debugging

This skill does not capture:

- RHADS-SSC installation or initial setup
- Template or pipeline customization (use rhads-customize)
- SBOM inspection workflows (use rhads-sbom)
- RHTAS installation and administration
- RHDH integration beyond promotion validation
- OPA/Rego language reference (external upstream docs)

## API Versions and CRDs

No CRDs are directly managed by Conforma CLI workflows.

| Component | Notes |
|-----------|-------|
| Conforma CLI (`ec`) | Binary downloaded from OCP cluster |
| Cosign | Sigstore-based signing and attestation tool |
| Fulcio | Certificate authority for keyless signing |
| Rekor | Transparency log for signatures and attestations |
| TUF | The Update Framework for secure metadata distribution |
| Keycloak | OIDC identity provider (sigstore realm for signing) |
| OPA/Rego | Policy engine for Conforma rules |
| ec-release-policy | OCI-distributed policy bundle (`quay.io/enterprise-contract/ec-release-policy`) |

## Related Official Sources To Add Later

- Red Hat Advanced Developer Suite - SSC 1.9 Installation Guide
- Red Hat Advanced Developer Suite - SSC 1.9 Customizing RHADS-SSC
- Red Hat Advanced Developer Suite - SSC 1.9 Inspecting SBOMs
- Red Hat Trusted Artifact Signer Documentation
- Enterprise Contract upstream documentation (policy collections)
