# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Chapter title | Working with certificates |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/working-with-certificates_certs |
| Documentation category | Install |
| Retrieved date | 2026-06-09 |
| Sections used | 8.1 through 8.7.2: certificate model, cluster-wide CA, custom CA, component-specific self-signed certificate handling, Llama Stack CA bundle reference, unmanaged mode, and CA bundle removal |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and demo self-signed certificate posture |
| `.agents/skills/rhoai-self-managed-installation/SKILL.md` | DSCI and DSC installation context |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | Pipeline workflow context when DSPA CA bundle settings are used |
| `.agents/skills/rhoai-chatbot-customization/SKILL.md` | Llama Stack/RAG context when TLS trust affects provider calls |

## Source Boundaries

- Product authority: official Red Hat documentation above.
- GitOps adaptation: project policy, not a Red Hat product requirement.
- Certificate issuance, rotation, and enterprise PKI architecture are outside
  this skill unless official RHOAI docs define the exact RHOAI integration.
- Do not copy private keys, kubeconfigs, or environment-specific CA material
  into repo examples.
- If a CR field casing differs between documentation prose and active CRD,
  trust the active CRD only after recording the verification command.
