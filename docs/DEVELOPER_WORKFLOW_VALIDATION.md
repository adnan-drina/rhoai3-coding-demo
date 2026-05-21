# Developer Workflow Validation

This guide holds the quality gates and evidence expectations for the planned
developer workflow stages `100-170`. The stage READMEs explain the story; this
file explains what to verify when a stage is implemented or rehearsed.

The planned stages remain documentation-only until they have executable stage
directories, deploy scripts, validate scripts, GitOps bases, and Argo CD
applications. Do not add stages `100-170` to
[`../flows/default.yaml`](../flows/default.yaml) until that implementation
exists.

## Shared Rules

- Keep API keys, tokens, kubeconfigs, provider credentials, and full private
  route hostnames out of Git and evidence.
- Record the model path used for each AI-assisted task.
- Use the private MaaS model path for source-code, corporate standards, and
  internal architecture context unless policy explicitly approves another path.
- Treat assistant output as a proposal until a human reviews the diff and
  validation evidence.
- Keep generated documentation aligned with implemented behavior, tests, or an
  accepted spec.
- Do not treat Continue terminal execution as validated in Dev Spaces unless the
  tool returns captured output. The current remote Che Code path can write a
  command into the active terminal without executing or capturing it. For shell
  evidence, use `Terminal > New Terminal (Select a Container) >
  tooling-container`, then record the command and output.

## Stage 100: Vibes

Quality gates:

- Developer Hub opens the selected component.
- The component links are limited to `Source Repo`, `Dev Spaces`, and
  `Getting Started`.
- The `Dev Spaces` link opens a single-repository workspace for the selected
  component.
- Continue uses a workspace-local MaaS configuration rendered from platform
  provisioning.
- The opening Continue prompt completes without printing secrets, endpoint
  URLs, private hostnames, source code, or full environment variables.
- The one-shot Quarkus vibe-coding prompt creates the required POM, source,
  test, and resources files in a new directory and reports a concise sanitized
  summary. Separate terminal validation tests the app, deploys only into the
  `hello-quarkus-vibe` namespace, verifies `GET /hello`, and records sanitized
  evidence.
- A generated Quarkus app that has only `pom.xml`, reports `No tests to run`,
  or compiles with Java source/target 8 fails validation.
- Generated Quarkus files use current Red Hat build of Quarkus 3.27 guidance:
  `quarkus-rest`, `quarkus-openshift`, `quarkus-junit5`, Rest Assured tests,
  Red Hat build of Quarkus Maven plugin coordinates, and `Deployment` language.
- The assistant does not use Helm tools, list or read Kubernetes Secrets, try
  terminal execution, claim "Command executed in remote terminal", or report
  unverified deployment results.

Evidence:

- Component name.
- Workspace repository name.
- Selected model ID.
- Prompt result: pass/fail.
- Quarkus test result.
- OpenShift deployment resource names.
- Route verification result with hostname redacted.
- Blocker, if any.

Detailed live validation is in
[`techdocs/stage-100-validation.md`](techdocs/stage-100-validation.md). The
sanitized evidence template is
[`../stages/100-governed-developer-entry-point/evidence-template.md`](../stages/100-governed-developer-entry-point/evidence-template.md).

## Stage 110: Specs

Quality gates:

- Specs separate the `what` from the `how`.
- README, API, standards, and test-plan changes start from a gap list.
- Generated tests compile and pass when tests are added.
- Documentation changes describe accepted specs or implemented behavior only.

Evidence:

- Prompt summary.
- Model path.
- Accepted spec summary.
- Files changed.
- Test command and result.
- Accepted and rejected README/API/test-plan findings.

## Stage 120: Skills

Quality gates:

- The near miss exposes a real review, policy, test, or documentation gap.
- The skill candidate states when to use it, required inputs, allowed paths,
  constraints, validation steps, and expected output.
- The corrected output passes the smallest relevant validation check.

Evidence:

- Original ambiguous prompt.
- Defect or policy issue found.
- Review checklist item that caught it.
- Corrected prompt or instruction.
- Skill candidate name.
- Final validation result.

## Stage 130: Agents

Quality gates:

- Planning and review agents do not edit files.
- Editing agents are scoped to the relevant paths.
- Bash, write, web, and MCP-backed tools require approval where the task is
  sensitive.
- The agent reads the relevant specs, applies the selected skills, and reports
  validation evidence.
- PR notes disclose material AI assistance.

Evidence:

- OpenCode model path and configuration summary.
- Agent or skill used.
- Specs used.
- Plan produced before edits.
- Tool-call and MCP-call summary.
- Files changed.
- Validation command and result.

## Stage 140: Golden Path Quarkus Service

Quality gates:

- Java, Quarkus, package, dependency, and test choices match the approved
  golden path.
- Maven build and tests pass.
- Health endpoints exist where expected.
- Configuration uses environment variables, ConfigMaps, Secrets, or
  platform-provided resources instead of hard-coded credentials.
- Documentation matches implemented behavior.

Evidence:

- Approved standards used by the agent.
- Golden-path packet or software-template reference.
- Generated plan.
- Files changed.
- Build and test results.
- Dependency and secret-handling review notes.

## Stage 150: Governed Pipeline And Deployment

Quality gates:

- Pipeline YAML parses cleanly.
- No credentials are committed.
- Tests run before image build.
- Deployment does not bypass the app-local GitOps or approved platform route.
- Rollback notes are documented.

Evidence:

- Pipeline plan and template source.
- Generated `.tekton/`, `Containerfile`, and app-local GitOps files.
- Static validation output.
- PipelineRun result when live validation exists.
- GitOps handoff evidence.

## Stage 155: Trusted Software Supply Chain

Quality gates:

- SBOM, signature, provenance, scan, and policy-gate requirements are generated
  or explicitly deferred.
- Signing keys, registry credentials, and scan tokens are not committed.
- AI-generated supply-chain changes are reviewed before use.

Evidence:

- Artifact list and ownership.
- SBOM or planned SBOM location.
- Signature and provenance strategy.
- Image registry and scan result location.
- Policy decision: advisory, blocking, or deferred.
- Human approval notes.

## Stage 160: Modernization At Scale

Quality gates:

- MTA analysis completes or the blocker is recorded.
- Findings are documented before remediation.
- Developer Lightspeed suggestions are reviewed as diffs.
- Custom rules cite the source standard or retrieved context.
- Generated rule YAML passes validation before promotion.

Evidence:

- Application branch or source used for analysis.
- MTA targets and rulesets.
- Finding selected for remediation.
- Developer Lightspeed suggestion and decision.
- Test or reference comparison.
- Custom rule draft and review notes.

## Stage 170: Agent Mesh Pattern

Quality gates:

- The architecture does not claim autonomous modernization without human
  review.
- Agent outputs are traceable to source context, MTA findings, tests, and
  decisions.
- Brownfield KPIs prioritize correctness and maintainability before velocity.
- Preview or horizon technologies are labeled as future candidates.

Evidence:

- Agent-to-harness mapping.
- Evidence flow diagram.
- AgentOps trace and evaluation checkpoints.
- Human approval points.
- Supply-chain boundaries for shared agent and MCP artifacts.
- Brownfield KPI scorecard.
