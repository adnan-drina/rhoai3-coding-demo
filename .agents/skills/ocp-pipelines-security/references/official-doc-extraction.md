# Official Doc Extraction

Use this extraction to keep OpenShift Pipelines security guidance grounded in
the official Red Hat OpenShift Pipelines 1.22 securing guide. All configuration
parameters, procedures, and security context details are taken directly from the
official documentation.

## Chapter 1: Tekton Chains for Supply Chain Security

Tekton Chains is a Kubernetes CRD controller that manages supply chain security
for tasks and pipelines created using Red Hat OpenShift Pipelines. Installed by
default with the OpenShift Pipelines Operator.

### How Tekton Chains Works

1. Observes all task run executions in the cluster.
2. When a task run completes, takes a snapshot.
3. Converts the snapshot to standard payload formats.
4. Signs and stores all artifacts.
5. Uses `Result` objects to capture information; falls back to OCI image URLs
   and digests when results are unavailable.

### Tekton Chains Configuration

Configure via the `TektonConfig` CR (`oc edit TektonConfig config`), within the
`chain:` section.

Example:

```yaml
apiVersion: operator.tekton.dev/v1alpha1
kind: TektonConfig
metadata:
  name: config
spec:
  chain:
    artifacts.taskrun.format: tekton
```

### Supported Configuration Parameters

#### Task Run Artifacts

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `artifacts.taskrun.format` | Format for storing task run payloads | `in-toto`, `slsa/v1` | `in-toto` |
| `artifacts.taskrun.storage` | Storage backend for task run signatures | `tekton`, `oci`, `gcs`, `docdb`, `grafeas` | `oci` |
| `artifacts.taskrun.signer` | Signature backend for signing task run payloads | `x509`, `kms` | `x509` |

Note: `slsa/v1` is an alias of `in-toto` for backwards compatibility.

#### Pipeline Run Artifacts

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `artifacts.pipelinerun.format` | Format for storing pipeline run payloads | `in-toto`, `slsa/v1` | `in-toto` |
| `artifacts.pipelinerun.storage` | Storage backend for pipeline run signatures | `tekton`, `oci`, `gcs`, `docdb`, `grafeas` | `oci` |
| `artifacts.pipelinerun.signer` | Signature backend for signing pipeline run payloads | `x509`, `kms` | `x509` |
| `artifacts.pipelinerun.enable-deep-inspection` | Record child task run results | `"true"`, `"false"` | `"false"` |

#### OCI Artifacts

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `artifacts.oci.format` | Format for storing OCI payloads | `simplesigning` | `simplesigning` |
| `artifacts.oci.storage` | Storage backend for OCI signatures | `tekton`, `oci`, `gcs`, `docdb`, `grafeas` | `oci` |
| `artifacts.oci.signer` | Signature backend for signing OCI payloads | `x509`, `kms` | `x509` |

#### KMS Signers

| Parameter | Description | Values |
|-----------|-------------|--------|
| `signers.kms.kmsref` | URI reference to a KMS service | Schemes: `gcpkms://`, `awskms://`, `azurekms://`, `hashivault://` |

#### Storage Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `storage.gcs.bucket` | GCS bucket for storage | — |
| `storage.oci.repository` | OCI repository for signatures and attestation | — |
| `builder.id` | Builder ID for in-toto attestations | `https://tekton.dev/chains/v2` |
| `builddefinition.buildtype` | Build type for in-toto attestation | `https://tekton.dev/chains/v2/slsa` |

The `builddefinition.buildtype` parameter supports two values:
- `https://tekton.dev/chains/v2/slsa` — strict SLSA v1.0 conformance
- `https://tekton.dev/chains/v2/slsa-tekton` — additional info including labels,
  annotations, and resolved dependencies

#### Transparency Attestation Storage

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `transparency.enabled` | Enable automatic binary transparency uploads | `true`, `false`, `manual` | `false` |
| `transparency.url` | URL for uploading transparency attestations | — | `https://rekor.sigstore.dev` |

When `transparency.enabled` is `manual`, only task runs and pipeline runs
annotated with `chains.tekton.dev/transparency-upload: "true"` are uploaded.

