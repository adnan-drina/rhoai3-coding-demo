#!/bin/bash
# sessionStart hook: inject project context and cluster login status
# Background subshell + sleep used instead of `timeout` for macOS compatibility

context=""

oc_check() {
    oc whoami &>/dev/null 2>&1
}

# Run oc whoami with a 5s deadline (macOS doesn't have GNU timeout)
if (oc_check & OC_PID=$!; sleep 5 & SLEEP_PID=$!; wait -n $OC_PID $SLEEP_PID 2>/dev/null; kill $OC_PID $SLEEP_PID 2>/dev/null; wait $OC_PID 2>/dev/null); then
    user=$(oc whoami 2>/dev/null)
    server=$(oc whoami --show-server 2>/dev/null)
    context="Cluster: $server (logged in as $user)"
else
    context="WARNING: Not logged in to OpenShift. Run 'oc login' before cluster operations."
fi

cat << EOF
{
    "additional_context": "$context"
}
EOF
