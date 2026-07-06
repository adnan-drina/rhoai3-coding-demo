# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Migration Toolkit for Applications |
| Version | 8.1 |
| Documentation category | Using the Tools |
| Official guide | Configuring and managing the Migration Toolkit for Applications user interface |
| Source URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html-single/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1/html/configuring_and_managing_the_migration_toolkit_for_applications_user_interface/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Configuring and managing the MTA user interface:

- Chapter 1: Introduction to the MTA user interface (capabilities overview,
  assessment and analysis for hybrid cloud migration)
- Chapter 2: Configuring the MTA instance environment (credentials — source
  control, Maven, proxy, Jira; repositories; proxy settings; custom migration
  targets; issue management; assessment questionnaires)
- Chapter 3: Configuring an MTA instance (stakeholders, stakeholder groups,
  business services, job functions, tag categories, tags)
- Chapter 4: Creating and configuring a Jira connection (Jira credentials,
  connection types — Cloud/Server/Datacenter, issue tracking)
- Chapter 5: Managing applications with MTA (adding applications, CSV import,
  application attributes, credentials assignment, default credentials,
  migration waves, Jira issue creation for waves)
- Chapter 6: Assessing applications with MTA (Assessment module features,
  Legacy Pathfinder default questionnaire, custom YAML questionnaires with
  conditional questions and auto-tagging, managing questionnaires, assessing
  and reviewing applications, assessment reports)
- Chapter 7: Tagging applications with MTA (creating tags, manual tagging,
  automatic tagging setup, displaying tags)
- Chapter 8: Working with archetypes (creating archetypes with criteria tags,
  archetype tags, stakeholders; assessing and reviewing archetypes)
- Chapter 9: Analyzing applications with analysis profiles (Technology Preview;
  centralized profile management from Hub, custom migration targets in
  profiles, using profiles for analysis)
- Chapter 10: Analyzing applications with MTA (configuring analysis — mode,
  targets, scope, custom rules; analysis execution; reviewing details;
  unmatched rules; downloading reports; analysis insights)
- Chapter 11: Managing MTA tasks by using Task Manager (displaying tasks,
  reviewing task logs)
- Chapter 12: Platform awareness in MTA user interface (Cloud Foundry source
  platforms, discovering/importing applications, discovery manifests, Admin
  and Migration view workflows)
- Chapter 13: Generating assets for application deployment (generators with
  Helm templates, target profiles, archetypes, asset repositories, discovery
  manifest-based asset generation)

## Source Boundaries

This skill covers the MTA user interface guide only. It provides procedures for
configuring, assessing, analyzing, and managing applications through the MTA
web console. It does not cover:

- MTA CLI usage (separate CLI guide, use mta-cli skill)
- VS Code extension configuration and usage (use mta-vscode skill)
- IntelliJ plugin configuration and usage (use mta-intellij skill)
- Developer Lightspeed AI features (use mta-lightspeed skill)
- MTA installation and operator deployment (separate Installation guide)
- Custom rule authoring syntax details (separate Rules guide)
- MTA REST API reference
- MTA architecture internals

## Platform Documented

| Platform | Notes |
|----------|-------|
| Red Hat OpenShift Container Platform | Primary deployment target |
| Cloud Foundry | Supported as source platform for platform awareness |

## Related Official Sources To Add Later

- MTA CLI Guide (mta-cli skill)
- MTA VS Code Extension Guide (mta-vscode skill)
- MTA IntelliJ Plugin Guide (mta-intellij skill)
- Developer Lightspeed Guide (mta-lightspeed skill)
- MTA Installation Guide
- MTA Rules Development Guide
