# Official Doc Extraction

Use this extraction to keep RHADS-SSC compliance content grounded in official
Red Hat sources. When implementation needs exact CLI flags or policy syntax,
verify against `ec validate image --help` and the installed RHADS-SSC 1.9
cluster.

## Conforma Overview

Conforma is a policy-driven workflow tool for maintaining software supply chain
security. It validates that container images are signed and attested by known
and trusted build systems using Sigstore and Cosign.

Key capabilities:

- SLSA provenance attestation verification
- Cryptographic signature validation
- OPA/Rego-based policy evaluation
- Automatic promotion gating between environments

When pushing code between RHADS-SSC namespaces (dev → stage → production),
Conforma automatically runs validation. Passing validation is required to merge
and complete promotion.

## Installing the Conforma CLI

Prerequisites: RHTAS on OCP 4.13+, `cosign` and `oc` installed.

```shell
gunzip ec-amd64.gz
chmod +x ec-amd64
sudo mv ec-amd64 /usr/local/bin/ec
```

Verify: `ec version`

## Generating Signing Keys

```shell
cosign generate-key-pair
```

Produces:
- `cosign.pub` — public key (share with collaborators for validation)
- `cosign.key` — private key (restrict to signing personnel)

## RHTAS Environment Setup

Configure shell for keyless signing:

```shell
export OPENSHIFT_APPS_SUBDOMAIN=apps.$(oc get dns cluster \
  -o jsonpath='{ .spec.baseDomain }')
export OIDC_AUTHENTICATION_REALM=sigstore
export FULCIO_URL=https://fulcio.$OPENSHIFT_APPS_SUBDOMAIN
export OIDC_ISSUER_URL=https://keycloak-keycloak-system.\
$OPENSHIFT_APPS_SUBDOMAIN/auth/realms/$OIDC_AUTHENTICATION_REALM
export REKOR_URL=https://rekor.$OPENSHIFT_APPS_SUBDOMAIN
export TUF_URL=https://tuf.$OPENSHIFT_APPS_SUBDOMAIN
```

Or use the provided script:

```shell
cd sigstore-ocp
source tas-env-variables.sh
```

## Signing a Container Image (Keyless)

Initialize TUF:

```shell
cosign initialize --mirror=$TUF_URL --root=$TUF_URL/root.json
```

Sign the image:

```shell
cosign sign -y --fulcio-url=$FULCIO_URL \
  --rekor-url=$REKOR_URL \
  --oidc-issuer=$OIDC_ISSUER_URL $IMAGE
```

Keycloak prompts for authentication in the browser.

## Creating SLSA Provenance Attestation

Create a `predicate.json` file:

```json
{
  "builder": {
    "id": "https://localhost/dummy-id"
  },
  "buildType": "https://localhost/dummy-type",
  "invocation": {},
  "buildConfig": {},
  "metadata": {
    "buildStartedOn": "2023-09-25T16:26:44Z",
    "buildFinishedOn": "2023-09-25T16:28:59Z",
    "completeness": {
      "parameters": false,
      "environment": false,
      "materials": false
    },
    "reproducible": false
  },
  "materials": []
}
```

Attest with Cosign:

```shell
cosign attest -y --fulcio-url=$FULCIO_URL \
  --rekor-url=$REKOR_URL \
  --oidc-issuer=$OIDC_ISSUER_URL \
  --predicate predicate.json \
  --type slsaprovenance $IMAGE
```

Verify the attestation tree:

```shell
cosign tree $IMAGE
```

Expected output includes at least one attestation (`.att`) and one signature
(`.sig`).

## Creating a Rego Policy Rule

```rego
package zero_to_hero

import future.keywords.contains
import future.keywords.if
import future.keywords.in

# METADATA
# title: Builder ID
# description: Verify the SLSA Provenance has the builder.id set to
#   the expected value.
# custom:
#   short_name: builder_id
#   failure_msg: The builder ID %q is not the expected %q
#   solution: >-
#     Ensure the correct build system was used to build the container
#     image.
deny contains result if {
    some attestation in input.attestations
    attestation.statement.predicateType == "https://slsa.dev/provenance/v0.2"

    expected := "https://localhost/dummy-id"
    got := attestation.statement.predicate.builder.id

    expected != got

    result := {
        "code": "zero_to_hero.builder_id",
        "msg": sprintf("The builder ID %q is not expected, %q",
                       [got, expected])
    }
}
```

METADATA block fields: `title`, `description`, `short_name`, `failure_msg`,
`solution`.

Save the `input` object for debugging:

```shell
ec validate image --public-key cosign.pub \
  --image "$REPOSITORY:latest" \
  --policy policy.yaml \
  --output policy-input=input.json
```

## Policy Configuration

### Inline YAML/JSON config

```yaml
sources:
  - policy:
      - "oci::quay.io/enterprise-contract/ec-release-policy:latest"
    data:
      - "git::https://github.com/enterprise-contract/ec-policies//example/data"
    config:
      include: ["@minimal"]
```

### Include/exclude examples

| Goal | Config |
|------|--------|
| Include specific packages | `"include": ["test", "java"]` |
| Exclude packages | `"exclude": ["attestation_task_bundle", "slsa_build_scripted_build"]` |
| Exclude single rule | `"exclude": ["attestation_task_bundle.unacceptable_task_bundle"]` |
| Include collection | `"include": ["@minimal"]` |
| Skip failed checks | `"exclude": ["test:get-clair-scan", "test:clamav-scan"]` |
| Wildcard all packages | `"include": ["*"]` |
| Fine-grained selection | Combine `include` and `exclude` with wildcards |

Wildcard `*` matches any full package name; it does not match partial names.

### Selector types

| Selector | Description |
|----------|-------------|
| package name | Include/exclude all rules from a package |
| rule name | `package.rule_code` — target a single rule |
| package name:term | Exclude a specific item from a rule's list |
| rule name:term | Include/exclude a specific rule for a term |
| @collection name | Predefined rule collection (prefix with `@`) |

## Validating with Conforma

### Key-based validation

```shell
ec validate image --public-key cosign.pub \
  --image "$REPOSITORY:latest" \
  --policy policy.yaml \
  --show-successes --info --output yaml
```

### Keyless validation (RHTAS)

```shell
ec validate image --image $IMAGE \
  --certificate-identity-regexp '.*' \
  --certificate-oidc-issuer-regexp '.*' \
  --output yaml --show-successes
```

Be as specific as possible with `--certificate-identity` and
`--certificate-oidc-issuer` patterns.

### Validation output

```yaml
success: true
successes:
  - metadata:
      code: builtin.attestation.signature_check
    msg: Pass
  - metadata:
      code: builtin.attestation.syntax_check
    msg: Pass
  - metadata:
      code: builtin.image.signature_check
    msg: Pass
```

Add `--info` for detailed violation explanations and solutions.

## Key CLI Commands

| Command | Purpose |
|---------|---------|
| `ec version` | Show installed Conforma CLI version |
| `ec validate image` | Validate container image against policies |
| `cosign generate-key-pair` | Generate signing key pair |
| `cosign sign` | Sign a container image |
| `cosign attest` | Create and sign an attestation |
| `cosign tree` | Display attestation and signature tree |
| `cosign initialize` | Configure TUF for RHTAS |

## Boundaries

- This extraction covers Conforma compliance workflows only.
- Template and pipeline customization belong in `rhads-customize`.
- SBOM inspection belongs in `rhads-sbom`.
- RHTAS installation and administration are not covered here.
- OPA/Rego language reference is external upstream documentation.
