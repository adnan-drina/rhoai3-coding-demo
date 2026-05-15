# Stage 160: Modernization At Scale With MTA And Developer Lightspeed

## Why This Matters

AI-powered development at enterprise scale is not only about generating new code. Many organizations have large Java estates that need modernization, and that work requires analysis, rules, evidence, remediation, testing, and application-owner review.

This planned stage uses Migration Toolkit for Applications and Red Hat Developer Lightspeed for MTA to show a modernization workflow grounded in static analysis instead of generic chat.

## Story Goal

Analyze a legacy Java application such as Coolstore, review MTA findings, use Developer Lightspeed for MTA for targeted remediation suggestions, compare one remediation against known behavior or a reference branch, and introduce custom rules derived from corporate standards.

## Platform Capabilities Consumed

- Stage 070 provides Dev Spaces and the MTA extension handoff.
- Stage 080 provides MTA and Red Hat Developer Lightspeed for MTA.
- Stage 130 provides OpenCode agents and skills for review and standards work.
- Stage 150 provides the delivery discipline that modernization changes should eventually pass through.
- Stage 155 provides the trusted software supply-chain evidence model for artifacts produced by modernization work.

## What This Stage Adds

This planned stage adds the modernization exercise.

- Coolstore or another legacy Java application as the analysis target.
- MTA analysis checklist and findings review workflow.
- Developer Lightspeed for MTA evaluation rubric.
- Custom MTA rule generation path from corporate technical standards.
- RAG-backed or MCP-backed retrieval of corporate standards as grounded context for rule creation.
- Eval-driven review of generated rules, remediation suggestions, false positives, and false negatives.
- Scribe MCP as a candidate tool for generating and validating Konveyor/Kantra rule YAML from reviewed rule intent.
- Modernization evidence model for findings, suggestions, accepted changes, tests, and review notes.

## Developer Workflow

### Starting Point

The future live environment has MTA and Developer Lightspeed for MTA installed from Stage 080. The developer opens the legacy application in Dev Spaces and has access to the MTA VS Code extension.

The current recommendation is to use `rhpds/mca-coolstore` as the canonical brownfield modernization source for this stage. It contains Java EE modernization pressure, in-tree Konveyor profiles, a custom audit-library migration ruleset, local system-scoped JARs, and a direct connection to the `rhpds/mca-devspaces` Developer Lightspeed workspace pattern.

For the golden-path and deployment stages, the demo should still use the smaller demo-owned `coolstore-inventory-service` described in the [`Quarkus target service options`](../140-golden-path-quarkus-service/quarkus-target-service-options.md) assessment rather than promising a full monolith conversion in one live iteration.

The `rhpds/mca-devspaces` project is a candidate reference for this stage's Dev Spaces implementation. It already packages Java and MTA VS Code extensions, configures Che Code editor policy, points its devfile at `rhpds/mca-coolstore`, and injects Developer Lightspeed for MTA provider settings at workspace startup. The remaining comparison decision is whether `konveyor-ecosystem/coolstore` should stay as a secondary reference for Quarkus migration material.

This stage now has a first exercise packet:

- [`MTA Coolstore Analysis Exercise`](mta-coolstore-analysis-exercise.md)
- [`Developer Lightspeed Evaluation Rubric`](developer-lightspeed-evaluation-rubric.md)
- [`MTA Custom Rule Exercise`](mta-custom-rule-exercise.md)

The packet is still documentation-only. It does not claim that MTA analysis has been run against the current cluster or a local `mca-coolstore` checkout.

### AI-Assisted Task

The developer performs a modernization slice:

- run or review an MTA analysis;
- inspect findings in MTA UI or the VS Code extension;
- select one finding for remediation;
- request a Developer Lightspeed for MTA suggestion;
- compare the suggestion with tests and reference behavior;
- propose a custom rule from corporate standards;
- retrieve the exact corporate standard passages that justify the custom rule;
- use Scribe through MCP to generate the draft Konveyor/Kantra rule after the rule intent is reviewed;
- validate generated rule YAML before adding it to a ruleset;
- evaluate the rule against expected-good and known-bad examples;
- re-run analysis once the rule path exists.

### Prompts Or Agent Instructions

Recommended OpenCode instruction for rule work:

```text
Review this corporate Java modernization standard and propose an MTA custom rule that would detect violations. Do not apply the rule until you explain the metadata, condition, message, labels, effort, and expected false positives.
```

Recommended grounded-rule instruction:

```text
Use only the retrieved corporate standards passages as source material. Cite the passage that justifies each rule condition, then list false positives, false negatives, and test examples before proposing the MTA rule.
```

Recommended Scribe MCP instruction:

```text
Use Scribe only after you have cited the standards passage and described the expected match. Generate the smallest useful Konveyor rule, validate it with Scribe, and report expected matches, known non-matches, false-positive risk, category, effort, labels, and review evidence. Do not commit the rule until a human approves it.
```

Recommended remediation review instruction:

```text
Compare this suggested remediation with the MTA finding, project tests, and reference behavior. Identify what must be reviewed before accepting the change.
```

### Expected Developer Actions

- Run or inspect MTA analysis for the selected application.
- Choose a bounded finding.
- Request and review a Developer Lightspeed for MTA suggestion.
- Accept, reject, or edit the suggested change based on evidence.
- Draft custom MTA rule content from a selected standard.
- Check that any standards-based rule cites the retrieved source text or approved policy document.
- Use Scribe-generated YAML as a draft, not as accepted policy.
- Review rule metadata, category, effort, labels, and match conditions.
- Review expected-good and known-bad examples for the generated rule.

### Review And Quality Gates

