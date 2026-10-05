#!/usr/bin/env bash
# setup-access.sh — Stage 010 platform access layer.
# Assigns existing authenticated identities to demo groups and builds the
# demo-sandbox S3 connection from the
# GitOps-provisioned ObjectBucketClaim. Run AFTER the platform is healthy
# before access acceptance, once the OBC is ready.
#
# Secret-bearing and credential-dependent steps live here, not in GitOps:
#   - rhods-admins membership (rhods-admins is operator-owned)
#   - the S3 connection secret (live OBC credentials, never committed)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Shared fail-closed environment and cluster identity guard.
REPO_ROOT="$ROOT_DIR"
# shellcheck source=../../scripts/shared/lib.sh
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in


# Use identities supplied by the existing provider. This script does not alter
# OAuth, create passwords, or manage the provider's Keycloak realm/database.
: "${RHOAI_ADMIN_USER:?Set RHOAI_ADMIN_USER to an existing authenticated administrator identity}"
: "${RHOAI_DEVELOPER_USER:?Set RHOAI_DEVELOPER_USER to an existing authenticated developer identity}"
for persona in "$RHOAI_ADMIN_USER" "$RHOAI_DEVELOPER_USER"; do
  if ! oc get user "$persona" >/dev/null 2>&1; then
    echo "Identity has not completed its first provider login; authentication remains unverified."
  fi
done
oc adm groups add-users rhods-admins "$RHOAI_ADMIN_USER"
oc adm groups add-users rhoai-developers "$RHOAI_DEVELOPER_USER"
echo "✓ Existing identities added to the demo access groups"

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

echo "✓ Platform group membership and demo-sandbox S3 connection configured"
echo "Verify access with real provider logins before declaring persona acceptance."
