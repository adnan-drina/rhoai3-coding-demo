---
name: rhoai-s3-object-storage-data
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when workbench code reads or writes the repo's ODF S3 buckets through an
  OpenShift AI connection: the Models and Workbench connections in demo-sandbox
  (rhoai-models, rhoai-workbench), the Models, Workbench and Pipelines
  connections in evaluated-models, a Boto3 client from the injected AWS_*
  variables, endpoint format, authentication or certificate errors against
  s3.openshift-storage.svc. Do NOT use for bucket provisioning and OBCs (use
  odf-object-bucket-claims), connection type templates (use
  rhoai-connection-types), attaching connections to workbenches (use
  rhoai-project-workflows) or the pipeline artifact store (use rhoai-ai-pipelines).
---

# RHOAI S3 Object Storage Data

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed records:
`gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/README.md`,
`gitops/stages/050-model-evaluation/050-model-qualification/README.md` (`storage/`).

## When to use

- A notebook in `demo-sandbox` or `evaluated-models` must list, read or write objects.
- An S3 call from a workbench fails on endpoint, credentials or TLS.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `demo-sandbox` buckets `rhoai-models` and `rhoai-workbench` are ODF OBCs; connections "Models" and "Workbench" are filled at runtime by Sync hook `sandbox-s3-connections`, no credentials in Git | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/` | [Prerequisites][prereq] |
| `evaluated-models` has buckets `evaluation-models-{models,workbench,pipelines}` and three connections, filled by hook `evaluated-models-s3-connections` | `gitops/stages/050-model-evaluation/050-model-qualification/storage/` | [Prerequisites][prereq] |
| Connections carry `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT`, `AWS_S3_BUCKET`, `AWS_DEFAULT_REGION`; region falls back to `us-east-1` | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/connection-job.yaml` | [Create an S3 client][client] |
| Endpoint is the in-cluster HTTPS service on port 443 (`s3.openshift-storage.svc`), signed by the OpenShift service CA; the Stage 050 Pipelines connection uses the external ODF Route `s3` instead so signed links open in a browser | `010-sandbox-storage/README.md` (How, Alignment), `gitops/stages/050-model-evaluation/050-model-qualification/storage/connection-job.yaml` | [Object storage endpoints][endpoints] |
| The Workbench bucket is for object exchange; files that need a POSIX filesystem stay on the workbench PVC | `stages/010-openshift-ai-platform-foundation/README.md` | [Object storage endpoints][endpoints] |

## Procedure

1. Attach the project's connection when creating the workbench
   (`rhoai-project-workflows`); the variables above then appear in the pod.
2. Build the client from those variables ([Create an S3 client][client]); never
   paste keys into a notebook committed to Git.
3. Use the bucket and object sections linked below for each operation;
   deleting objects or buckets in the shared demo buckets is a recorded step.
4. Configuration checks after the OpenShift safety guard in `AGENTS.md` (they
   print no values and make no authenticated S3 call):

   ```bash
   ./stages/010-openshift-ai-platform-foundation/validate-sandbox-storage.sh
   oc get obc -n demo-sandbox rhoai-models rhoai-workbench
   oc get obc -n evaluated-models
   ```

## Pitfalls

- TLS: the repo configures no CA trust for the service-CA endpoint; this is a
  recorded Gap in `010-sandbox-storage/README.md`. If a client rejects the
  certificate, follow [self-signed certificates][selfsigned] and
  `rhoai-certificate-management`; do not switch to plain HTTP.
- The service host resolves only inside the cluster; from a laptop use the
  ODF Route (`oc get route s3 -n openshift-storage`).
- Connection changes reach a workbench only after it restarts.
- Each connection names one fixed, OBC-owned bucket (`Prune=false,Delete=false`).
  A new bucket is a new OBC in Git (`odf-object-bucket-claims`), not a
  notebook `create_bucket` call; never delete an OBC-owned bucket from a notebook.
- Authenticated S3 operations are not covered by any validate script.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Setup | [Prerequisites][prereq], [Create an S3 client][client] |
| Buckets | [List][lsb], [Create][mkb], [Delete][rmb] |
| Objects | [List][lso], [Download][get], [Upload][put], [Copy][cp], [Delete][rmo] |
| Endpoints and TLS | [Object storage endpoints][endpoints], [Verification and troubleshooting][verify], [Self-signed certificates][selfsigned] |

## Related skills

`odf-object-bucket-claims`, `rhoai-connection-types`, `rhoai-project-workflows`,
`rhoai-data-science-ide-workflows`, `rhoai-certificate-management`,
`rhoai-ai-pipelines`, `rhoai-mlflow`.

[prereq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#s3-prerequisites_s3
[client]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#creating-an-s3-client_s3
[lsb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#listing-available-amazon-buckets_s3
[mkb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#creating-an-s3-bucket_s3
[rmb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#deleting-a-s3-bucket_s3
[lso]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#listing-files-in-available-amazon-s3-buckets-using-notebook-cells_s3
[get]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#downloading-files-from-available-amazon-s3-buckets-using-notebook-cells_s3
[put]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#uploading-files-to-available-amazon-s3-buckets-using-notebook-cells_s3
[cp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#copying-files-to-between-buckets_s3
[rmo]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#deleting-files-on-your-object-store_s3
[endpoints]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#overview-of-object-storage-endpoints_s3
[verify]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#verification_and_troubleshooting
[selfsigned]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_data_in_an_s3-compatible_object_store/index#accessing-s3-compatible-object-storage-with-self-signed-certificates_s3
