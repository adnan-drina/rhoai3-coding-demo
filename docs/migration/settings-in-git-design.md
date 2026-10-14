# Job-driven platform settings: design review (2026-10-14)

The component review proposed moving the settings that Stage 020-060 hook Jobs patch today into Git, as Stage 010 Kustomize
components switched on per stage. This note records why that is not done as proposed, and what can move.

## What the Jobs do today

| Stage | Hook (component) | Writes | Waits for first |
|---|---|---|---|
| 020 | `kueue/dsc-enablement` | DSC `kueue` Unmanaged, `autoCreateQueues: false` | Kueue operator CSV Succeeded, `kueues` CRD Established |
| 030 | `private-model-serving/dsc-enablement`, `model-discovery` | DSC `kserve`, `modelregistry`; dashboard catalog, registry, tool-calling and MCP flags | serving prerequisites |
| 040 | `maas-platform/jobs/enable-maas` | MaaS, Gen AI studio, tracing and custom-endpoint dashboard flags, `genAiStudioConfig` | MaaS operands |
| 050 | `mlflow/dsc-enablement` | DSC `trustyai`, `mlflowoperator`, `aipipelines`; `disableLMEval`, `globalProjectPrompts`, `globalMLflowNamespaces` | MLflow prerequisites |
| 060 | `mcp-platform`, `agent-console` | DSC `mcplifecycleoperator`; `agentOps` | MCP Catalog enabled |

`010-rhoai-platform` owns the `DataScienceCluster` and `OdhDashboardConfig` and lists each of those fields in
`ignoreDifferences` with `RespectIgnoreDifferences=true`; `stage_apps.delegated()` lets each stage check that its field is
delegated before writing it.

## Why the proposed change does not fit

- **One owner per object.** Argo CD annotation tracking gives each object exactly one owning Application. Later stages
  cannot also own fields of `default-dsc` or `odh-dashboard-config` in Git; two Applications applying the same object
  rewrite its tracking id and flap.
- **Staged enablement needs ordering.** Each hook waits for its own stage's operator and CRDs before it switches the
  component on. Declaring all fields in Stage 010 would enable components before their operators exist (for example Kueue
  before Stage 020 installs it) and break Stage 010 readiness.
- **Stage 010 is not re-pointed by later stages.** Activating per-stage Kustomize components on `010-rhoai-platform`
  (`spec.source.kustomize.components`) would require later stage deploys to change, and possibly re-point, the Stage 010
  Application, coupling every stage to Stage 010's revision. The deploy scripts deliberately never re-point Stage 010.

The delegation model (Stage 010 owns the singleton, later stages write named fields after their prerequisites, Argo CD
leaves exactly those fields alone) is the right pattern for shared singletons in a staged platform. Keep it.

## What can still improve

1. **Declare the Stage 050 pipeline server (`DataSciencePipelinesApplication dspa`) in Git.** It is a namespaced object
   only Stage 050 uses, so `050-model-qualification` can own it; the cluster-specific S3 endpoint would be a deploy-time
   `source.kustomize` patch, like the Stage 040 Gateway hostnames. The hook would keep only the connection Secret.
   Needs a live adoption of the existing `dspa` (tracking id, no recreation) and a pipeline-server check afterwards.
2. **Move the image-registry `defaultRoute` decision to Stage 010.** It is cluster-wide; Stage 050 only consumes it.
   The registry operator owns `configs.imageregistry.operator.openshift.io/cluster`, so it stays a narrow patch, but in
   the stage that owns platform configuration.
3. **Keep the hook Jobs small and uniform.** One shared, tested enablement script per stage that only patches its
   delegated fields after a prerequisite wait, following the hook checklist in `.agents/rules/gitops.md`; move the
   MCP and tool-calling flags from the Stage 030 discovery hook to the Stage 060 MCP hook that consumes them.
4. **Validate by delegation.** `validate-stage-flow.sh` could check that every field a hook patches is listed in
   `010-rhoai-platform` `ignoreDifferences`, and that no listed field lacks a writer (the stale `llamastackoperator`
   entry would have been caught).

Items 1-4 are tracked in `BACKLOG.md`; each needs a live adoption or behaviour check and is done one at a time.

## Outcome (2026-10-14)

- Done: item 4 (`stage_apps.py check-delegations`, run by `validate-stage-flow.sh`) and item 2 (`010-rhoai-platform`
  declares `spec.defaultRoute: true`; the Stage 050 hook only waits for the route).
- Not done: item 1. The DSPA spec needs the generated bucket name and a custom server config derived from the
  operator-generated one, which the hook patches in after creation; Git ownership would add a deploy-time patch and a
  delegated field while keeping the hook.
- Not done: item 3's flag move. Stage 060 requires the MCP Catalog to be enabled before it deploys and the Stage 040
  playground uses tool calling, so Stage 030 stays their writer. The uniform-hook goal is covered by the declared
  writes and the delegation check.
