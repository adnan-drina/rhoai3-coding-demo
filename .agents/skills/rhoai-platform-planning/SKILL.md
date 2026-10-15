---
name: rhoai-platform-planning
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when planning or reviewing the platform a fresh environment needs before
  Stage 010 (OpenShift 4.22 on AWS, RHOAI 3.5, worker sizing, default storage
  class, identity provider, object storage, GPU workers), when a README claims
  a supported OpenShift version, architecture or accelerator, or when a new
  capability adds platform prerequisites. Covers the provisioning contract in
  docs/OPERATIONS.md, the node-sizing and operator-policy guards, and the
  supported-configurations sources. Do NOT use for DSC/DSCI fields (use
  rhoai-dsci-dsc-configuration), GPU manifests (use
  rhoai-nvidia-gpu-accelerators), update channels (use rhoai-update-channels),
  feature support posture (use rhoai-release-and-support-posture), or live
  inventory (use inspect-cluster).
---

# RHOAI Platform Planning

Thin skill: this repo's platform targets and guards, with supported
configurations in the linked Red Hat sources. Detailed record:
`docs/OPERATIONS.md` (Fresh environment baseline) and `docs/PLATFORM_BASELINE.md`.

## When to use

- A new cluster is requested or inspected before `stages/010-*/deploy.sh`.
- A README, slide or skill states a supported OpenShift version, CPU
  architecture, accelerator or storage prerequisite.
- A new stage capability needs object storage, a database, GPUs or an extra
  operator.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Target OCP 4.22 on AWS (multinode); RHOAI 3.5 on x86_64. The supported-configurations article lists OCP 4.19.9+ to 4.22 for 3.5; the 3.5 install page lists fewer, so the article is the compatibility source | `docs/OPERATIONS.md` (Provisioning contract) | [Supported configurations 3.x][supcfg]; [Platform requirements][platreq] |
| Project sizing rule: every non-GPU control-plane and CPU worker node has at least 16 vCPU / 60 GiB capacity; stricter than the documented minimum and a project rule, not a Red Hat one | `require_node_sizing` in `scripts/lib.sh`, `docs/OPERATIONS.md` | [Platform requirements][platreq] |
| Operator versions are bounded by a minimum-version and channel policy (`rhods-operator` `stable-3.5`, minimum `3.5.1`) | `check_operator_policy` in `scripts/lib.sh`, `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/subscription.yaml` | [Component requirements][compreq] |
| Default dynamic storage is the cluster's `gp3-csi`; ODF adds standalone MCG (object storage) only, no Ceph block/file | `gitops/stages/010-openshift-ai-platform-foundation/010-odf/`, `docs/PLATFORM_BASELINE.md` (ODF demo storage intent) | [Platform requirements][platreq] |
| Identity provider is the environment's Keycloak (OpenID provider `rhbk`), not managed in Git; Stage 010 validate checks it | `stages/010-openshift-ai-platform-foundation/validate.sh`, `docs/OPERATIONS.md` (Ownership and stage boundaries) | [Platform requirements][platreq] |
| GPU workers: NVIDIA RTX PRO 6000 on `g7e.2xlarge` (default) and L40S on `g6e.2xlarge`, one GPU per worker, no time-slicing | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/`, `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/README.md` | [RHOAI supported accelerators][accel] |
| AutoRAG and AutoML are out of scope; a capability is not "installed" until its stage GitOps and validation exist | `docs/OPERATIONS.md` (Ownership and stage boundaries) | [Component requirements][compreq] |

Product versions and documentation versions: `.agents/references/red-hat-doc-map.yaml`
(print with `python3 .agents/tools/check-doc-links.py --versions`).

## Procedure

1. Compare the environment with the Provisioning contract table in
   `docs/OPERATIONS.md`; record exceptions there, not in this skill.
2. Check the supported-configurations article for the OCP minor and
   architecture, and the Red Hat AI accelerator table for each GPU model.
3. List the new capability's prerequisites from its component requirements
   section and map each to a stage that owns it.
4. Run the read-only guards after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   (source scripts/lib.sh && load_env && check_oc_logged_in && require_node_sizing \
     && check_operator_policy gitops/stages/010-openshift-ai-platform-foundation --verify)
   oc get clusterversion version -o jsonpath='{.status.desired.version}{"\n"}'
   oc get storageclass
   ```

5. Hand implementation to the owning component skill.

## Pitfalls

- The 3.5 install page and the supported-configurations article disagree on
  the OCP range; cite the article, dated (`docs/OPERATIONS.md` records this).
- Capacity is not allocatable; record both (`docs/OPERATIONS.md`).
- A fresh AWS cluster can report `Upgradeable=False` (`MissingRootCredential`);
  that is a provisioner issue, see `docs/TROUBLESHOOTING.md#a-fresh-cluster-is-available-but-the-baseline-has-exceptions`.
- The supported-configurations and lifecycle articles are Customer Portal
  pages, not versioned docs: quote the date you read them.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Platform and component requirements | [Requirements][req], [Platform requirements][platreq], [Component requirements][compreq] |
| Supported OCP versions and architectures | [Red Hat OpenShift AI: Supported Configurations 3.x][supcfg] (Customer Portal) |
| Accelerators and llm-d platforms | [Supported AI accelerators for OpenShift AI][accel], [llm-d supported platforms][llmd] (Red Hat AI 3) |
| Lifecycle | [Self-Managed life cycle][lifecycle] (Customer Portal) |

## Related skills

`rhoai-release-and-support-posture`, `rhoai-update-channels`,
`rhoai-self-managed-installation`, `rhoai-nvidia-gpu-accelerators`,
`odf-multicloud-gateway`, `inspect-cluster`.

[req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#requirements-for-openshift-ai-self-managed_install
[platreq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#platform_requirements
[compreq]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#component_requirements
[supcfg]: https://access.redhat.com/articles/rhoai-supported-configs-3.x
[lifecycle]: https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle
[accel]: https://docs.redhat.com/en/documentation/red_hat_ai/3/html-single/supported_product_and_hardware_configurations/index#rhoai-supported-ai-accelerators_supported-configurations
[llmd]: https://docs.redhat.com/en/documentation/red_hat_ai/3/html-single/supported_product_and_hardware_configurations/index#llmd-supported-platforms_supported-configurations
