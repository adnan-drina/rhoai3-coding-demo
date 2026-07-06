#!/usr/bin/env bash
# prepare-policy-benchmark-data.sh - seed chat/RAG policy benchmark CSV files.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODEL_NS="${RHOAI_MODEL_NAMESPACE:-demo-sandbox}"
GUIDELLM_DATA_PVC="${RHOAI_GUIDELLM_DATA_PVC:-benchmark-data}"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

MODEL_NS="${RHOAI_MODEL_NAMESPACE:-$MODEL_NS}"
GUIDELLM_DATA_PVC="${RHOAI_GUIDELLM_DATA_PVC:-$GUIDELLM_DATA_PVC}"

if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set." >&2
  exit 1
fi

ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match guard." >&2
  exit 1
fi

if ! oc get pvc "$GUIDELLM_DATA_PVC" -n "$MODEL_NS" --insecure-skip-tls-verify=true >/dev/null 2>&1; then
  echo "ERROR: expected benchmark data PVC ${MODEL_NS}/${GUIDELLM_DATA_PVC} is missing." >&2
  exit 1
fi

JOB_NAME="seed-stage210-policy-benchmark-data"

oc delete job "$JOB_NAME" -n "$MODEL_NS" --ignore-not-found \
  --insecure-skip-tls-verify=true >/dev/null

oc apply -f - --insecure-skip-tls-verify=true <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${JOB_NAME}
  namespace: ${MODEL_NS}
  labels:
    app.kubernetes.io/part-of: rhoai3-coding-demo
    app.kubernetes.io/name: stage210-policy-benchmark-data
    demo.rhoai.io/stage: "210"
spec:
  backoffLimit: 0
  template:
    metadata:
      labels:
        app.kubernetes.io/name: stage210-policy-benchmark-data
        demo.rhoai.io/stage: "210"
    spec:
      restartPolicy: Never
      containers:
        - name: seed
          image: registry.access.redhat.com/ubi9/ubi-minimal:latest
          command:
            - /bin/sh
            - -c
            - |
              set -eu
              cat > /tmp/seed-policy-data.sh <<'SCRIPT'
              set -eu

              write_chat() {
                printf 'prompt,output_tokens_count\n' > /data/policy-chat.csv
                i=1
                while [ "\$i" -le 160 ]; do
                  topic=\$((i % 8))
                  case "\$topic" in
                    0) domain="European banking compliance and AI platform operations"; question="How should a bank document model access controls for an internal assistant?";;
                    1) domain="insurance claims processing and regulated data handling"; question="How can an AI assistant summarize claim evidence without exposing sensitive data?";;
                    2) domain="manufacturing maintenance and private knowledge bases"; question="How should a technician ask follow up questions about a machine fault?";;
                    3) domain="public sector service delivery and auditability"; question="What evidence should be retained when an assistant answers a citizen-service question?";;
                    4) domain="healthcare operations and strict data minimization"; question="How should a clinical operations assistant handle uncertain retrieved context?";;
                    5) domain="telecommunications support and incident response"; question="How should an assistant escalate a network incident when confidence is low?";;
                    6) domain="energy trading operations and operational risk"; question="How should an assistant distinguish policy facts from operational recommendations?";;
                    *) domain="enterprise software engineering and platform reliability"; question="How should an engineering assistant explain a failed Kubernetes rollout?";;
                  esac
                  printf '"You are a private AI assistant for %s. ' "\$domain" >> /data/policy-chat.csv
                  printf 'Answer concisely for a technical enterprise user. ' >> /data/policy-chat.csv
                  printf 'Follow these rules. Ground your answer in the provided enterprise context. Call out uncertainty. Prefer safe operational guidance. Avoid exposing secrets. ' >> /data/policy-chat.csv
                  printf 'Enterprise context: the organization uses Red Hat OpenShift AI on OpenShift, GitOps, hardware profiles, model registry, vLLM model serving, and governed access policies. ' >> /data/policy-chat.csv
                  printf 'The audience includes platform engineers, architects, compliance stakeholders, and application teams. ' >> /data/policy-chat.csv
                  printf 'The answer should include a short recommendation, risk note, and next action. ' >> /data/policy-chat.csv
                  printf 'User question: %s",256\n' "\$question" >> /data/policy-chat.csv
                  i=\$((i + 1))
                done
              }

              write_rag() {
                printf 'prompt,output_tokens_count\n' > /data/policy-rag-4k.csv
                i=1
                while [ "\$i" -le 80 ]; do
                  topic=\$((i % 4))
                  case "\$topic" in
                    0) question="Summarize the access policy decision and identify the strongest operational risk.";;
                    1) question="Create an implementation checklist for the platform team based only on the retrieved context.";;
                    2) question="Explain which facts support a conservative MaaS quota for this model.";;
                    *) question="Draft a short answer for an enterprise architect and list what evidence is missing.";;
                  esac
                  printf '"You are a RAG assistant for a European regulated enterprise. Use only the retrieved context. If context is insufficient, say what is missing. ' >> /data/policy-rag-4k.csv
                  j=1
                  while [ "\$j" -le 42 ]; do
                    printf 'Retrieved passage %03d: The platform runs Red Hat OpenShift AI on OpenShift with GitOps controlled changes, one GPU-backed Nemotron endpoint, model registry metadata, vLLM metrics, Grafana dashboards, and future Models as a Service governance. Policies should protect scarce GPU capacity, limit concurrent active generations, constrain prompt and completion tokens, preserve audit evidence, and route external provider use through explicit authorization. ' "\$j" >> /data/policy-rag-4k.csv
                    j=\$((j + 1))
                  done
                  printf 'Question: %s",512\n' "\$question" >> /data/policy-rag-4k.csv
                  i=\$((i + 1))
                done
              }

              write_chat
              write_rag
              wc -l /data/policy-chat.csv /data/policy-rag-4k.csv
              SCRIPT
              /bin/sh /tmp/seed-policy-data.sh
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: ${GUIDELLM_DATA_PVC}
EOF

oc wait -n "$MODEL_NS" --for=condition=complete "job/${JOB_NAME}" \
  --timeout=5m --insecure-skip-tls-verify=true
oc logs -n "$MODEL_NS" "job/${JOB_NAME}" --insecure-skip-tls-verify=true

echo "✓ Policy benchmark data ready in ${MODEL_NS}/${GUIDELLM_DATA_PVC}:"
echo "  /data/policy-chat.csv"
echo "  /data/policy-rag-4k.csv"