#### x509 Keyless Signing with Fulcio

| Parameter | Description | Values | Default |
|-----------|-------------|--------|---------|
| `signers.x509.fulcio.enabled` | Enable requesting certificates from Fulcio | `true`, `false` | `false` |
| `signers.x509.fulcio.address` | Fulcio address | — | `https://v1.fulcio.sigstore.dev` |
| `signers.x509.fulcio.issuer` | Expected OIDC issuer | — | `https://oauth2.sigstore.dev/auth` |
| `signers.x509.fulcio.provider` | ID Token provider | `google`, `spiffe`, `github`, `filesystem` | attempts all |
| `signers.x509.identity.token.file` | Path to ID Token file | — | — |
| `signers.x509.tuf.mirror.url` | URL for TUF server | — | `https://sigstore-tuf-root.storage.googleapis.com` |

#### KMS Authentication

| Parameter | Description |
|-----------|-------------|
| `signers.kms.auth.address` | URI of the KMS server (`VAULT_ADDR`) |
| `signers.kms.auth.token` | Authentication token (`VAULT_TOKEN`) — insecure for production |
| `signers.kms.auth.token-path` | Full path of file with auth token — preferred for production |
| `signers.kms.auth.oidc.path` | Path for OIDC authentication (e.g. `jwt` for Vault) |
| `signers.kms.auth.oidc.role` | Role for OIDC authentication |
| `signers.kms.auth.spire.sock` | URI of the Spire socket |
| `signers.kms.auth.spire.audience` | Audience for requesting SVID from Spire |

#### Docstore Storage

| Parameter | Description |
|-----------|-------------|
| `storage.docdb.url` | go-cloud URI reference to a docstore collection |
| `storage.docdb.mongo-server-url` | Mongo server URL (insecure for production) |
| `storage.docdb.mongo-server-url-dir` | Directory containing `MONGO_SERVER_URL` file (preferred) |

Supported docstore services: `firestore`, `dynamodb`.

#### Grafeas Storage

| Parameter | Description | Default |
|-----------|-------------|---------|
| `storage.grafeas.projectid` | OCP project containing Grafeas server | — |
| `storage.grafeas.noteid` | Prefix for note names | `tekton-` |
| `storage.grafeas.notehint` | Human-readable name for ATTESTATION note | `This attestation note was generated by Tekton Chains` |

### Mounting Secrets for Chains Controller

#### Mongo Server URL Secret

```bash
oc create secret generic mongo-url -n tekton-chains \
  --from-file=MONGO_SERVER_URL=<path>/MONGO_SERVER_URL
```

Mount in `TektonConfig` CR under `chain.options.deployments.tekton-chains-controller`
and set `storage.docdb.mongo-server-url-dir` to the mount path (e.g. `/tmp/mongo-url`).

#### KMS Authentication Token Secret

```bash
oc create secret generic kms-secrets -n tekton-chains \
  --from-file=KMS_AUTH_TOKEN=<path_and_name>
```

Mount in `TektonConfig` CR and set `signers.kms.auth.token-path` to the full
path (e.g. `/etc/kms-secrets/KMS_AUTH_TOKEN`).

### Namespace Scoping for Tekton Chains

Add `--namespace=` argument in the `TektonConfig` CR under
`chain.options.deployments.tekton-chains-controller` to limit which namespaces
Chains monitors. If omitted or empty, all namespaces are watched.

```yaml
spec:
  chain:
    options:
      deployments:
        tekton-chains-controller:
          spec:
            template:
              spec:
                containers:
                - args:
                  - --namespace=dev, test
                  name: tekton-chains-controller
```

## Chapter 2: Signing Secrets for Tekton Chains

A private key and password must exist in the `signing-secrets` secret in the
`openshift-pipelines` namespace.

### Supported Signing Schemes

- **x509**: Private key stored as `x509.pem`, unencrypted PKCS #8 PEM,
  `ed25519` or `ecdsa` type
- **cosign**: Private key stored as `cosign.key`, password as `cosign.password`,
  encrypted PEM of type `ENCRYPTED COSIGN PRIVATE KEY`

Use only one scheme at a time.

### Generating Keys

