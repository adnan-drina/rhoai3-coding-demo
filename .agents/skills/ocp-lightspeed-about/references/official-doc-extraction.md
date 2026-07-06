# Official Doc Extraction

Use this extraction to keep OpenShift Lightspeed conceptual content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify the
active cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Product Overview

Red Hat OpenShift Lightspeed is a generative AI service that helps developers
and administrators solve problems by providing context-aware recommendations
for OpenShift Container Platform. Users interact with the virtual assistant
using plain English directly inside the OpenShift web console.

OpenShift Lightspeed answers questions using information from official OpenShift
Container Platform documentation.

## Supported Interfaces

OpenShift Lightspeed categorizes programmatic and user interactions by stability
level:

- **REST API** (`/v1/`): stable and supported interface for programmatic
  interactions.
- **Gradio UI** (`/ui`) and internal endpoints: development and debugging only;
  unstable and must not be used for programmatic purposes.

## Product Coverage

OpenShift Lightspeed uses official OpenShift Container Platform documentation as
its primary knowledge source. For products not fully covered by OCP
documentation, the LLM generates answers directly:

- Builds for Red Hat OpenShift
- Red Hat Advanced Cluster Security for Kubernetes
- Red Hat Advanced Cluster Management for Kubernetes
- Red Hat CodeReady Workspaces
- Red Hat OpenShift GitOps
- Red Hat OpenShift Pipelines
- Red Hat OpenShift Serverless
- Red Hat OpenShift Service Mesh 3.x
- Red Hat Quay

## Cluster Resource Requirements

| Component | Min CPU (Cores) | Min Memory | Max Memory |
|-----------|-----------------|------------|------------|
| Application server | 0.5 | 1 GB | 4 Gi |
| PostgreSQL database | 0.3 | 300 Mi | 2 Gi |
| OCP web console | 0.1 | 50 Mi | 100 Mi |
| OpenShift Lightspeed operator | 0.1 | 64 Mi | 256 Mi |

## OpenShift Requirements

- Supported architecture: x86_64
- FIPS mode supported (x86_64, ppc64le, s390X architectures for cryptographic
  libraries)
- OpenShift Container Platform clusters enable telemetry by default; when on,
  Lightspeed sends chats and feedback to Red Hat; disable cluster telemetry to
  stop this

## LLM Provider Requirements

The LLM is a machine learning model that interprets and generates human-like
language. OpenShift Lightspeed does not provide the LLM; you must configure it
before installing the operator.

### SaaS Providers

- **OpenAI**: requires access to the OpenAI API platform
- **Microsoft Azure OpenAI**: requires access to Microsoft Azure OpenAI
- **IBM watsonx**: requires an IBM Cloud watsonx account

### Self-Hosted Providers

- **Red Hat OpenShift AI**: OpenAI API-compatible; must deploy on the
  single-model serving platform with the vLLM runtime; if in a different
  cluster, expose via route; supports vLLM Server 0.8.4+
- **Red Hat Enterprise Linux AI**: OpenAI API-compatible; configured similarly
  to OpenAI provider; model deployment must allow access via secure connection;
  supports vLLM Server 0.8.4+

## Disconnected Mode

OpenShift Lightspeed works in disconnected clusters without full internet
access. Container images must be mirrored. List the OpenShift Lightspeed
Operator with the `oc mirror` command.

## Data Use and Privacy

OpenShift Lightspeed adds cluster and environment details to user messages
before sending to the LLM. The service has limited ability to filter or hide
data sent to the LLM.

Key points:
- Do not enter private information into the interface
- Transcripts and feedback sent to Red Hat use the Red Hat Insights system
- Data follows the same security rules and access limits as Insights
- Users can request Red Hat delete their data via email

## Telemetry and Data Collection

Messages and cluster data pass through a redaction layer before reaching the
LLM. By default, chat transcripts are sent to Red Hat every two hours.

### Transcript Collection

Stored transcripts include:
- User queries
- Complete messages sent to the LLM (system instructions, referenced docs, user
  question)
- Complete LLM responses

Transcripts are linked to the originating cluster. Red Hat can match clusters to
customer accounts but transcripts do not contain user data.

### Feedback Collection

Opt-in user feedback from the virtual assistant interface. Stored data includes:
- Feedback score
- Feedback text
- Original query
- LLM response

Feedback stays associated with the originating cluster. Red Hat cannot link
feedback to specific persons.

### Disabling Data Collection

Disable via the `OLSConfig` custom resource:

```yaml
apiVersion: ols.openshift.io/v1alpha1
kind: OLSConfig
metadata:
  name: cluster
spec:
  ols:
    userDataCollection:
      feedbackDisabled: true
      transcriptsDisabled: true
```

Fields:
- `spec.ols.userDataCollection.feedbackDisabled`: disables feedback collection
- `spec.ols.userDataCollection.transcriptsDisabled`: disables transcript
  collection

To fully stop sending chat transcripts or feedback, opt out of remote health
monitoring at the cluster level.

## Remote Health Monitoring

Uses the Telemeter Client and Insights Operator to gather and report cluster
information. To stop sending transcripts or feedback, opt out of remote health
monitoring following OCP documentation.
