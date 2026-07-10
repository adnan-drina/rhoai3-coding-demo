# Plan: Mapping adv-app-platform-demo-showroom Concepts to Demo Stages

Source: github.com/rhpds/adv-app-platform-demo-showroom (Parasol Insurance
narrative; 7 modules in 3 sections: foundational platform → advanced
developer platform → intelligent applications).

## Concept-to-stage map

| Showroom module | Concepts | Our stage | Assessment |
|---|---|---|---|
| M1 Developer experience | DevSpaces inner loop, Quarkus dev mode, devfile governance, AI code assistance, MTA as context | **050 + 060** | We're deeper: their single "AI assistant fixes code smells" beat is our whole 050→060 maturity ladder. Adoptable: one-click topology→DevSpaces entry; devfile-registry governance talking point. |
| M2 CI/CD pipeline | Tekton pipeline, SonarQube SAST gate, AI fixes the failure, GitOps deploy | **080 implementation feed + 060** | Their pipeline-fails→AI-fixes→pipeline-passes loop is the perfect 060 demo beat (skills-guided agent fixes the gate failure). Their Tekton layout feeds our 080 pipeline. |
| M3 Platform operations | Service Mesh mTLS/Kiali, HPA, Vault secrets | *gap (deliberate)* | Not core to the coding-demo thesis. Mesh 3 already underpins our gateway (010/040). Note HPA/Vault/Kiali as BACKLOG platform-ops topics only if a customer asks. |
| M4 Developer Hub | RHDH catalog, **Developer Lightspeed**, self-service software templates | **090** | Direct reuse: their template/self-service Show flows upgrade our 090 capstone (scaffold a component → lands in catalog → opens governed workspace). |
| M5 Secure development | Dependency Analytics in DevSpaces, ACS scan, **TAS signing**, SBOM, **SLSA via Tekton Chains** | **080 implementation** | This is the concrete recipe our 080 was missing: Tekton Chains + TAS + SBOM in a pipeline for the Stage 080 migrated app. Dependency Analytics plugin is a cheap 050 workspace addition. |
| M6 Supply chain | **TPA** SBOM/vuln management, RHDH topology wrap-up | **080 implementation + 090** | TPA completes the Trusted Software Factory story; topology view belongs to the 090 capstone. |
| M7 AI applications | Quarkus + LangChain4j app consuming an existing LLM (email triage), same golden path | **new exercise candidate** | The missing beat in our arc: *applications* (not just developers) consuming MaaS. A LangChain4j/Quarkus exercise against our governed endpoints fits as a 060 follow-on exercise or a BACKLOG topic "AI-enhanced application development". |

## Narrative lessons worth adopting

- **Persona journey framing**: Parasol Insurance gives every module a business
  beat ("Know/Show" structure per part). Our stages have personas
  (ai-admin/ai-developer) but READMEs lead with architecture; consider a
  one-paragraph business scene per stage README ("What the audience sees").
- **Good-to-great progression**: their 3-section structure mirrors our
  maturity ladder — validates the 050→090 arc design.
- **Fail-forward demo beats**: the pipeline *failing* on code smells is the
  memorable moment. Our equivalents (one-shot limits in 050, Kueue quota
  block, 403-before-policy) are already natural fail-forward beats — script
  them deliberately instead of avoiding them.

## Actions

1. **080 implementation phase (BACKLOG update)**: adopt M5/M6 as the
   reference recipe — Tekton pipeline for the migrated app with SonarQube
   gate, Tekton Chains SLSA attestation, TAS signing, SBOM generation, TPA
   management. Showroom pages 07/08 are the how-to source.
2. **090 scope (BACKLOG note)**: RHDH software template for self-service
   workspace/component scaffolding + topology wrap-up, per M4/M6.
3. **060 demo script**: steal the M2 beat — agent fixes a failing quality
   gate under skills; contrast with 050's one-shot attempt.
4. **050 cheap win**: add the Dependency Analytics extension to the
   workspace editor policy (M5 Part 1).
5. **New BACKLOG topic**: "AI-enhanced application development" — Quarkus +
   LangChain4j service consuming MaaS endpoints (M7 pattern) on the same
   golden path; candidate future stage after 060.
6. **Stage README polish (later)**: one business-scene paragraph per stage.
