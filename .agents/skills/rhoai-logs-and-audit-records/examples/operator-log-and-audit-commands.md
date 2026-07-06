# Operator Log And Audit Command Patterns

These commands are live-cluster operations. Follow the OpenShift safety guard
in `AGENTS.md` before running them.

## Temporary Development Logging

```bash
oc patch dsci default-dsci \
  -p '{"spec":{"devFlags":{"logmode":"development"}}}' \
  --type=merge
```

Return to production/default logging after troubleshooting:

```bash
oc patch dsci default-dsci \
  -p '{"spec":{"devFlags":{"logmode":"production"}}}' \
  --type=merge
```

For GitOps, verify the active DSCI schema and encode the same field in the
managed `DSCInitialization` manifest instead of using a live patch.

```yaml
apiVersion: dscinitialization.opendatahub.io/v2
kind: DSCInitialization
metadata:
  name: default-dsci
spec:
  devFlags:
    logmode: production
```

## Stream Operator Logs

```bash
for pod in $(oc get pods -l name=rhods-operator -n redhat-ods-operator -o name); do
  oc logs -f "$pod" -n redhat-ods-operator &
done
```

Stop streams:

```bash
kill $(jobs -p)
```

## Collect OpenShift AI Audit Entries

```bash
audit_file="/tmp/kube-apiserver-audit-opendatahub.log"

oc adm node-logs --role=master --path=kube-apiserver/ \
  | awk '{ print $1 }' | sort -u \
  | while read node ; do
      oc adm node-logs "$node" --path=kube-apiserver/audit.log < /dev/null
    done \
  | grep opendatahub > "$audit_file"
```

## Filter DSC And DSCI User Changes

```bash
jq 'select((.objectRef.apiGroup == "dscinitialization.opendatahub.io"
            or .objectRef.apiGroup == "datasciencecluster.opendatahub.io")
          and .user.username != "system:serviceaccount:redhat-ods-operator:redhat-ods-operator-controller-manager"
          and .verb != "get" and .verb != "watch" and .verb != "list")' \
  < /tmp/kube-apiserver-audit-opendatahub.log
```

Do not commit the collected audit log file. Extract and sanitize only the
minimal evidence needed for documentation or a review note.
