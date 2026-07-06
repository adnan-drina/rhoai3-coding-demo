# Official Doc Extraction

## MCG Role

- Multicloud Object Gateway provides S3-compatible object storage through ODF.
- MCG can be deployed as a standalone object-storage service.
- Standalone MCG is a good default for this demo because many RHOAI workflows
  need object storage while not necessarily needing ODF block or file storage.

## NooBaa Health And Endpoint Discovery

Use readonly checks after the OpenShift safety guard passes:

```bash
oc get noobaa -n openshift-storage
oc get pods -n openshift-storage
oc get route s3 -n openshift-storage
```

The Red Hat Developer article shows `oc get noobaa -n openshift-storage` as a
developer-friendly readiness check and uses the `s3` route for external S3
endpoint discovery. Verify the route in the active cluster before documenting
it as a dependency.

## Object Service Operations

The ODF managing-hybrid-and-multicloud documentation is the authority for:

- BackingStore resources.
- BucketClass resources.
- Namespace buckets.
- Object bucket policies.
- Bucket notifications and replication.
- Lifecycle behavior.
- Scaling NooBaa endpoints.
- Securing MCG.

Do not invent fields for those resources. Use official docs and live schema
checks before writing manifests.

## Monitoring And Troubleshooting

- Monitor MCG and ObjectBucketClaim health through the ODF object dashboard.
- Use NooBaa resource phase, object dashboard state, pods, events, routes, and
  must-gather as first diagnostics.
- Back up the NooBaa database PVC according to official ODF guidance when
  operating MCG as a durable object-store service.
