---
name: rhdh-diagnostic-data
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when collecting Red Hat Developer Hub 1.10 diagnostic data for a support
  case: must-gather on OpenShift, collector scope (default and opt-in), heap
  dumps, options and output layout. No repo configuration exists for it. Do NOT
  use for the repo's known RHDH failures (see docs/TROUBLESHOOTING.md) or
  metrics (use rhdh-monitoring).
---

# Developer Hub diagnostic data

Thin skill, link-only stub: the feature is not used in this repo. Product
behavior lives in the linked Developer Hub 1.10 sections.

## When to use

- A Developer Hub problem needs a support case, or memory diagnosis with a heap dump.

## Not used in this repo

The repo carries no must-gather configuration. Repo-specific RHDH failures
(catalog generator refusal, OIDC 504, Kubernetes tabs) are in
`docs/TROUBLESHOOTING.md`; read those first. must-gather output can contain
configuration values, so review it before sharing.

Adopting it is a Stage 070 change: record the decision in
`gitops/stages/070-advanced-app-platform/rhdh/README.md` and convert this stub
to a full thin skill.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Overview | [Overview][l1] |
| must-gather on OpenShift | [must-gather on OpenShift][l2] |
| Data types and scope | [Data types and scope][l3] |
| Heap dumps | [Heap dumps][l4] |
| Configuration options | [Configuration options][l5] |
| Output structure | [Output structure][l6] |

## Related skills

`rhdh-monitoring`, `rhoai-troubleshoot`.

[l1]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#diagnostic-data-collection-overview_diagnostic-data-collection
[l2]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#run-must-gather-on-openshift-to-collect-diagnostic-data_diagnostic-data-collection
[l3]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#diagnostic-data-types-and-collection-scope_diagnostic-data-collection
[l4]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#collect-heap-dumps-to-diagnose-memory-issues_diagnostic-data-collection
[l5]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#configuration-options-for-diagnostic-collection_diagnostic-data-collection
[l6]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/collect_diagnostic_data_to_streamline_support_resolution/index#diagnostic-data-output-structure-and-organization_diagnostic-data-collection
