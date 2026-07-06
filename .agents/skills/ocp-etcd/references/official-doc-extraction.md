# Official Documentation Extraction

## Product Role

etcd is the OpenShift control plane data store and is managed by OpenShift
operators. Demo guidance should treat it as platform state, not as an
application component.

Use etcd knowledge to explain:

- why control plane health matters to RHOAI and GitOps workflows
- why backup and restore must be deliberate and tested
- why cluster latency, disk latency, and API transaction rate are platform
  prerequisites for reliable AI workloads
- why unsupported low-level control plane mutations are outside normal demo
  GitOps

## Performance And Latency

The official docs cover disk latency, consensus latency, leader election, log
replication, node scaling, network jitter, peer round trip time, and API
transaction rate. Use those sections to review platform assumptions before
introducing heavy demo workloads.

Review principles:

- Investigate control plane and etcd operator status before blaming RHOAI.
- Check disk and network latency before changing timer or hardware-speed
  tolerance.
- Treat frequent leader elections, missed heartbeats, and high consensus
  latency as control plane stability signals.
- Use the official hardware validation and latency procedures when sizing or
  qualifying a new OpenShift environment.
- For stretched or multi-site designs, account for etcd peer round trip time,
  storage latency, and layered-product latency limits.

## Storage, Defragmentation, And Database Size

The official docs include supported procedures for:

- moving etcd to a different disk when resolving performance issues
- defragmenting etcd data
- determining database size and understanding the effects of growth
- increasing database size when required
- clearing `NOSPACE` alarms after the official procedure calls for it

Do not translate these procedures into casual GitOps patches. They are
maintenance actions that require cluster-admin access, official procedure
review, backup, and live-cluster guard checks.

## Tuning

The official docs expose `spec.controlPlaneHardwareSpeed` on `etcd/cluster` with
valid values of `""`, `"Standard"`, and `"Slower"`. Use this only when the
official symptoms match, such as many leader elections caused by timeouts or
missed heartbeats.

Do not invent timer fields. If tuning is proposed, record:

- the current value from `oc describe etcd/cluster`
- the observed symptom
- the official section used
- the expected pod rollout and verification

## Backup And Restore

Use the official backup procedure before cluster-impacting changes. The
documented backup script is `/usr/local/bin/cluster-backup.sh`, run from a
control plane debug shell with a target directory. It creates:

- `snapshot_<datetimestamp>.db`
- `static_kuberesources_<datetimestamp>.tar.gz`

If etcd encryption is enabled, the static Kubernetes resources archive contains
the encryption keys needed to restore that snapshot. Treat both files as
sensitive operational artifacts. Do not commit them.

Restore and disaster recovery are destructive, cluster-wide procedures. They
can make the API unavailable and require SSH access to control plane hosts.
Use the official restore section directly, and involve Red Hat Support for
production-like recovery or uncertain failure modes.

## Unhealthy Member Replacement

The official docs include procedures for replacing an unhealthy etcd member and
for validating the restored member list and endpoint health. Use those
procedures only after confirming:

- the affected node and pod
- current etcd pod status in `openshift-etcd`
- current backup status
- quorum and control plane operator status
- whether the cluster is single-node or multi-node OpenShift

Any procedure that temporarily disables quorum guard or patches
`unsupportedConfigOverrides` must remain an explicit, official, high-risk
recovery step.

## Encryption

By default, OpenShift etcd data is not encrypted. Enabling etcd encryption adds
protection for selected sensitive resources such as secrets, config maps,
routes, OAuth access tokens, and OAuth authorize tokens.

Supported encryption types are AES-CBC and AES-GCM. Configure them through the
`APIServer` `spec.encryption.type` field:

- `aescbc` for AES-CBC
- `aesgcm` for AES-GCM
- `identity` to disable encryption

Important boundaries:

- etcd encryption encrypts values, not keys; resource types, namespaces, and
  object names remain unencrypted.
- Do not take a backup until initial encryption has completed.
- Encryption and decryption can take 20 minutes or longer depending on cluster
  and database size.
- Verify `Encrypted` status conditions for OpenShift API server, Kubernetes API
  server, and the OpenShift OAuth API server.
- If encryption is enabled during backup, store the static resources archive
  separately and securely because it contains restore keys.

## Spanned Cluster Guidance

Red Hat strongly recommends deploying OpenShift clusters within a data center.
A cluster that spans many data centers extends the cluster as a single failure
domain and is not a substitute for disaster recovery.

For this demo, do not present a stretched OpenShift cluster as the default
European enterprise pattern. Prefer one cluster per region or site, managed by
multi-cluster tooling, unless official platform-specific docs and support
guidance approve the design.
