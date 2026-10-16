# GPU MachineSet generation

The GPU MachineSets in `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/` carry this cluster's AMI,
subnets, security groups and infrastructure name, so they are generated per cluster from an active CPU worker
MachineSet and committed before `deploy.sh` runs. `deploy.sh` refuses to deploy when a committed MachineSet no longer
matches the worker it was derived from.

| Script | When to run |
|---|---|
| `generate.sh [SOURCE] [--write]` | On a new cluster, or when `deploy.sh` reports that a GPU MachineSet differs from its source worker. Without `--write` it only prints the MachineSets. With `--write` it replaces the pool files and the replica exceptions in `gitops/applications/020-gpu-machinesets.yaml`; review, commit and publish them, then run `deploy.sh`. `SOURCE` defaults to `RHOAI_SOURCE_WORKER_MACHINESET`. |
