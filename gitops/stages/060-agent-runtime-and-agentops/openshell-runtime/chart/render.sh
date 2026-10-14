#!/usr/bin/env bash
set -euo pipefail
candidate_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
: "${OPENSHELL_CHART_PATH:?Provide the verified native chart archive identified by source-pins.json}"
# A complete stream is required: Helm --post-renderer excludes hook manifests.
helm template openshell "$OPENSHELL_CHART_PATH" --namespace openshell \
  --values "$candidate_dir/values.yaml" | "$candidate_dir/post-render.sh"