#### Via TektonConfig CR (Automated)

Set `generateSigningSecret: true` in the `chain` section. Generates ECDSA cosign
key pair automatically.

**Warning**: Setting `generateSigningSecret` from `true` to `false` empties the
`signing-secrets` secret.

Extract the public key:
```bash
oc extract -n openshift-pipelines secret/signing-secrets --keys=cosign.pub
```

#### Via cosign Tool (Manual)

```bash
cosign generate-key-pair k8s://openshift-pipelines/signing-secrets
```

#### Via Skopeo Tool (Manual)

1. `skopeo generate-sigstore-key --output-prefix <mykey>`
2. Base64-encode the `.pub`, `.private`, and passphrase files
3. Create the `signing-secrets` secret with `cosign.key`, `cosign.password`,
   `cosign.pub` data fields

### Resolving "Secret Already Exists"

Delete the existing secret:
```bash
oc delete secret signing-secrets -n openshift-pipelines
```

## Chapter 3: OCI Registry Authentication

Configure a service account with credentials for Tekton Chains to push
signatures to an OCI registry.

```bash
export NAMESPACE=<namespace>
export SERVICE_ACCOUNT_NAME=<service_account>

oc create secret registry-credentials \
  --from-file=.dockerconfigjson \
  --type=kubernetes.io/dockerconfigjson \
  -n $NAMESPACE

oc patch serviceaccount $SERVICE_ACCOUNT_NAME \
  -p "{\"imagePullSecrets\": [{\"name\": \"registry-credentials\"}]}" -n $NAMESPACE
```

Best practice: Create a separate service account rather than patching the
default `pipeline` SA (the Operator will override it).

## Chapter 4: Create and Verify Task Run Signatures

Procedure to sign and verify without additional authentication:

1. Configure `TektonConfig` to disable OCI storage and use `tekton` for task
   run format and storage
2. Restart Chains controller: `oc delete po -n openshift-pipelines -l app=tekton-chains-controller`
3. Create a task run
4. Retrieve signature from annotations:
   ```bash
   export TASKRUN_UID=$(tkn tr describe --last -o jsonpath='{.metadata.uid}')
   tkn tr describe --last -o jsonpath="{.metadata.annotations.chains\.tekton\.dev/signature-taskrun-$TASKRUN_UID}" | base64 -d > sig
   ```
5. Verify with cosign:
   ```bash
   cosign verify-blob-attestation --insecure-ignore-tlog --key path/to/cosign.pub --signature sig --type slsaprovenance --check-claims=false /dev/null
   ```

## Chapter 5: Sign and Verify Image and Provenance

End-to-end procedure using Kaniko task:

1. Create Docker config secret for registry authentication
2. Configure Chains: `artifacts.taskrun.format: in-toto`,
   `artifacts.taskrun.storage: oci`, `transparency.enabled: true`
3. Run Kaniko task to build and push image
4. Wait for `chains.tekton.dev/signed=true` annotation
5. Verify: `cosign verify --key cosign.pub $REGISTRY/image`
6. Verify attestation: `cosign verify-attestation --key cosign.pub $REGISTRY/image`
7. Search Rekor for provenance: `rekor-cli search --sha <image_digest>`
8. Retrieve attestation: `rekor-cli get --uuid <uuid> --format json | jq -r .Attestation | base64 --decode | jq`

## Chapter 6: Software Supply Chain Security in the Web Console

### Viewing Project Vulnerabilities

PipelineRun details page shows vulnerabilities by severity (critical, high,
medium, low). Available from OCP 4.15+.

Vulnerability scan task must produce results in this format:
```json
{"vulnerabilities":{"critical": N, "high": N, "medium": N, "low": N}}
```

The result must be named ending with `SCAN_OUTPUT` and annotated with:
- `task.output.location: results`
- `task.results.format: application/json`
- `task.results.key: SCAN_OUTPUT`

### Viewing and Downloading SBOMs

SBOM task must produce a `LINK_TO_SBOM` result annotated with:
- `task.output.location: results`
- `task.results.format: application/text`
- `task.results.key: LINK_TO_SBOM`
- `task.results.type: external-link` (optional, opens in new tab)

