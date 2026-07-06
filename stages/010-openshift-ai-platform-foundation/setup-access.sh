#!/usr/bin/env bash
# setup-access.sh — Stage 010 platform access layer.
# Creates the htpasswd identity provider with ai-admin (RHOAI admin) and
# ai-developer (regular user), and builds the demo-sandbox S3 connection from the
# GitOps-provisioned ObjectBucketClaim. Run AFTER the platform is healthy
# (./validate.sh passes) so the OBC exists.
#
# Secret-bearing and credential-dependent steps live here, not in GitOps:
#   - htpasswd secret and user passwords
#   - rhods-admins membership (rhods-admins is operator-owned)
#   - the S3 connection secret (live OBC credentials, never committed)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Load local environment ────────────────────────────────────────────────────
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

# ── OpenShift safety guard ────────────────────────────────────────────────────
if [[ -z "${RHOAI_EXPECTED_API_SERVER:-}" ]]; then
  echo "ERROR: RHOAI_EXPECTED_API_SERVER is not set in .env." >&2
  exit 1
fi
ACTUAL_SERVER=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$ACTUAL_SERVER" != *"$RHOAI_EXPECTED_API_SERVER"* ]]; then
  echo "ERROR: Active cluster ($ACTUAL_SERVER) does not match RHOAI_EXPECTED_API_SERVER." >&2
  exit 1
fi
echo "✓ Cluster guard passed: $ACTUAL_SERVER"

# openssl produces finite output and cut consumes all stdin, so no SIGPIPE under
# `set -o pipefail` (unlike `/dev/urandom | head -c`).
gen_pw() { openssl rand -base64 24 | LC_ALL=C tr -dc 'A-Za-z0-9' | cut -c1-16; }
htpasswd_entry() {  # <user> <password> -> "user:hash"
  if command -v htpasswd > /dev/null 2>&1; then
    htpasswd -nbB "$1" "$2"
  else
    echo "$1:$(openssl passwd -apr1 "$2")"
  fi
}

# ── Step 1: passwords (reuse .env values if present, else generate) ───────────
AI_ADMIN_PASSWORD="${AI_ADMIN_PASSWORD:-$(gen_pw)}"
AI_DEVELOPER_PASSWORD="${AI_DEVELOPER_PASSWORD:-$(gen_pw)}"

# ── Step 2: htpasswd secret in openshift-config ──────────────────────────────
echo ""
echo "── Step 2: Creating htpasswd secret ──"
HT_FILE=$(mktemp)
htpasswd_entry ai-admin "$AI_ADMIN_PASSWORD" >> "$HT_FILE"
htpasswd_entry ai-developer "$AI_DEVELOPER_PASSWORD" >> "$HT_FILE"
oc create secret generic htpasswd-secret \
  --from-file=htpasswd="$HT_FILE" -n openshift-config \
  --dry-run=client -o yaml | oc apply -f -
rm -f "$HT_FILE"
echo "✓ htpasswd-secret applied (ai-admin, ai-developer)"

# ── Step 3: wire the htpasswd identity provider into the cluster OAuth ────────
echo ""
echo "── Step 3: Configuring OAuth identity provider ──"
IDP_JSON='{"name":"demo-htpasswd","mappingMethod":"claim","type":"HTPasswd","htpasswd":{"fileData":{"name":"htpasswd-secret"}}}'
if oc get oauth cluster -o jsonpath='{.spec.identityProviders[*].name}' 2>/dev/null | grep -qw demo-htpasswd; then
  echo "✓ demo-htpasswd identity provider already present"
else
  if [[ -z "$(oc get oauth cluster -o jsonpath='{.spec.identityProviders}' 2>/dev/null || true)" ]]; then
    oc patch oauth cluster --type=json \
      -p "[{\"op\":\"add\",\"path\":\"/spec/identityProviders\",\"value\":[${IDP_JSON}]}]"
  else
    oc patch oauth cluster --type=json \
      -p "[{\"op\":\"add\",\"path\":\"/spec/identityProviders/-\",\"value\":${IDP_JSON}}]"
  fi
  echo "✓ demo-htpasswd identity provider added (kubeadmin retained)"
fi

