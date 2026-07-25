# Workshop capacity overlay: qwen3-6-35b-a3b coding worker

The demo's default posture serves ONE local model (qwen3-6-27b) on one
GPU node — measured single-stream parity with this MoE and better
quality made the second card unnecessary for presenter-driven use. This
overlay restores the 35B coding worker for multi-user hands-on sessions
(the MoE's 3B-active experts give ~3.4x aggregate throughput under
concurrent load).

To enable (before a workshop):
1. Scale the GPU machineset to 2 (see `scripts/resume-gpu-demo.sh` for
   the machineset name) and wait for the node.
2. Add `- ../optional/qwen35b-workshop` to `../base/kustomization.yaml`
   resources and re-add `qwen3-6-35b-a3b` to the Stage 040 access
   policies (devspaces-coding-models, personal-*); commit and sync.
3. Re-run the key-provisioning job (Stage 050 devspaces) so
   MAAS_API_KEY_QWEN is minted; restart workspaces to pick up the
   provider.

Reverse the steps (and scale the machineset back to 1) after the event.
