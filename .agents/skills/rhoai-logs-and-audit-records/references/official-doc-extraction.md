# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 Administer chapter
captured in `source-capture.md`.

## Operator Logger Configuration

The OpenShift AI Operator logger is configured at runtime through:

```text
DSCInitialization.spec.devFlags.logmode
```

If `logmode` is not set, the Operator uses the default INFO log level.

The log level applies to all OpenShift AI Operator components, not only
components in `Managed` state.

| `logmode` value | Stacktrace level | Verbosity | Output | Timestamp type |
|-----------------|------------------|-----------|--------|----------------|
| `devel` or `development` | WARN | INFO | Console/plain text | Epoch timestamps |
| unset or empty string | ERROR | INFO | JSON | Human-readable timestamps |
| `prod` or `production` | ERROR | INFO | JSON | Human-readable timestamps |

Operational implications:

- `development`/`devel` logs are generated more frequently and include WARN
  level and above.
- `production`/`prod` or unset logs are less frequent and include ERROR level
  and above.
- Development logging uses console/plain text output.
- Production/default logging uses JSON output.

Prerequisites:

- administrator access to `DSCInitialization` resources
- OpenShift CLI installed for CLI workflows

Official CLI pattern:

```bash
oc patch dsci default-dsci -p '{"spec":{"devFlags":{"logmode":"development"}}}' --type=merge
```

Use this as a temporary live operation only after the project OpenShift safety
guard passes, or encode the equivalent verified field in GitOps when persistent
logger configuration is intended.

Official YAML shape:

```yaml
apiVersion: dscinitialization.opendatahub.io/v2
kind: DSCInitialization
metadata:
  name: default-dsci
spec:
  devFlags:
    logmode: development
```

## Viewing OpenShift AI Operator Logs

Operator logs are streamed from pods with label `name=rhods-operator` in the
`redhat-ods-operator` namespace.

Official command pattern:

```bash
for pod in $(oc get pods -l name=rhods-operator -n redhat-ods-operator -o name); do
  oc logs -f "$pod" -n redhat-ods-operator &
done
```

Stop viewing with `Ctrl+C`. To stop background log streams, terminate the
background jobs.

The OpenShift console path is:

```text
Workloads -> Pods -> redhat-ods-operator project -> pod -> Logs
```

## Viewing Audit Records

Cluster administrators can use OpenShift auditing to review changes made to
OpenShift AI Operator configuration, especially changes to:

- `DataScienceCluster` custom resources
- `DSCInitialization` custom resources

Audit logging is enabled by default in standard OpenShift cluster
configurations. Red Hat OpenShift Service on AWS has different default behavior
called out in Red Hat documentation because the Elasticsearch log store does
not provide secure audit-log storage by default; check the active cluster type
before assuming audit availability.

To access full changed-resource content, the OpenShift audit log policy must be
set to `WriteRequestBodies` or a more comprehensive profile.

Official audit collection pattern:

```bash
oc adm node-logs --role=master --path=kube-apiserver/ \
  | awk '{ print $1 }' | sort -u \
  | while read node ; do
      oc adm node-logs $node --path=kube-apiserver/audit.log < /dev/null
    done \
  | grep opendatahub > /tmp/kube-apiserver-audit-opendatahub.log
```

Official filter pattern for DSC and DSCI changes:

```bash
jq 'select((.objectRef.apiGroup == "dscinitialization.opendatahub.io"
            or .objectRef.apiGroup == "datasciencecluster.opendatahub.io")
          and .user.username != "system:serviceaccount:redhat-ods-operator:redhat-ods-operator-controller-manager"
          and .verb != "get" and .verb != "watch" and .verb != "list")' < /tmp/kube-apiserver-audit-opendatahub.log
```

Verification: commands return relevant log entries.

## Unresolved Items

This chapter does not define:

- OpenShift audit-policy profile selection for this demo
- log retention or forwarding architecture
- SIEM integration
- per-component application log collection outside the OpenShift AI Operator
- model-serving, pipeline, or workbench log review

Use official OpenShift documentation or the relevant component skill before
implementing those areas.
