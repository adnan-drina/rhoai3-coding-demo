# Official Doc Extraction

Use this extraction to keep OpenShift Lightspeed installation content grounded
in official Red Hat sources. When implementation needs exact CR fields, verify
the active cluster schema with `oc explain` or `oc get crd` before authoring
GitOps manifests.

> **Coverage note**: The official Install guide (captured 2026-07-06) covers
> Operator installation only. OLSConfig CR creation, LLM provider secret
> setup, and uninstallation are not present in this guide and are expected in
> the Configuring guide. This extraction documents exactly what the Install
> guide provides.

## Prerequisites and Requirements

### Cluster Requirements

- OpenShift Container Platform 4.16 to 4.19 for the OperatorHub installation
  path.
- OpenShift Container Platform 4.20 or later for the software catalog
  installation path.
- Logged in to the OpenShift Container Platform web console as a user with
  the `cluster-admin` role.

### LLM Provider Requirement

An LLM provider must be configured and available before installing the
Operator. The Operator does not install an LLM provider.

Supported LLM providers:

| Provider | Requirements |
|----------|-------------|
| Red Hat Enterprise Linux AI (RHEL AI) | RHEL AI hosting an LLM; see "Generating a custom LLM by using RHEL AI" |
| Red Hat OpenShift AI | OpenShift AI hosting an LLM; see "About model serving" |
| IBM watsonx | IBM Cloud project with watsonx access; IBM watsonx API key |
| OpenAI | OpenAI API key or OpenAI project name; optional service account in a dedicated project for usage tracking |
| Microsoft Azure OpenAI | Azure OpenAI Service instance; at least one model deployment in Azure OpenAI Studio |

Either Red Hat LLM provider (RHEL AI or OpenShift AI) can use a server or
inference service that processes inference queries.

### Subscription Requirements

A valid and active subscription to one of these products is required:

- Red Hat OpenShift Kubernetes Engine
- Red Hat OpenShift Virtualization Engine
- OpenShift Container Platform
- Red Hat OpenShift Platform Plus

## Operator Installation via OperatorHub (OCP 4.16-4.19)

Prerequisites:

- OpenShift Container Platform 4.16 to 4.19 deployed.
- Logged in as `cluster-admin`.
- LLM provider configured and reachable.

Procedure:

1. In the web console, navigate to Operators > OperatorHub.
2. Search for "OpenShift Lightspeed".
3. Locate the OpenShift Lightspeed Operator and click to select it.
4. When the prompt about the community operator displays, click Continue.
5. Click Install.
6. Use the default installation settings and click Install to continue.
7. Navigate to Operators > Installed Operators to verify. `Succeeded` should
   display in the Status column.

## Operator Installation via Software Catalog (OCP 4.20+)

Prerequisites:

- OpenShift Container Platform 4.20 or later deployed.
- Logged in as `cluster-admin`.
- LLM provider configured and reachable.

Procedure:

1. In the web console, navigate to Ecosystem > Software Catalog.
2. Click the Project drop-down list and enable the toggle to show default
   projects.
3. Enter `openshift-marketplace` in the search field.
4. Click to select `openshift-marketplace`.
5. Search for "OpenShift Lightspeed".
6. Locate the OpenShift Lightspeed Operator and click to select it.
7. When the prompt about the OpenShift Lightspeed Operator displays, click
   Install.
8. Use the default installation settings and click Install to continue.
9. Navigate to Ecosystem > Installed Operators to verify. `Succeeded` should
   display in the Status column.

## Verification

After installation, verify the Operator status:

- Navigate to the Installed Operators page (Operators > Installed Operators on
  OCP 4.16-4.19, or Ecosystem > Installed Operators on OCP 4.20+).
- Confirm `Succeeded` appears in the Status column for the OpenShift
  Lightspeed Operator.

CLI verification (expected, not explicitly in the Install guide):

```shell
oc get csv -n openshift-lightspeed-operator -o custom-columns=NAME:.metadata.name,PHASE:.status.phase
```

## Post-Installation: Configuration (Not in Install Guide)

The following steps are required after Operator installation but are documented
in the separate Configuring guide, not the Install guide:

- **OLSConfig CR**: Create the OLSConfig custom resource to configure the
  OpenShift Lightspeed Service, including model selection and provider
  settings.
- **LLM provider credentials**: Create a Kubernetes Secret with API keys or
  credentials for the chosen LLM provider.
- **Service verification**: Confirm the Lightspeed Service is running and
  responding to queries.

These topics should be captured in `ocp-lightspeed-configure` when that skill
is created.

## Uninstallation (Not in Install Guide)

The Install guide does not document uninstallation procedures. Uninstallation
steps are expected in a separate guide or in the Configuring documentation.

Expected uninstallation steps (to be confirmed from official docs):

1. Delete the OLSConfig CR.
2. Uninstall the OpenShift Lightspeed Operator from OperatorHub or software
   catalog.
3. Delete any remaining CRDs in the Lightspeed API group.

> **Do not use the expected steps above for implementation.** Wait for the
> official uninstallation documentation to be captured.
