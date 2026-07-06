# S3 Object Storage Patterns

These examples are review patterns. Verify the active connection type,
environment variables, bucket policy, endpoint, and provider documentation
before copying anything into notebooks or demo scripts.

## Boto3 Client Shape

```python
import os
import boto3
from botocore.client import Config

key_id = os.environ.get("AWS_ACCESS_KEY_ID")
secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
endpoint = os.environ.get("AWS_S3_ENDPOINT")
region = os.environ.get("AWS_DEFAULT_REGION")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=key_id,
    aws_secret_access_key=secret_key,
    config=Config(signature_version="s3v4"),
    endpoint_url=endpoint,
    region_name=region,
)
```

Review points:

- Confirm the environment variable names match the selected connection.
- Do not hard-code secret values.
- Test `s3_client.list_buckets()` before object operations.

## Bucket Operations

```python
s3_client.list_buckets()
s3_client.create_bucket(Bucket="<bucket-name>")
s3_client.delete_bucket(Bucket="<empty-bucket-name>")
```

Review points:

- Bucket creation and deletion require scoped permissions.
- Delete only empty buckets.
- Verify create/delete with a bucket listing.

## Object Operations

```python
s3_client.list_objects_v2(Bucket="<bucket-name>", Prefix="<optional-prefix>")
s3_client.download_file("<bucket-name>", "<object-key>", "<local-path>")
s3_client.upload_file("<local-path>", "<bucket-name>", "<object-key>")
s3_client.copy(
    {"Bucket": "<source-bucket>", "Key": "<source-key>"},
    "<destination-bucket>",
    "<destination-key>",
)
s3_client.delete_object(Bucket="<bucket-name>", Key="<object-key>")
```

Review points:

- Object keys are full paths inside the bucket.
- Local paths are paths inside the workbench container.
- Verify upload/copy/delete with `list_objects_v2`.
- Handle empty bucket listings gracefully.

## Endpoint Format Matrix

| Provider | Endpoint pattern | Review points |
|----------|------------------|---------------|
| MinIO on cluster | `http://<host>:9000` or `https://<host>:9000` | protocol, host, port, cluster DNS, network reachability |
| Amazon S3 | `https://<bucket>.s3.<region>.amazonaws.com` | bucket region, HTTPS, IAM scope |
| Other S3-compatible | provider-specific HTTPS URL | provider docs, bucket and region parameters |

## Self-Signed CA Pattern

```bash
oc get dscinitializations.dscinitialization.opendatahub.io default-dsci -o json \
  | jq -r '.spec.trustedCABundle.customCABundle' > /tmp/my-custom-ca-bundles.crt

oc get configmap kube-root-ca.crt -o jsonpath="{['data']['ca\\.crt']}" \
  >> /tmp/my-custom-ca-bundles.crt
```

Review points:

- Do not run live `oc` commands until the OpenShift safety guard is satisfied.
- Review the full patch workflow with `rhoai-certificate-management`.
- Prefer CA trust over disabling TLS verification for product guidance.
