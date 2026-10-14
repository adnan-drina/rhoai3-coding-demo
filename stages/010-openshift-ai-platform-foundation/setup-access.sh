#!/usr/bin/env bash
# setup-access.sh — Stage 010 platform access layer.
# Assigns existing authenticated identities to demo groups. Run AFTER the
# platform is healthy, before access acceptance.
#
# rhods-admins membership lives here, not in GitOps (rhods-admins is operator-owned).
# demo-sandbox S3 connections come from 010-sandbox-storage (Models, Workbench).
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

echo "✓ Platform group membership configured"
echo "Verify access with real provider logins before declaring persona acceptance."
