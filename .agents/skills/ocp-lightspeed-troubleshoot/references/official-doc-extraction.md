# Official Doc Extraction

Use this extraction to keep OpenShift Lightspeed troubleshooting guidance
grounded in the official Red Hat OpenShift Lightspeed 1.0 troubleshoot guide.
All error messages, status codes, and resolution procedures are taken directly
from the official documentation.

## Chapter 1: Troubleshooting OpenShift Lightspeed

Review solutions and workarounds for common installation, configuration, and
operational issues encountered with OpenShift Lightspeed.

### 1.1 502 Bad Gateway Errors in the Interface

**Symptom:** 502 Bad Gateway errors appear in the OpenShift web console
interface after deploying OpenShift Lightspeed.

**Cause:** Service pods have not finished starting.

**Resolution:** Wait a few minutes after deploying OpenShift Lightspeed and
OpenShift Container Platform before trying the interface again. No
configuration change is needed.

### 1.2 Operator Missing from the OperatorHub List

**Symptom:** The OpenShift Lightspeed Operator does not appear in the
OperatorHub catalog.

**Cause:** The OperatorHub displays the OpenShift Lightspeed Operator only for
supported architectures. Filtering prevents the Operator from appearing on
anything other than the `x86_64` architecture.

**Resolution:** Verify the cluster architecture is `x86_64`:

```bash
oc get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}'
```

### 1.3 Reasoning Model Generates Delineator Prompt

**Symptom:** Reasoning models emit tags such as `THOUGHT` or `reasoning` that
appear in the OpenShift Lightspeed response output, separating inner logic from
the final answer.

**Cause:** These tags are part of the model itself. OpenShift Lightspeed does
not control or add them to the output.

**Resolution options:**

1. Add a keyword to your prompt if the model supports it, such as `/nothink`.
   Check the model documentation for the specific keyword.
2. Disable the delineator feature in the inference server configuration
   settings. See the documentation for the inference server or the model being
   used.

### 1.4 API Authentication Failures

**Symptom:** HTTP error status codes when connecting to the OpenShift
Lightspeed API.

#### 401 Unauthorized

**Cause:** The `Authorization` header is missing, malformed, or does not use
the `Bearer` scheme.

**Example detail:** `Unauthorized: No auth header found`

**Resolution:** Ensure the request includes a valid `Authorization: Bearer
<token>` header. Obtain a token via:

```bash
oc whoami -t
```

Then include it in API requests:

```bash
curl -H "Authorization: Bearer $(oc whoami -t)" \
  https://<lightspeed-route>/v1/query
```

#### 403 Forbidden

**Cause:** The token is invalid, expired, or the user lacks RBAC permissions
for the `/ols-access` path.

**Example detail:** `Forbidden: User does not have access`

**Resolution:** Verify the user has the required RBAC role binding for
OpenShift Lightspeed access. Check token validity:

```bash
oc login --token=<token> --server=<api-server>
oc whoami
```

#### 500 Internal Error

**Cause:** An unexpected error occurred through the Kubernetes `TokenReview`
process.

**Example detail:** `Forbidden: Unable to Review Token`

**Resolution:** Check the OpenShift Lightspeed server pod logs for details:

```bash
oc logs -n openshift-lightspeed deployment/lightspeed-app-server
```

Verify that the OpenShift API server is reachable and the service account has
`TokenReview` permissions.

### 1.5 Resolving Prompt Is Too Long Errors

**Symptom:** `Prompt is too long` error when submitting a query.

**Cause:** The total number of tokens (input query, RAG context, and expected
response) exceeds the model context window.

**Resolution:**

1. Verify that the context window value is set correctly for the specific model
   and provider in the `OLSConfig` CR.
2. Set a lower value for the maximum response tokens parameter to allow more
   space for the input query and context.
3. Shorten the query or reduce the size of any attached files.

### 1.6 Resolving Truncated Responses

**Symptom:** Model responses are truncated or incomplete.

**Cause:** The model reaches its pre-configured response token limit.

**Resolution:**

1. Verify that the model supports a higher response token limit.
2. Increase the token limit value in the OpenShift Lightspeed configuration
   (`OLSConfig` CR).
3. If the response is still cut off, type `continue` as a follow-up query to
   prompt the model to provide the remaining text.

> **Note:** Set the response token value in reasonable proportion to the context
> window value. Setting this value too high reserves tokens and might limit the
> size of your input query.

### 1.7 Resolving Issues with Conversation History

**Symptom:** Earlier conversation dialogue is truncated or lost when the model
reaches its context limit.

**Cause:** The context window does not leave enough space for conversation
history after accounting for the response token allocation.

**Resolution:**

1. Verify the context window is correctly set for the specific model and
   provider.
2. Lower the max response tokens value to increase the remaining space
   available for conversation history.

### 1.8 Google Vertex AI Configuration Resource Is Rejected

**Symptom:** The `OLSConfig` custom resource (CR) is rejected during deployment
with a validation error related to Google Vertex AI configuration.

#### Error: `googleVertexConfig is required for google_vertex provider`

**Cause:** The `googleVertexConfig` object is missing from the CR when using
`type: google_vertex`.

**Resolution:** Provide the `googleVertexConfig` object containing both
`projectID` and `location`:

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  llm:
    providers:
      - name: my-vertex-provider
        type: google_vertex
        googleVertexConfig:
          projectID: my-gcp-project
          location: us-central1
        models:
          - name: gemini-2.0-flash
```

#### Error: `googleVertexConfig may only be set when type is google_vertex`

**Cause:** The `googleVertexConfig` field is set for a provider type other than
`google_vertex`.

**Resolution:** Remove the `googleVertexConfig` field. For the
`google_vertex_anthropic` type, use `googleVertexAnthropicConfig` instead.

#### Error: `credentialKey must not be empty or whitespace`

**Cause:** The `credentialKey` field in the credentials reference is set to an
empty or whitespace-only string.

**Resolution:** Provide a valid key name string, or omit the field entirely to
default to `apitoken`.

## Diagnostic Commands Reference

Useful commands for troubleshooting OpenShift Lightspeed:

```bash
# Check Lightspeed operator pod status
oc get pods -n openshift-lightspeed

# View operator logs
oc logs -n openshift-lightspeed deployment/lightspeed-operator-controller-manager

# View application server logs
oc logs -n openshift-lightspeed deployment/lightspeed-app-server

# Check OLSConfig CR status
oc get olsconfig cluster -o yaml

# Verify cluster architecture
oc get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}'

# Test API authentication
curl -k -H "Authorization: Bearer $(oc whoami -t)" \
  https://$(oc get route -n openshift-lightspeed lightspeed-app-server -o jsonpath='{.spec.host}')/v1/query

# Check RBAC for Lightspeed access
oc auth can-i get ols-access --as=<username>
```
