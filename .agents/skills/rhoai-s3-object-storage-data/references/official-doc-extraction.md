# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Concept Model

Users can access data in S3-compatible object stores such as Ceph, MinIO, IBM
Cloud Object Storage, and Amazon S3 from an OpenShift AI workbench.

The official guide uses Boto3, the AWS SDK for Python, to create a local S3
client in a workbench and run bucket and object operations.

## Prerequisites

The user needs:

- an OpenShift AI workbench
- access to an S3-compatible object store
- credentials for the S3-compatible storage account
- files to work with in the object store
- a configured workbench connection based on the S3 account credentials

Credential rule:

- storage credentials must be scoped only to resources for the specific
  project
- shared credentials with access to multiple projects' buckets must not be used

## Boto3 Client Setup

The official workflow opens the workbench, clones the
`opendatahub-io/odh-doc-examples` repository, opens the `storage` folder, and
uses `s3client_examples.ipynb`.

The notebook examples cover:

- installing Boto3 and required libraries
- creating an S3 client session
- creating an S3 client connection
- listing files
- creating a bucket
- uploading a file
- downloading a file
- copying files between buckets
- deleting an object
- deleting a bucket

The official example reads these environment variables:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_ENDPOINT`
- `AWS_DEFAULT_REGION`

The S3 client uses AWS signature version `s3v4`, the configured endpoint URL,
and the configured region.

Verification:

- `list_buckets()` succeeds
- response metadata includes HTTP status code `200`
- bucket data is returned

## Bucket Operations

List buckets:

- use Boto3 `list_buckets()`
- verify HTTP status code `200`
- optionally print only bucket names from the returned `Buckets` list

Create bucket:

- use Boto3 `create_bucket(Bucket='<bucket_name>')`
- verify the new bucket appears in a subsequent bucket listing

Delete bucket:

- ensure the bucket is empty before deleting it
- use Boto3 `delete_bucket(Bucket='<bucket_name>')`
- verify the deleted bucket no longer appears in bucket listings

## Object Operations

List objects:

- use Boto3 `list_objects_v2(Bucket='<bucket_name>')`
- optionally print object keys from `Contents`
- use the `Prefix` argument to refine listing by path prefix

Download object:

- use Boto3 `download_file('<bucket_name>', '<object_name>', '<file_name>')`
- object name must include the full path/key in the bucket
- file name is the target local path in the workbench
- verify the file appears at the specified workbench path

Upload object:

- use Boto3 `upload_file('<file_name>', '<bucket_name>', '<object_name>')`
- file name must include the full local path in the workbench
- object name is the full key used to save the file in the bucket
- verify the uploaded object appears in object listing

Copy object:

- define `copy_source` with source `Bucket` and `Key`
- call Boto3 `copy(copy_source, '<destination_bucket>',
  '<destination_key>')`
- verify the destination object appears in destination bucket listing

Delete object:

- use Boto3 `delete_object(Bucket='<bucket_name>', Key='<object_key>')`
- successful deletion returns HTTP status code `204`
- verify the object no longer appears in object listing

## Endpoint Formatting

Correct endpoint formatting reduces connection errors and access problems.

On-cluster MinIO:

- prefix endpoint with `http://` or `https://` based on MinIO security setup
- include cluster IP or hostname
- include port when required, commonly `9000`
- verify MinIO is reachable from inside the cluster

Amazon S3:

- use `https://`
- use region-specific endpoint format
- official guide format: `<bucket-name>.s3.<region>.amazonaws.com`
- ensure the bucket is in the expected region for security and compliance

Other S3-compatible object stores:

- follow the provider-specific endpoint format
- include provider base URL, bucket name, and region parameters as required by
  that provider
- verify provider documentation before finalizing the endpoint

Troubleshooting checks:

- network accessibility from OpenShift AI cluster
- correct authentication credentials
- exact endpoint URL format without typos or missing components

## Self-Signed Certificates

For in-cluster object storage solutions or databases using self-signed
certificates, OpenShift AI components need a trusted CA certificate.

The official guide uses each namespace's `kube-root-ca.crt` ConfigMap and
updates the OpenShift AI `DSCInitialization` trusted CA custom bundle.

Official workflow shape:

- retrieve current `default-dsci` trusted CA custom bundle
- append the `kube-root-ca.crt` CA certificate
- patch `dscinitialization default-dsci` at
  `/spec/trustedCABundle/customCABundle`

Verification:

- components configured to use object storage or in-cluster databases with the
  trusted certificate start successfully
- the guide gives an AI Pipelines local object storage example as a verification
  path

Use `rhoai-certificate-management` for broader CA bundle policy and GitOps
review before implementing certificate changes.

## Out Of Scope For This Guide

This guide does not define:

- how to provision S3-compatible object storage itself
- production IAM or bucket lifecycle design
- connection type template administration
- OpenShift storage class configuration
- complete AI Pipelines object-store setup
- model registry database or artifact storage setup
- model-serving object storage behavior
- production PKI design