Download SBOM via CLI:
```bash
cosign download sbom quay.io/<workspace>/user-workload@sha256
```

### Signed Badge

PipelineRuns that meet Tekton Chains requirements display a signed badge when
Chains is configured and the run has been signed.

## Chapter 7: Security Context for Pods

### Default SCC

Default service account: `pipeline`. Default SCC: `pipelines-scc` (extends
`anyuid` with `SETFCAP` capability and `fsGroup: MustRunAs`). Buildah uses
`vfs` as default storage driver.

### Configuring Default and Maximum SCC

In `TektonConfig` CR:

```yaml
spec:
  platforms:
    openshift:
      scc:
        default: "restricted-v2"
        maxAllowed: "privileged"
```

- `default`: SCC attached to the `pipeline` SA for all pods
- `maxAllowed`: Least restrictive SCC allowed in any namespace (does not apply
  to custom SA/SCC configurations)

### Per-Namespace SCC

Set the `operator.tekton.dev/scc` annotation on the namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: test-namespace
  annotations:
    operator.tekton.dev/scc: nonroot
```

Must not be less restrictive than `maxAllowed`.

### Custom SCC and Service Account

To avoid pod timeouts caused by `fsGroup.type: MustRunAs`:

1. Create custom SCC with `fsGroup.type: RunAsAny`
2. Create custom service account
3. Associate: `oc adm policy add-scc-to-user my-scc -z fsgroup-runasany`
4. Use in PipelineRun/TaskRun via `taskRunTemplate.serviceAccountName`

Best practice: Always use custom SCC and SA for pipeline runs.

## Chapter 8: Secure Webhooks with Event Listeners

### HTTPS EventListener

OpenShift Pipelines supports both HTTP and HTTPS for EventListener resources.
The `tekton-operator-proxy-webhook` pod monitors namespace labels.

To enable HTTPS:
```bash
oc label namespace <ns_name> operator.tekton.dev/enable-annotation=enabled
```

This causes the webhook to set
`service.beta.openshift.io/serving-cert-secret-name=<secret_name>` on the
EventListener, creating the necessary secrets and certificates.

### Secure Routes

Create re-encrypted TLS termination routes:
```bash
oc create route reencrypt --service=<svc_name> --cert=tls.crt --key=tls.key --ca-cert=ca.crt --hostname=<hostname>
```

### EventListener Security Context

Configure pod-level and container-level security context directly in the
EventListener CR:

```yaml
spec:
  resources:
    kubernetesResource:
      spec:
        template:
          spec:
            securityContext:
              runAsNonRoot: true
            containers:
              - securityContext:
                  readOnlyRootFilesystem: true
```

## Chapter 9: Pipeline Authentication with Repositories

### Authentication via Service Accounts

#### Git Authentication Secrets

- `kubernetes.io/basic-auth`: Username and password
- `kubernetes.io/ssh-auth`: SSH private key

Annotation keys must begin with `tekton.dev/git-` with the host URL as value.

Example basic-auth:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: git-secret-basic
  annotations:
    tekton.dev/git-0: github.com
    tekton.dev/git-1: gitlab.com
type: kubernetes.io/basic-auth
stringData:
  username: <username>
  password: <password>
```

Example ssh-auth:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: git-secret-ssh
  annotations:
    tekton.dev/git-0: https://github.com
type: kubernetes.io/ssh-auth
stringData:
  ssh-privatekey: <private-key-content>
```

#### Container Registry Authentication Secrets

- `kubernetes.io/basic-auth`: Username and password (requires `tekton.dev/docker-` annotations)
- `kubernetes.io/dockercfg`: Serialized `~/.dockercfg`
- `kubernetes.io/dockerconfigjson`: Serialized `~/.docker/config.json`

#### SSH Authentication Considerations

Git SSH authentication ignores `$HOME` and uses `/etc/passwd`. When running
Git commands directly in steps, symlink `/tekton/home/.ssh` to the user's
home directory:
```yaml
script:
  ln -s $HOME/.ssh /root/.ssh
