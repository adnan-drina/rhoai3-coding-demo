# ObjectBucketClaim Pattern

This is a demo pattern derived from Red Hat ODF documentation and the Red Hat
Developer article. Verify the CRD and storage class in the live cluster before
using it as active GitOps.

```yaml
apiVersion: objectbucket.io/v1alpha1
kind: ObjectBucketClaim
metadata:
  name: demo-object-store
  namespace: demo-project
spec:
  generateBucketName: demo-object-store
  storageClassName: openshift-storage.noobaa.io
```

Validation:

```bash
oc get crd objectbucketclaims.objectbucket.io
oc get storageclass openshift-storage.noobaa.io
oc get obc -n demo-project demo-object-store
oc get configmap -n demo-project demo-object-store
oc get secret -n demo-project demo-object-store
```

Do not commit generated Secret values. Reference the generated Secret and
ConfigMap from workloads at runtime.