# ── Step 4: group membership (RHOAI admin) ───────────────────────────────────
echo ""
echo "── Step 4: Granting RHOAI admin to ai-admin ──"
# rhods-admins is the RHOAI auth CR adminGroup (operator-owned). rhoai-developers
# is GitOps-managed and already contains ai-developer.
oc adm groups add-users rhods-admins ai-admin 2>/dev/null || true
echo "✓ ai-admin added to rhods-admins (RHOAI administrators)"

# ── Step 5: build the demo-sandbox S3 connection from the OBC ─────────────────
echo ""
echo "── Step 5: Building demo-sandbox S3 connection ──"
echo "   Waiting for ObjectBucketClaim demo-sandbox-bucket to bind …"
for _ in $(seq 1 24); do
  PHASE=$(oc get obc demo-sandbox-bucket -n demo-sandbox -o jsonpath='{.status.phase}' 2>/dev/null || true)
  [[ "$PHASE" == "Bound" ]] && break
  sleep 5
done
if [[ "${PHASE:-}" != "Bound" ]]; then
  echo "ERROR: OBC demo-sandbox-bucket is not Bound (phase=${PHASE:-missing})." >&2
  echo "       Ensure the stage-010 Argo CD Application has synced the access tree." >&2
  exit 1
fi

AKID=$(oc get secret demo-sandbox-bucket -n demo-sandbox -o go-template='{{.data.AWS_ACCESS_KEY_ID | base64decode}}')
SAK=$(oc get secret demo-sandbox-bucket -n demo-sandbox -o go-template='{{.data.AWS_SECRET_ACCESS_KEY | base64decode}}')
BUCKET=$(oc get configmap demo-sandbox-bucket -n demo-sandbox -o jsonpath='{.data.BUCKET_NAME}')
HOST=$(oc get configmap demo-sandbox-bucket -n demo-sandbox -o jsonpath='{.data.BUCKET_HOST}')
PORT=$(oc get configmap demo-sandbox-bucket -n demo-sandbox -o jsonpath='{.data.BUCKET_PORT}')

# RHOAI dashboard connection: labels + S3 connection-type fields verified against
# the cluster's pre-installed `s3` connection type configmap.
oc apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: demo-sandbox-s3
  namespace: demo-sandbox
  labels:
    opendatahub.io/dashboard: "true"
  annotations:
    opendatahub.io/connection-type-ref: s3
    openshift.io/display-name: "demo-sandbox object storage"
type: Opaque
stringData:
  AWS_ACCESS_KEY_ID: "${AKID}"
  AWS_SECRET_ACCESS_KEY: "${SAK}"
  AWS_S3_ENDPOINT: "https://${HOST}:${PORT}"
  AWS_S3_BUCKET: "${BUCKET}"
  AWS_DEFAULT_REGION: "us-east-1"
EOF
echo "✓ Connection demo-sandbox-s3 created (bucket ${BUCKET})"

# ── Step 6: persist generated passwords to .env (gitignored) ──────────────────
grep -q '^AI_ADMIN_PASSWORD=' "$ROOT_DIR/.env" 2>/dev/null || \
  echo "AI_ADMIN_PASSWORD=${AI_ADMIN_PASSWORD}" >> "$ROOT_DIR/.env"
grep -q '^AI_DEVELOPER_PASSWORD=' "$ROOT_DIR/.env" 2>/dev/null || \
  echo "AI_DEVELOPER_PASSWORD=${AI_DEVELOPER_PASSWORD}" >> "$ROOT_DIR/.env"

CONSOLE=$(oc whoami --show-console 2>/dev/null || true)
echo ""
echo "════════════════════════════════════════════════════════════════"
echo " Platform access ready"
echo "════════════════════════════════════════════════════════════════"
echo " Console:      ${CONSOLE}"
echo " Login IdP:    demo-htpasswd"
echo " ai-admin      / ${AI_ADMIN_PASSWORD}   (RHOAI administrator)"
echo " ai-developer  / ${AI_DEVELOPER_PASSWORD}   (regular user, edit on demo-sandbox)"
echo " Project:      demo-sandbox   Connection: demo-sandbox-s3"
echo " Passwords saved to .env (gitignored)."
echo "════════════════════════════════════════════════════════════════"
echo " Note: htpasswd identities appear after first login; allow ~1 min"
echo " for the OAuth pods to roll out before logging in."
