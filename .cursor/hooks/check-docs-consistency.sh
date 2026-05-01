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

# Extract step name from path
step_name=""
if [[ "$file_path" == *gitops/step-* ]]; then
    step_name=$(echo "$file_path" | grep -o 'step-[0-9]*-[a-z-]*' | head -1)
elif [[ "$file_path" == *steps/step-* ]]; then
    step_name=$(echo "$file_path" | grep -o 'step-[0-9]*-[a-z-]*' | head -1)
fi

# Only check for step-related files
if [[ -z "$step_name" ]]; then
    exit 0
fi

# Determine what was edited and what the companion is
edited_type=""
companion_hint=""

if [[ "$file_path" == *gitops/*/*.yaml ]]; then
    edited_type="manifest"
    companion_hint="steps/$step_name/README.md"
elif [[ "$file_path" == */README.md ]]; then
    edited_type="readme"
    companion_hint="gitops/$step_name/base/"
elif [[ "$file_path" == */deploy.sh ]] || [[ "$file_path" == */validate.sh ]]; then
    edited_type="script"
    companion_hint="steps/$step_name/README.md and gitops/$step_name/base/"
fi

if [[ -z "$edited_type" ]]; then
    exit 0
fi

# Check if the companion was already edited in this session
companion_edited=false
if [[ "$edited_type" == "manifest" ]]; then
    if grep -q "steps/$step_name/README.md" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
elif [[ "$edited_type" == "readme" ]]; then
    if grep -q "gitops/$step_name" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
elif [[ "$edited_type" == "script" ]]; then
    if grep -q "steps/$step_name/README.md" "$TRACK_FILE" 2>/dev/null || \
       grep -q "gitops/$step_name" "$TRACK_FILE" 2>/dev/null; then
        companion_edited=true
    fi
fi

if [[ "$companion_edited" == "false" ]]; then
    cat << EOF
{"additional_context": "REMINDER: You edited a $edited_type in $step_name but haven't touched $companion_hint yet. Code and documentation must be aligned — every change must be atomic: code + docs in the same commit."}
EOF
else
    exit 0
fi
