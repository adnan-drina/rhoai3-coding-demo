#!/usr/bin/env python3
"""beforeShellExecution hook: guard against destructive oc commands."""
import json
import sys

PROTECTED_NAMESPACES = {
    "redhat-ods-applications",
    "redhat-ods-operator",
    "openshift-gitops",
    "openshift-operators",
}
DESTRUCTIVE_PATTERNS = ["oc delete", "oc scale", "oc patch"]


def main():
    payload = json.load(sys.stdin)
    command = payload.get("command", "")
    response = {"continue": True, "permission": "allow"}

    is_destructive = any(pattern in command for pattern in DESTRUCTIVE_PATTERNS)
    if not is_destructive:
        print(json.dumps(response))
        return

    targets_protected = any(ns in command for ns in PROTECTED_NAMESPACES)
    if targets_protected:
        response.update({
            "permission": "ask",
            "user_message": f"Destructive command targeting protected namespace: {command}",
            "agent_message": (
                f"The command '{command}' targets a protected namespace. "
                "Confirm with the user before proceeding. For scaling operations, "
                "consider using the manage-resources skill."
            ),
        })

    print(json.dumps(response))


if __name__ == "__main__":
    main()