```

Not needed when using `git` pipeline resource or `git-clone` catalog task.

#### Non-Root User Considerations

- SSH auth requires a valid home directory in `/etc/passwd`
- Must symlink secret files from `/tekton/home` to the non-root user's home

### Authentication via Workspaces

Configure a named workspace in the task, bind a secret to it at runtime.
No annotations required.

#### SSH via Workspaces

```bash
oc create secret generic my-github-ssh-credentials \
  --from-file=id_ed25519=/home/user/.ssh/id_ed25519 \
  --from-file=known_hosts=/home/user/.ssh/known_hosts
```

Run with:
```bash
tkn task start <task_name> --workspace name=ssh-directory,secret=my-github-ssh-credentials
```

#### Container Registry via Workspaces

```bash
oc create secret generic my-registry-credentials \
  --from-file=config.json=/home/user/credentials/config.json
```

Set `DOCKER_CONFIG` environment variable to `$(workspaces.dockerconfig.path)`.

#### Limiting Secrets to Specific Steps

Define the workspace in both the task specification and the step specification.
Steps without the workspace definition cannot access the secret.

## Chapter 10: Building Container Images with Buildah as Non-Root

### User Namespace Method (Simpler)

Add annotations to the task:
```yaml
metadata:
  annotations:
    io.kubernetes.cri-o.userns-mode: 'auto:size=65536;map-to-root=true'
    io.openshift.builder: 'true'
```

Add `stepTemplate` with:
- `securityContext.runAsNonRoot: true`
- `securityContext.runAsUser: 1000`
- `securityContext.capabilities.add: [SETFCAP]`

### Custom SA and SCC Method (More Compatible)

1. Create custom SCC with `allowPrivilegeEscalation: true`,
   `runAsUser.type: MustRunAs`, `runAsUser.uid: 1000`
2. Create `pipelines-sa-userid-1000` service account
3. Create ClusterRole and RoleBinding for the custom SCC
4. Modify Buildah task with `securityContext.runAsUser: 1000`
5. Change volume mount to `/home/build/.local/share/containers`

**Important**: Buildah requires `allowPrivilegeEscalation: true` to use
`SETUID` and `SETGID` capabilities.

### Limitations of Unprivileged Builds

- `--mount=type=cache` may fail due to permission issues
- `--mount=type=secret` fails because mounting requires additional capabilities

## Chapter 11: buildah-ns Tekton Task

The `buildah-ns` task builds OCI images without a container runtime daemon,
using user namespace isolation for enhanced security.

### Security Annotations

```
io.kubernetes.cri-o.userns-mode: "auto"
io.openshift.builder: "true"
```

### Security Model

User namespace isolation maps UIDs:
- Inside the container: processes run as UID 0 (appear as root)
- Outside the container: processes run as a nonzero UID on the host

Security advantages:
- Kernel-level isolation between containers
- Reduced privilege exposure
- Container escape protection

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `IMAGE` | string | Required | Fully qualified image name with tag |
| `CONTAINERFILE_PATH` | string | `Containerfile` | Path to build file |
| `TLS_VERIFY` | string | `true` | Verify TLS when pushing |
| `VERBOSE` | string | `false` | Enable verbose output |
| `SUBDIRECTORY` | string | `.` | Build context subdirectory |
| `STORAGE_DRIVER` | string | `overlay` | Buildah storage driver |
| `BUILD_EXTRA_ARGS` | string | empty | Additional build flags |
| `PUSH_EXTRA_ARGS` | string | empty | Additional push flags |
| `SKIP_PUSH` | string | `false` | Skip pushing to registry |

### Results

| Name | Description |
|------|-------------|
| `IMAGE_URL` | Fully qualified name of the built image |
| `IMAGE_DIGEST` | SHA256 digest of the built image |

### Running the buildah-ns Task

```yaml
apiVersion: tekton.dev/v1
kind: PipelineRun
spec:
  pipelineRef:
    name: task-buildah-ns
  params:
    - name: IMAGE
      value: your-image-name
    - name: TLS_VERIFY
      value: true
  workspaces:
    - name: source
      persistentVolumeClaim:
        claimName: your-pvc-name
```

If the target registry requires authentication, configure a Kubernetes secret
and link it to the service account.
