#!/bin/bash
# afterFileEdit hook: validate kustomize build after GitOps YAML edits

input=$(cat)
file_path=$(echo "$input" | jq -r '.file_path // empty' 2>/dev/null)

# Only validate gitops YAML files
if [[ -z "$file_path" ]] || [[ "$file_path" != *gitops*/*.yaml ]]; then
    exit 0
fi

# Find the nearest kustomization.yaml
dir=$(dirname "$file_path")
while [[ "$dir" != "/" ]] && [[ ! -f "$dir/kustomization.yaml" ]]; do
    dir=$(dirname "$dir")
done

if [[ ! -f "$dir/kustomization.yaml" ]]; then
    exit 0
fi

# Run kustomize build
if ! kustomize build "$dir" > /dev/null 2>&1; then
    echo "{\"additional_context\": \"WARNING: kustomize build failed for $dir after your edit. Run 'kustomize build $dir' to see errors.\"}"
else
    exit 0
fi
