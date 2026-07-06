---
name: rhads-compliance
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when managing compliance with Conforma, verifying and governing code
  promotion compliance, and customizing sample policies in RHADS-SSC. Do NOT use
  for template customization (use rhads-customize), SBOM inspection (use
  rhads-sbom), or RHADS-SSC installation.
---

# Managing Compliance with RHADS-SSC

Use this skill when working with Conforma for policy-driven supply chain
security, container image signing and attestation, and compliance validation in
Red Hat Advanced Developer Suite - Software Supply Chain (RHADS-SSC) 1.9.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers the Conforma CLI
(`ec`), Rego-based policy authoring, container image signing and attestation
with Cosign and Red Hat Trusted Artifact Signer (RHTAS), and keyless signature
validation.

## Key Concepts

### Conforma

Policy-driven workflow tool that validates container images are signed and
attested by known and trusted build systems. Uses Sigstore, Cosign, and OPA
(Rego) for policy evaluation. Runs automatically during code promotion between
RHADS-SSC environments (dev → stage → production).

### SLSA Provenance

Verifiable information about where, when, and how a software artifact was
produced. Conforma uses SLSA provenance attestations to cryptographically verify
build integrity.

### Promotion Validation

When pushing code between namespaces (dev → stage, stage → production),
Conforma automatically validates that the container image was signed and
attested. Passing validation is required to merge and complete promotion.

## Prerequisites

- Red Hat Trusted Artifact Signer (RHTAS) installed on OCP 4.13+.
- `cosign`, `ec`, and `oc` binaries installed on workstation.
- Access to the OCP web console.

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Read `references/official-doc-extraction.md` for detailed procedures.
3. Install the Conforma CLI (`ec`).
4. Generate signing keys or configure keyless signing via RHTAS.
5. Sign container images with Cosign.
6. Create SLSA provenance and attest images.
7. Author or customize Rego-based Conforma policies.
8. Validate images with `ec validate image`.
9. Review the successes and violations report.

### Install Conforma CLI

```shell
gunzip ec-amd64.gz
chmod +x ec-amd64
sudo mv ec-amd64 /usr/local/bin/ec
ec version
```

### Generate Signing Keys

```shell
cosign generate-key-pair
```

Produces `cosign.pub` (public) and `cosign.key` (private).

### Sign a Container Image (Keyless via RHTAS)

```shell
cosign initialize --mirror=$TUF_URL --root=$TUF_URL/root.json

cosign sign -y --fulcio-url=$FULCIO_URL \
  --rekor-url=$REKOR_URL \
  --oidc-issuer=$OIDC_ISSUER_URL $IMAGE
```

### Create and Attest SLSA Provenance

```shell
cosign attest -y --fulcio-url=$FULCIO_URL \
  --rekor-url=$REKOR_URL \
  --oidc-issuer=$OIDC_ISSUER_URL \
  --predicate predicate.json \
  --type slsaprovenance $IMAGE
```

### Verify Attestation Tree

```shell
cosign tree $IMAGE
```

### Create a Rego Policy Rule

See `references/official-doc-extraction.md` for the full Rego example. Policy
rules use OPA `deny` rules with `METADATA` annotation blocks (`title`,
`description`, `short_name`, `failure_msg`, `solution`). Access image data via
`input.attestations` and match `predicateType` for SLSA provenance.

### Configure Policy Sources

```yaml
sources:
  - policy:
      - <path_or_oci_ref>
    data:
      - <data_source>
    config:
      include: ["@minimal"]
      exclude: ["attestation_task_bundle"]
```

### Validate Image

```shell
ec validate image --image $IMAGE \
  --certificate-identity-regexp '.*' \
  --certificate-oidc-issuer-regexp '.*' \
  --output yaml --show-successes
```

## Policy Configuration Options

| Feature | Syntax |
|---------|--------|
| Include package | `"include": ["test", "java"]` |
| Exclude package | `"exclude": ["attestation_task_bundle"]` |
| Exclude single rule | `"exclude": ["pkg.rule_name"]` |
| Include collection | `"include": ["@minimal"]` |
| Skip failed checks | `"exclude": ["test:get-clair-scan"]` |
| Wildcard | `"*"` matches any package (not partial) |

## RHTAS Environment Variables

```shell
export OPENSHIFT_APPS_SUBDOMAIN=apps.$(oc get dns cluster \
  -o jsonpath='{ .spec.baseDomain }')
export FULCIO_URL=https://fulcio.$OPENSHIFT_APPS_SUBDOMAIN
export REKOR_URL=https://rekor.$OPENSHIFT_APPS_SUBDOMAIN
export TUF_URL=https://tuf.$OPENSHIFT_APPS_SUBDOMAIN
export OIDC_ISSUER_URL=https://keycloak-keycloak-system.\
$OPENSHIFT_APPS_SUBDOMAIN/auth/realms/sigstore
```

Or use the provided script: `source tas-env-variables.sh`

## Validation

- `ec version` confirms the CLI is installed.
- `cosign tree $IMAGE` shows at least one attestation and one signature.
- `ec validate image` output includes `success: true` and expected checks.
- Add `--info` flag for detailed violation explanations and solutions.
- Save the `input` object with `--output policy-input=input.json` for
  debugging custom Rego rules.

## Related Skills

- `rhads-customize` — template and pipeline customization.
- `rhads-sbom` — SBOM inspection with Trusted Profile Analyzer.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
