# RHOAI3 Coding Demo

**Red Hat OpenShift AI 3.4 demo on OpenShift Container Platform 4.20 — GitOps-driven, step-by-step.**

## Architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│                 GitOps-Driven AI Lifecycle                            │
│                                                                       │
│ Ingest ──→ Train ──→ Evaluate ──→ Register ──→ Deploy ──→ Monitor     │
│   ↑                                                         │         │
│   └──────────────────── Retrain ────────────────────────────┘         │
├───────────────────────────────────────────────────────────────────────┤
│                  RHOAI 3.x — AI/ML Platform                           │
├───────────────────────────────────────────────────────────────────────┤
│               OpenShift Container Platform                            │
│                                                                       │
│ NFD        NVIDIA GPU  Serverless   Service Mesh     Monitoring       │
│ Operator   Operator    (Knative)    (Istio)          (Prometheus)     │
│                                                                       │
│ Auth       GitOps    Pipelines    Data Foundation*   Streams*         │
│ Operator   (ArgoCD)  (Tekton)     (Ceph)             (Kafka)          │
├───────────────────────────────────────────────────────────────────────┤
│                        Infrastructure                                 │
└───────────────────────────────────────────────────────────────────────┘
```

## What You Need

- OpenShift 4.20+ cluster (AWS recommended)
- GPU nodes (NVIDIA L4) for model serving workloads
- Cluster admin access
- `oc` CLI installed

## Quick Start

```bash
git clone https://github.com/adnan-drina/rhoai3-coding-demo.git && cd rhoai3-coding-demo
cp env.example .env              # Edit with your config
oc login --token=<token> --server=<api>
./scripts/bootstrap.sh           # Install ArgoCD + auto-detects fork URL
```

> **Using a fork?** `bootstrap.sh` auto-detects your git remote and updates all ArgoCD Applications. No manual `sed` needed.

Deploy steps in order:

```bash
# Step 01: RHOAI Platform
./steps/step-01-rhoai/deploy.sh
```

## Step Details

| Step | Name | Capability | Ref |
|------|------|-----------|-----|
| 01 | [RHOAI Platform](steps/step-01-rhoai/README.md) | RHOAI Operator, DataScienceCluster, GenAI Studio, Hardware Profiles | [RHOAI 3.4 Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/installing_and_uninstalling_openshift_ai_self-managed/index) |

## GitOps Architecture

- **Per-step deployment** — each `deploy.sh` applies its own ArgoCD Application (`oc apply -f`), giving control over ordering and runtime setup (secrets, SCC grants, model uploads) between syncs.
- **`targetRevision: main`** — acceptable for a demo project where the single branch is the source of truth.
- **Fork-friendly** — `bootstrap.sh` auto-detects the git remote URL and updates all ArgoCD Applications. No manual URL changes needed for forks.

## Project Structure

```text
rhoai3-coding-demo/
├── scripts/                 # Bootstrap, shared shell libs, validation
│   ├── bootstrap.sh         # Install GitOps operator + configure ArgoCD
│   ├── lib.sh               # Shared logging, env, oc helpers
│   ├── validate-lib.sh      # Shared validation check functions
│   └── validate-demo-flow.sh
├── gitops/                  # Kubernetes manifests (Kustomize)
│   └── argocd/
│       └── app-of-apps/     # One ArgoCD Application per step
├── steps/                   # Per-step deploy/validate/README + app code
│   └── step-NN-<name>/
│       ├── README.md
│       ├── deploy.sh
│       └── validate.sh
├── env.example              # Template for .env
└── README.md
```

## Demo Credentials

| Username | Password | Role |
|----------|----------|------|
| `ai-admin` | `redhat123` | Service Governor (RHOAI Admin) |
| `ai-developer` | `redhat123` | Service Consumer (RHOAI User) |

## References

- [Red Hat OpenShift AI — Product Page](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat OpenShift AI — Datasheet](https://www.redhat.com/en/resources/red-hat-openshift-ai-hybrid-cloud-datasheet)
- [RHOAI 3.4 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/)
- [RHOAI 3.4 Release Notes](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/release_notes/index)
