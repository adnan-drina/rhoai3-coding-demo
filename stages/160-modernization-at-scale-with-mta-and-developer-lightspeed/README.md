# Stage 160: Modernization At Scale With MTA And Developer Lightspeed

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Enterprise AI development is not only about generating new services. Many organizations have Java estates that need modernization, and that work requires analysis, rules, remediation, testing, evidence, and application-owner review.

Stage 160 uses Migration Toolkit for Applications and Red Hat Developer Lightspeed for MTA to show modernization grounded in static analysis instead of generic chat.

## What This Stage Adds

This planned stage adds a brownfield modernization workflow.

- `rhpds/mca-coolstore` as the recommended modernization source.
- MTA findings as the evidence base for remediation.
- Developer Lightspeed for MTA suggestions reviewed as diffs, not blindly accepted changes.
- Custom rule design from corporate standards.
- A future Scribe MCP path for drafting and validating Konveyor/Kantra rules.
- Documentation-only exercise packets for analysis, remediation evaluation, and custom rules.

Exercise packet:

- [`MTA Coolstore Analysis Exercise`](mta-coolstore-analysis-exercise.md)
- [`Developer Lightspeed Evaluation Rubric`](developer-lightspeed-evaluation-rubric.md)
- [`MTA Custom Rule Exercise`](mta-custom-rule-exercise.md)

The packet does not claim that MTA analysis has run against the current cluster or a local `mca-coolstore` checkout.

## Platform Capabilities Consumed

- Stage 070 provides Dev Spaces and the MTA extension handoff.
- Stage 080 provides MTA and Developer Lightspeed for MTA.
- Stage 130 provides OpenCode agents and skills.
- Stage 150 provides delivery discipline for modernization changes.
- Stage 155 provides the supply-chain evidence model.

## Developer Workflow

The developer opens the legacy application in Dev Spaces and uses the MTA VS Code extension or MTA UI to review analysis findings.

The modernization slice should:

- run or review MTA analysis;
- inspect findings;
- select one finding for remediation;
- request a Developer Lightspeed for MTA suggestion;
- compare the suggestion with tests and reference behavior;
- propose a custom rule from corporate standards;
- cite the standards passages that justify the rule;
- validate generated rule YAML before adding it to a ruleset;
- evaluate the rule against expected-good and known-bad examples.

For golden-path and deployment stages, continue using the smaller demo-owned `coolstore-inventory-service` target rather than promising a full monolith conversion.

## Starter Prompts

```text
Review this corporate Java modernization standard and propose an MTA custom rule that would detect violations. Do not apply the rule until you explain the metadata, condition, message, labels, effort, and expected false positives.
```

```text
Use only the retrieved corporate standards passages as source material. Cite the passage that justifies each rule condition, then list false positives, false negatives, and test examples before proposing the MTA rule.
```

```text
Use Scribe only after you have cited the standards passage and described the expected match. Generate the smallest useful Konveyor rule, validate it with Scribe, and report expected matches, known non-matches, false-positive risk, category, effort, labels, and review evidence. Do not commit the rule until a human approves it.
```

```text
Compare this suggested remediation with the MTA finding, project tests, and reference behavior. Identify what must be reviewed before accepting the change.
```

## What To Notice And Why It Matters

The proof point is that AI assistance is grounded in modernization evidence. MTA identifies issues through rules and static analysis. Developer Lightspeed for MTA uses that context for focused suggestions. The developer still decides what to accept.

This matters because modernization at scale needs repeatability. Custom rules let enterprise standards become analysis inputs, and review evidence prevents AI-generated remediation from becoming uncontrolled rewriting.

## How Red Hat And Open Source Make It Work

Migration Toolkit for Applications provides application inventory, static analysis, rules, and IDE integration. Red Hat Developer Lightspeed for MTA adds AI-assisted code resolution based on MTA findings and is Technology Preview in MTA 8.1.

Konveyor is the open source modernization foundation, and Kai is the upstream AI-assisted modernization effort associated with Developer Lightspeed-style remediation.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis and rules.
- **[Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)** provides AI-assisted code resolution workflows.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the developer workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) provides the upstream modernization community.
- [Kai](https://github.com/konveyor/kai) is the upstream AI-assisted modernization effort.
- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore) is the recommended Java modernization source for this demo.
- [konveyor-ecosystem/coolstore](https://github.com/konveyor-ecosystem/coolstore) remains a possible secondary reference for comparison material.

## TODOs

- TODO: Confirm the exact execution path for `rhpds/mca-coolstore`.
- TODO: Decide whether `konveyor-ecosystem/coolstore` remains a secondary reference.
- TODO: Decide whether `rhpds/mca-devspaces` is adopted directly, adapted, or used only as a reference.
- TODO: Decide whether MTA rule generation uses Scribe MCP, a RAG-backed standards lookup, or a local reviewed skill.
- TODO: Add standards corpus ingestion only after corporate source documents are selected.
- TODO: Add a RAG evaluation set for standards retrieval and rule-condition review.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [Migration Toolkit for Applications 8.1 documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/)
- [Configuring and Using Red Hat Developer Lightspeed for MTA](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_red_hat_developer_lightspeed_for_mta/index)
- [Configuring and using rules for an MTA analysis](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_using_rules_for_an_mta_analysis/index)
- [MTA Coolstore Analysis Exercise](mta-coolstore-analysis-exercise.md)
- [Developer Lightspeed Evaluation Rubric](developer-lightspeed-evaluation-rubric.md)
- [MTA Custom Rule Exercise](mta-custom-rule-exercise.md)
- [Deploy an enterprise RAG chatbot on Red Hat OpenShift AI](https://developers.redhat.com/articles/2026/01/29/deploy-enterprise-rag-chatbot-red-hat-openshift-ai)
- [Coolstore sample application](https://github.com/konveyor-ecosystem/coolstore)
- [rhpds/mca-devspaces](https://github.com/rhpds/mca-devspaces)
- [rhpds/mca-coolstore](https://github.com/rhpds/mca-coolstore)
- [mca-coolstore candidate assessment](mca-coolstore-candidate-assessment.md)
- [Quarkus target service options](../140-golden-path-quarkus-service/quarkus-target-service-options.md)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)

## Next Stage

[Stage 170: Agent Mesh Modernization Pattern](../170-agent-mesh-modernization-pattern/README.md) maps the single-application workflow to the Red Hat agent mesh modernization pattern.
