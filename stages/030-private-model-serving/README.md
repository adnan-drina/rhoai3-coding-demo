# Stage 030 — Private Model Serving

## Why This Matters

Private models need a dependable serving platform and a shared place to discover and manage model artifacts. This stage gives platform teams those foundations before Stage 040 deploys models and governs access through Models-as-a-Service.

## Architecture

```text
OpenShift AI DataScienceCluster
  ├── Native KServe control plane
  └── Model Registry component
        ├── demo-registry + native PostgreSQL
        ├── Model Catalog
        └── Agent Catalog (Developer Preview)
OpenShift monitoring
  ├── Persistent platform Prometheus
  └── Persistent user-workload Prometheus
```

## Demo

Explore the Model Catalog and Agent Catalog, then open Model Registry to see how teams can organize model versions and artifact references. Agent Catalog discovers starter kits; it does not deploy or host agents. Stage 040 supplies the model deployments and registry records.

Browse the Governed Coding Agents source for OpenCode and Hermes. Each card
describes its runtime and links to the Stage 060 launch instructions. A catalog
entry does not deploy an agent.

## What This Stage Adds

- Native KServe serving infrastructure managed by OpenShift AI.
- The `demo-registry` instance with its operator-managed PostgreSQL database and access for the administrator and developer groups.
- Native Model Catalog and Developer Preview Agent Catalog discovery.
- Persistent OpenShift platform and user-workload monitoring for later model telemetry.

## What To Notice And Why It Matters

Registry metadata and model-serving workloads have separate lifecycles. Enabling KServe does not allocate a model or consume a GPU. Model discovery also does not certify a model's performance or compatibility; teams still qualify each model in Stage 040.

## How Red Hat And Open Source Make It Work

OpenShift AI manages KServe and the registry/catalog components through the shared DataScienceCluster. Kubernetes Jobs configure the intended component fields; native operators create and reconcile the workloads. OpenShift monitoring stores platform and user-workload metrics on persistent volumes.

## Trust Boundaries

Registry access uses the existing OpenShift identities and project groups. The default PostgreSQL database is suitable for this demo; its single-instance, non-TLS database connection is not a production HA or backup design. Registry and namespace deletion require deliberate lifecycle review because they hold metadata and persistent data.

## Red Hat Products Used

| Product | Version | Role |
|---|---|---|
| Red Hat OpenShift Container Platform | 4.22 | Native monitoring and storage |
| Red Hat OpenShift AI | 3.5 | KServe, Model Registry and Model Catalog |
| Agent Catalog | Developer Preview in RHOAI 3.5 | Agent starter-kit discovery |

## Open Source Projects To Know

KServe provides model-serving orchestration. Model Registry records models, versions and artifact references. Prometheus supplies the native metric storage and query path.

## Deploy And Validate

```bash
./stages/030-private-model-serving/deploy.sh "$GIT_REPO_BRANCH"
./stages/030-private-model-serving/validate.sh
```

Deployment uses a reviewed published revision. See [Operations](../../docs/OPERATIONS.md#stage-030) for prerequisites and the existing-cluster registry handoff. Validation checks native serving readiness, persistent monitoring and authenticated discovery APIs; actual persona and browser interaction are separate checks.

## References

- [Installing OpenShift AI 3.5](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install)
- [Enabling Model Registry and Model Catalog](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_model_registries/enabling-the-model-registry-component_managing-model-registries)
- [Dashboard configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard)
- [Developer Preview features](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes)

## Next Stage

[Stage 040 — Governed Models-as-a-Service](../040-governed-models-as-a-service/README.md)
