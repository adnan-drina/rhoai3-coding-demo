#!/usr/bin/env bash
# Native Studio is enabled by Stage040; playground creation belongs to its UI.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
"$SCRIPT_DIR/validate.sh" --readiness
printf '%s\n' 'Open GenAI Studio as your project user, create a playground, and select a ready governed model endpoint/connection.' 'Studio creates its own project PostgreSQL/PVC resources. This helper does not create or patch them, configure external credentials, or deploy RAG.'
