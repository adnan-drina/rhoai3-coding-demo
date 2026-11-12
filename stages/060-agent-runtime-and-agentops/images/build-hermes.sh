#!/usr/bin/env bash
# Build the Hermes runtime image (hermes-runtime-api:0.20.5-api in ai-agents) through the GitOps-owned binary
# BuildConfig: the selected Stage 130 Hermes fork plus its hash-locked native HTTP dependency wheels. The tag is an
# output handle, never a runtime pin; the script prints the immutable image reference the Build produced.
# Changes: starts one OpenShift Build (a new image in the ai-agents ImageStream); nothing else. Safe to rerun (each run
# is a new Build of the same reviewed input). The revision is the commit 060-openshell-runtime is Synced at
# (status.sync.revision); this checkout's build inputs must equal it.
# Usage: stages/060-agent-runtime-and-agentops/images/build-hermes.sh
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
NAME=hermes-runtime-api TAG=hermes-runtime-api:0.20.5-api

# ── Read-only preflight: published revision, unchanged build inputs, GitOps-owned build objects ─────────────────────
APP_JSON=$(get applications.argoproj.io "$APP" -n openshift-gitops)
jq -e --arg repo "${GIT_REPO_URL:-https://github.com/adnan-drina/rhoai3-coding-demo.git}" --arg rev "${GIT_REPO_BRANCH:-main}" --arg path "$RUNTIME_PATH" '
  .spec as $s | $s.source == {repoURL: $repo, targetRevision: $rev, path: $path} and $s.project == "rhoai-demo"
  and $s.destination == {server: "https://kubernetes.default.svc", namespace: "openshift-gitops"}
  and (.metadata.ownerReferences // [] | length) == 0 and .operation == null and .metadata.deletionTimestamp == null
  and .status.sync.status == "Synced" and .status.operationState.phase == "Succeeded"' <<<"$APP_JSON" >/dev/null ||
  fail "$APP is not Synced at ${GIT_REPO_BRANCH:-main}"
REVISION=$(jq -r '.status.sync.revision' <<<"$APP_JSON")
git -C "$REPO_ROOT" cat-file -e "$REVISION^{commit}" 2>/dev/null || git -C "$REPO_ROOT" fetch -q --no-tags origin "${GIT_REPO_BRANCH:-main}" ||
  fail "Could not fetch ${GIT_REPO_BRANCH:-main}"
git -C "$REPO_ROOT" diff --quiet "$REVISION" -- "$SCRIPT_DIR/build-hermes.sh" "$SCRIPT_DIR/hermes-api" "$RUNTIME_PATH/hermes-images" ||
  fail "The build inputs differ from $REVISION, the commit $APP is Synced at"
for kind in buildconfig.build.openshift.io imagestream.image.openshift.io; do
  get "$kind" "$NAME" -n ai-agents | jq -e --arg app "$APP" --arg name "$NAME" '.metadata as $m
    | $m.deletionTimestamp == null and ($m.ownerReferences // [] | length) == 0
    and $m.annotations["argocd.argoproj.io/tracking-id"] == "\($app):\(.apiVersion | split("/")[0])/\(.kind):ai-agents/\($name)"' >/dev/null ||
    fail "$kind/$NAME is not owned by $APP"
done

# ── Build context: the reviewed files plus the checksum-verified wheels ─────────────────────────────────────────────
CONTEXT=$(mktemp -d "${TMPDIR:-/tmp}/hermes-runtime-api-build.XXXXXX")
trap 'rm -rf "$CONTEXT"' EXIT
for file in Dockerfile requirements.lock dependency-source.json verify-packaging.py; do
  cp "$SCRIPT_DIR/hermes-api/$file" "$CONTEXT/$file"
done
mkdir "$CONTEXT/wheels"
while IFS=$'\t' read -r url filename sha256; do
  [[ "$url" == https://files.pythonhosted.org/* && "$filename" == "$(basename "$filename")" ]] || fail "Unreviewed wheel source $filename"
  curl -fsSL --max-time 30 -o "$CONTEXT/wheels/$filename" "$url" || fail "Download failed: $filename"
  [[ $(shasum -a 256 "$CONTEXT/wheels/$filename" | cut -d' ' -f1) == "$sha256" ]] || fail "Dependency wheel checksum mismatch: $filename"
done < <(jq -r '.wheels[] | [.url, .filename, .sha256] | @tsv' "$SCRIPT_DIR/hermes-api/dependency-source.json")

# ── Build, then read back the immutable output digest ──────────────────────────────────────────────────────────────
BUILD=$(oc --request-timeout=120s start-build "$NAME" -n ai-agents --from-dir="$CONTEXT" -o name)
# A terminal failed build must not wait for the successful-completion deadline (BuildConfig: 1800 s).
phase=""
for _ in $(seq 1 370); do
  phase=$(oc --request-timeout=15s get "$BUILD" -n ai-agents -o jsonpath='{.status.phase}')
  case "$phase" in
    Complete) break ;;
    Failed|Error|Cancelled) fail "Hermes image build failed: $phase" ;;
  esac
  sleep 5
done
[[ "$phase" == Complete ]] || fail "Hermes image build deadline exceeded"
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