- MTA analysis completes for the selected target.
- Findings are documented before remediation.
- Suggested code changes are reviewed as diffs.
- Tests or reference behavior support accepted changes.
- Custom rules are reviewed before use.
- Standards-derived rules cite the source standard or retrieved context.
- Scribe-generated rules pass Scribe validation and MTA validation before use.
- Rule behavior is evaluated against expected matches and known non-matches before it is promoted.
- Modernized artifacts follow the Stage 155 supply-chain evidence model before promotion.
- Model path for modernization context is recorded.

### Evidence To Capture

- Application branch or source used for analysis.
- MTA target technologies and rule sets.
- Finding selected for remediation.
- Developer Lightspeed suggestion and decision.
- Test or reference comparison.
- Custom rule draft and review notes.
- Model path and data classification.

## What To Notice And Why It Matters

The proof point is that AI assistance is grounded in modernization evidence. MTA identifies issues through rules and static analysis. Developer Lightspeed for MTA uses that context for focused suggestions. The developer still decides what to accept.

This matters because modernization at scale needs repeatability. Custom rules let enterprise standards become analysis inputs, and review evidence prevents AI-generated remediation from becoming uncontrolled rewriting.

## How Red Hat And Open Source Make It Work

Migration Toolkit for Applications provides application inventory, static analysis, rules, and IDE integration. Red Hat Developer Lightspeed for MTA adds AI-assisted code resolution based on MTA findings and context. The MTA rule system lets organizations extend analysis coverage for custom frameworks, technologies, and corporate standards.

In the reviewed MTA 8.1 documentation, Developer Lightspeed for MTA is Technology Preview. In this demo, its output should be evaluated as a suggested diff that a developer can accept, edit, reject, or defer after review.

Konveyor is the open source modernization foundation behind these workflows, and Kai is the upstream AI-assisted modernization effort associated with Developer Lightspeed-style remediation.

Red Hat's enterprise RAG, document-processing, and RAG-evaluation guidance adds a way to make corporate standards usable by agents without turning them into ungrounded prompt text. Standards can be processed, chunked, retrieved, cited, and evaluated before they influence MTA custom rules or remediation guidance.

## Trust Boundaries

Modernization context can include source code, dependency information, analysis findings, and remediation suggestions. The model path must match the data classification. Custom MTA rules should be reviewed like code because they influence what the organization treats as a modernization issue.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis and rules.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)** provides AI-assisted code resolution workflows.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the developer workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access for modernization context.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) provides the upstream modernization community.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort.
- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore) is the recommended Java modernization source for this demo.
- [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore) remains a possible secondary reference for comparison material.

## Future Implementation Notes

- Confirm the exact Stage 160 execution path for `rhpds/mca-coolstore` and whether `konveyor-ecosystem/coolstore` remains a secondary reference.
- Use the [`mca-coolstore` candidate assessment](mca-coolstore-candidate-assessment.md) as the current application-selection baseline.
- Use the [`Quarkus target service options`](../140-golden-path-quarkus-service/quarkus-target-service-options.md) assessment when comparing brownfield inventory behavior to the smaller target service.
- Decide whether to use the `rhpds/mca-devspaces` workspace pattern directly, adapt it into this repo, or keep the current Stage 070 workspace and only borrow its MTA extension setup.
- Use the [`MTA Coolstore Analysis Exercise`](mta-coolstore-analysis-exercise.md) as the first analysis checklist.
- Use the [`Developer Lightspeed Evaluation Rubric`](developer-lightspeed-evaluation-rubric.md) when reviewing suggested remediation.
- Use the [`MTA Custom Rule Exercise`](mta-custom-rule-exercise.md) as the first standards-to-rule workflow.
- Decide whether MTA rule generation should use an MCP service, a RAG-backed standards lookup, or a local reviewed skill.
- Decide whether Scribe runs locally inside Dev Spaces for the first demo or as a shared OpenShift MCP service behind MCP Gateway.
- Define an OpenCode `mta-rule-engineer` agent or skill that can call Scribe while keeping Scribe tools disabled for unrelated agents.
- Add a standards corpus ingestion step using document-processing tooling once the corporate source documents are selected.
- Add a RAG evaluation set for standards retrieval, expected rule conditions, known-bad matches, and rule false-positive review.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Migration Toolkit for Applications 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [Configuring and Using Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [Configuring and using rules for an MTA analysis](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_rules_for_an_mta_analysis/index)
- [MTA Coolstore Analysis Exercise](mta-coolstore-analysis-exercise.md)
- [Developer Lightspeed Evaluation Rubric](developer-lightspeed-evaluation-rubric.md)
- [MTA Custom Rule Exercise](mta-custom-rule-exercise.md)
- [Deploy an enterprise RAG chatbot on Red Hat OpenShift AI](https://developers.redhat.com/articles/2026/01/29/deploy-enterprise-rag-chatbot-red-hat-openshift-ai)
- [Breaking the RAG bottleneck: Scalable document processing with Ray Data and Docling](https://www.redhat.com/en/blog/breaking-rag-bottleneck-scalable-document-processing-ray-data-docling)
- [Synthetic data for RAG evaluation: Why your RAG system needs better testing](https://developers.redhat.com/articles/2026/02/23/synthetic-data-rag-evaluation-why-your-rag-system-needs-better-testing)
- [Coolstore sample application](https://github.com/konveyor-ecosystem/coolstore)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore)
- [mca-coolstore candidate assessment](mca-coolstore-candidate-assessment.md)
- [Quarkus target service options](../140-golden-path-quarkus-service/quarkus-target-service-options.md)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)

## Next Stage

[Stage 170: Agent Mesh Modernization Pattern](../170-agent-mesh-modernization-pattern/README.md) maps the single-application workflow to the Red Hat agent mesh modernization pattern.
