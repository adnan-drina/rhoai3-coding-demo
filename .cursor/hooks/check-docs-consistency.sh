#!/bin/bash
# afterFileEdit hook: enforce code-docs-GitOps consistency
#
# When a gitops manifest is edited, warn if the companion README wasn't also
# edited. When a README is edited, warn if no manifest was touched.
# Tracks edits in a session-local temp file to detect partial changes.

input=$(cat)
file_path=$(echo "$input" | jq -r '.file_path // empty' 2>/dev/null)

if [[ -z "$file_path" ]]; then
    exit 0
fi

# Session tracking file (one per conversation, cleaned up by OS temp policy)
SESSION_ID=$(echo "$input" | jq -r '.conversation_id // "unknown"' 2>/dev/null)
TRACK_FILE="/tmp/cursor-edit-track-${SESSION_ID}.log"

# Record this edit
echo "$file_path" >> "$TRACK_FILE"

if [[ "$file_path" == *demo/flows/*.yaml ]]; then
    cat << EOF
{"additional_context": "REMINDER: You edited demo flow metadata. Run scripts/validate-stage-flow.sh and check README.md, docs/OPERATIONS.md, and stage READMEs for ordering or dependency changes."}
EOF
    exit 0
fi

# Extract stage or compatibility step name from path
stage_name=""
is_stage_path=false
if [[ "$file_path" == *gitops/stages/* ]]; then
    stage_name=$(echo "$file_path" | grep -o 'stages/[0-9][0-9][0-9]-[a-z0-9-]*' | cut -d/ -f2 | head -1)
    is_stage_path=true
elif [[ "$file_path" == *stages/[0-9][0-9][0-9]-* ]]; then
    stage_name=$(echo "$file_path" | grep -o 'stages/[0-9][0-9][0-9]-[a-z0-9-]*' | cut -d/ -f2 | head -1)
    is_stage_path=true
elif [[ "$file_path" == *gitops/step-* ]]; then
    stage_name=$(echo "$file_path" | grep -o 'step-[0-9]*-[a-z-]*' | head -1)
elif [[ "$file_path" == *steps/step-* ]]; then
    stage_name=$(echo "$file_path" | grep -o 'step-[0-9]*-[a-z-]*' | head -1)
fi

# Only check for stage/step-related files
if [[ -z "$stage_name" ]]; then
    exit 0
fi

# Determine what was edited and what the companion is
edited_type=""
companion_hint=""

if [[ "$file_path" == *gitops/stages/*/*.yaml ]]; then
    edited_type="manifest"
    companion_hint="stages/$stage_name/README.md"
elif [[ "$file_path" == *gitops/*/*.yaml ]]; then
    edited_type="manifest"
    companion_hint="steps/$stage_name/README.md"
elif [[ "$file_path" == */README.md ]]; then
    edited_type="readme"
    if [[ "$is_stage_path" == "true" ]]; then
        companion_hint="gitops/stages/$stage_name/base/"
    else
        companion_hint="gitops/$stage_name/base/"
    fi
elif [[ "$file_path" == */deploy.sh ]] || [[ "$file_path" == */validate.sh ]]; then
    edited_type="script"
    if [[ "$is_stage_path" == "true" ]]; then
        companion_hint="stages/$stage_name/README.md and gitops/stages/$stage_name/base/"
    else
        companion_hint="steps/$stage_name/README.md and gitops/$stage_name/base/"
    fi
fi

if [[ -z "$edited_type" ]]; then
    exit 0
fi

# Check if the companion was already edited in this session
companion_edited=false
if [[ "$edited_type" == "manifest" ]]; then
    if grep -q "stages/$stage_name/README.md" "$TRACK_FILE" 2>/dev/null || \
       grep -q "steps/$stage_name/README.md" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
elif [[ "$edited_type" == "readme" ]]; then
    if grep -q "gitops/stages/$stage_name" "$TRACK_FILE" 2>/dev/null || \
       grep -q "gitops/$stage_name" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
elif [[ "$edited_type" == "script" ]]; then
    if grep -q "stages/$stage_name/README.md" "$TRACK_FILE" 2>/dev/null || \
       grep -q "steps/$stage_name/README.md" "$TRACK_FILE" 2>/dev/null || \
       grep -q "gitops/stages/$stage_name" "$TRACK_FILE" 2>/dev/null || \
       grep -q "gitops/$stage_name" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
fi

if [[ "$companion_edited" == "false" ]]; then
    cat << EOF
{"additional_context": "REMINDER: You edited a $edited_type in $stage_name but haven't touched $companion_hint yet. Code and documentation must be aligned — every change must be atomic: code + docs in the same commit."}
EOF
else
    exit 0
fi
