# Item 7 Analysis: Modernization At Scale

## Scope

Define the first documentation-ready Stage 160 modernization exercise. This item does not run MTA, clone `rhpds/mca-coolstore`, create stage directories, add deploy scripts, or register stages `100-170` in `flows/default.yaml`.

## Sources Reviewed

- Local planning repository:
  - `docs/developer-workflow/README.md`
  - `docs/developer-workflow/160-modernization-at-scale-with-mta-and-developer-lightspeed.md`
  - `docs/developer-workflow/170-agent-mesh-modernization-pattern.md`
  - `docs/developer-workflow/mca-coolstore-candidate-assessment.md`
  - `docs/developer-workflow/dls-devspaces-stage-map.md`
  - `docs/developer-workflow/scribe-mcp-stage-map.md`
  - `docs/developer-workflow/quarkus-target-service-options.md`
- rh-brain reference material:
  - `wiki/demos/rhoai3-coding-demo Developer Workflow Extension.md`
  - `wiki/demos/Trusted Enterprise AI Development Platform on OpenShift AI.md`
  - `raw/Migration toolkit for applications.md`
  - `raw/Red Hat Developer Lightspeed.md`
  - `raw/Refactoring at the speed of mission An "agent mesh" approach to legacy system modernization with Red Hat AI.md`
- Official Red Hat sources checked:
  - Migration Toolkit for Applications 8.1 documentation landing page
  - MTA 8.1 command-line interface guide
  - MTA 8.1 rules guide
  - Red Hat Developer Lightspeed for MTA 8.1 guide
  - Migration Toolkit for Applications product page
  - Red Hat Developer Lightspeed for MTA product page
  - Red Hat agent mesh modernization blog

## Findings

- The current planning docs already select `rhpds/mca-coolstore` as the brownfield modernization source and keep `coolstore-inventory-service` as the smaller Quarkus target for golden-path, pipeline, and supply-chain work.
- No local `mca-coolstore` checkout was found under `/Users/adrina/Sandbox`, so this item cannot honestly record an MTA analysis result.
- MTA 8.1 supports source analysis through the CLI and produces report artifacts such as `analysis.log`, `dependencies.yaml`, `output.yaml`, and a static report. The exercise should capture those outputs as evidence after a live run.
- MTA 8.1 custom rules carry metadata such as rule ID, labels, category, effort, description, condition, and message. The custom-rule exercise should require human review of that metadata before a generated rule is used.
- Red Hat Developer Lightspeed for MTA 8.1 is documented as a Technology Preview feature. The rubric must treat its suggestions as reviewable drafts, not authoritative changes.
- Developer Lightspeed for MTA is grounded in MTA findings, source context, optional custom rule context, solved examples, and RAG-style retrieval. This fits the demo story better than generic chat because the recommendation starts from static-analysis evidence.
- The agent mesh source reinforces that brownfield modernization should measure correctness, maintainability, developer ownership, and traceability before velocity.
- Scribe remains a candidate MCP service for rule generation and validation, but not a replacement for MTA validation or human approval.

## Implementation Decision

Add documentation-only Stage 160 support files:

- `mta-coolstore-analysis-exercise.md` for the MTA analysis and evidence workflow;
- `developer-lightspeed-evaluation-rubric.md` for reviewing Developer Lightspeed suggestions;
- `mta-custom-rule-exercise.md` for standards-grounded custom rule drafting and review.

Update the Stage 160 page and developer workflow index to link the new exercise packet. Leave Stage 170 as architecture-only, but point it at the new Stage 160 evidence as the single-application input to a future agent mesh.

## Risks

- Developer Lightspeed for MTA is Technology Preview in the reviewed 8.1 docs, so demo language must avoid production-readiness claims.
- MTA output depends on the exact source revision, rules, source and target technologies, Maven access, and runtime mode. Exercise docs must require recording those inputs.
- A generated custom rule can encode a standard incorrectly, create false positives, or miss true violations. Rule-generation docs must require cited standards, known-good and known-bad examples, validation, and human approval.
- Corporate standards are not present in this repository. The first exercise must use an explicit sample passage or a human-provided approved source, and must not imply that demo placeholder text is real policy.

## Expected File Changes

- `docs/developer-workflow/item-7-modernization-at-scale-analysis.md`
- `docs/developer-workflow/mta-coolstore-analysis-exercise.md`
- `docs/developer-workflow/developer-lightspeed-evaluation-rubric.md`
- `docs/developer-workflow/mta-custom-rule-exercise.md`
- `docs/developer-workflow/README.md`
- `docs/developer-workflow/160-modernization-at-scale-with-mta-and-developer-lightspeed.md`
- `docs/developer-workflow/170-agent-mesh-modernization-pattern.md`

No executable stage structure, GitOps base, deploy script, validate script, generated MTA output, or live analysis evidence should be added by this item.
