#!/usr/bin/env bash
# Build the OpenCode runtime image (opencode-runtime:1.18.16 in ai-agents) through the GitOps-owned binary BuildConfig
# from the exact official release asset named in opencode/release-source.json (checksum-verified). The tag is an output
# handle, never a runtime pin; the script prints the immutable image reference the Build produced.
# Changes: starts one OpenShift Build (a new image in the ai-agents ImageStream); nothing else. Safe to rerun (each run
# is a new Build of the same reviewed input). The revision is RHOAI_STAGE060_EXPECTED_REVISION, default HEAD; it must
# be published on origin, match this checkout's build inputs, and be the revision 060-openshell-runtime is synced to.
# Usage: stages/060-agent-runtime-and-agentops/images/build-opencode.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
[[ $# -eq 0 ]] || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
load_env
check_oc_logged_in
fail() { log_error "$*"; exit 1; }
get() { oc --request-timeout=15s get "$@" -o json; }
APP=060-openshell-runtime
RUNTIME_PATH=gitops/stages/060-agent-runtime-and-agentops/060-openshell-runtime
NAME=opencode-runtime TAG=opencode-runtime:1.18.16

# ── Read-only preflight: published revision, unchanged build inputs, GitOps-owned build objects ─────────────────────
REVISION="${RHOAI_STAGE060_EXPECTED_REVISION:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || fail "The revision must be a full commit SHA"
git -C "$REPO_ROOT" ls-remote origin | awk -v revision="$REVISION" '$1 == revision { found=1 } END { exit !found }' ||
  fail "Revision $REVISION is not published on origin"
git -C "$REPO_ROOT" diff --quiet "$REVISION" -- "$SCRIPT_DIR/build-opencode.sh" "$SCRIPT_DIR/opencode" "$RUNTIME_PATH/images" ||
  fail "The build inputs differ from revision $REVISION"
SOURCE=$(jq -n -c --arg repo "${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}" --arg rev "$REVISION" --arg path "$RUNTIME_PATH" \
  '{repoURL: $repo, targetRevision: $rev, path: $path}')
get applications.argoproj.io "$APP" -n openshift-gitops | jq -e --argjson src "$SOURCE" --arg rev "$REVISION" '.spec as $s
  | $s.source == $src and $s.project == "rhoai-demo" and $s.destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}
  and (.metadata.ownerReferences // [] | length) == 0 and .operation == null and .metadata.deletionTimestamp == null
  and .status.sync.status == "Synced" and .status.sync.revision == $rev
  and .status.operationState.phase == "Succeeded" and .status.operationState.syncResult.revision == $rev
  and .status.operationState.syncResult.source == $src' >/dev/null || fail "$APP is not synced at $REVISION"
for kind in buildconfig.build.openshift.io imagestream.image.openshift.io; do
  get "$kind" "$NAME" -n ai-agents | jq -e --arg app "$APP" --arg name "$NAME" '.metadata as $m
    | $m.deletionTimestamp == null and ($m.ownerReferences // [] | length) == 0
    and $m.annotations["argocd.argoproj.io/tracking-id"] == "\($app):\(.apiVersion | split("/")[0])/\(.kind):ai-agents/\($name)"' >/dev/null ||
    fail "$kind/$NAME is not owned by $APP"
done

# ── Build context: the reviewed Dockerfile plus the single binary of the checksum-verified release archive ──────────
CONTEXT=$(mktemp -d "${TMPDIR:-/tmp}/opencode-runtime-build.XXXXXX")
trap 'rm -rf "$CONTEXT"' EXIT
RELEASE="$SCRIPT_DIR/opencode/release-source.json"
curl -fsSL --max-time 30 -o "$CONTEXT/release.tar.gz" "$(jq -r '.asset' "$RELEASE")" || fail "Release download failed"
[[ $(shasum -a 256 "$CONTEXT/release.tar.gz" | cut -d' ' -f1) == $(jq -r '.assetSha256' "$RELEASE") ]] || fail "Release archive checksum mismatch"
# Exactly one regular file named opencode.
[[ $(tar -tvzf "$CONTEXT/release.tar.gz" | awk '{ print substr($1, 1, 1), $NF }') == "- opencode" ]] || fail "Unexpected release archive"
tar -xzf "$CONTEXT/release.tar.gz" -C "$CONTEXT" opencode
rm "$CONTEXT/release.tar.gz"
cp "$SCRIPT_DIR/opencode/Dockerfile" "$CONTEXT/Dockerfile"

# ── Build, then read back the immutable output digest ──────────────────────────────────────────────────────────────
BUILD=$(oc --request-timeout=120s start-build "$NAME" -n ai-agents --from-dir="$CONTEXT" -o name)
oc --request-timeout=15s wait "$BUILD" -n ai-agents --for=jsonpath='{.status.phase}'=Complete --timeout=610s >/dev/null ||
  fail "OpenCode image build did not complete"
jq -n -e -r --slurpfile b <(get "$BUILD" -n ai-agents) --slurpfile c <(get buildconfig.build.openshift.io "$NAME" -n ai-agents) \
  --slurpfile t <(get imagestreamtag "$TAG" -n ai-agents) --slurpfile i <(get imagestream.image.openshift.io "$NAME" -n ai-agents) --arg tag "$TAG" '
  $b[0] as $b | $c[0] as $c | $t[0] as $t | $b.status.output.to.imageDigest as $d
  | if $b.status.phase == "Complete" and $b.metadata.deletionTimestamp == null
      and any($b.metadata.ownerReferences[]?; .uid == $c.metadata.uid and .kind == "BuildConfig")
      and $b.spec.output.to == {kind: "ImageStreamTag", name: $tag} and $c.spec.output.to == {kind: "ImageStreamTag", name: $tag}
      and ($d // "" | test("^sha256:[0-9a-f]{64}$"))
      and $t.image.metadata.name == $d and ($t.image.dockerImageReference | endswith("@" + $d))
    then "\($i[0].status.dockerImageRepository)@\($d)" else empty end' ||
  fail "The Build output is not the immutable image now tagged $TAG (ownership, output tag or digest differs)"
