#!/usr/bin/env bash
# Build the reviewed backend patch on an already running local Podman engine.
# Never starts a VM, runs the service, pushes an image or contacts OpenShift.
# Usage: build-local.sh --source CLEAN_PINNED_CHECKOUT --connection LOCAL_CONNECTION --output EMPTY_DIR
set -euo pipefail
umask 077
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
commit=f9a56b1769b0933e3fe7454a174b1f42a229f07a
repository=https://github.com/noyitz/ai-gateway-metering-service
source_dir=''; connection=''; output=''
fail() { printf 'Local backend build: %s\n' "$*" >&2; exit 1; }
while (($#)); do
    (($# >= 2)) || fail 'expected option/value pairs; see script usage'
    case "$1" in
        --source) source_dir=$2 ;;
        --connection) connection=$2 ;;
        --output) output=$2 ;;
        *) fail "unknown option: $1" ;;
    esac
    shift 2
done
for prerequisite in podman git jq shasum tar; do
    command -v "$prerequisite" >/dev/null || fail "missing prerequisite: $prerequisite"
done
[[ -d "$source_dir" ]] || fail 'source checkout is required'
[[ $(git -C "$source_dir" rev-parse HEAD) == "$commit" ]] || fail 'source revision differs from reviewed pin'
[[ -z $(git -C "$source_dir" status --porcelain --untracked-files=all) ]] || fail 'source checkout must be clean'
[[ "$connection" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]] || fail 'explicit local Podman connection is required'
podman system connection list --format json | jq -e --arg name "$connection" '
    [.[]|select(.Name==$name)] | length==1 and (.[0].URI |
    test("^ssh://[^/@[:space:]]+@(127[.]0[.]0[.]1|localhost|\\[::1\\]):[0-9]+/[^?#[:space:]]+$") or
    test("^unix:///[^?#[:space:]]+$"))' >/dev/null || fail 'connection must use loopback SSH or local Unix socket'
[[ -d "$output" && ! -L "$output" ]] || fail 'output must be an existing empty directory'
output=$(cd "$output" && pwd -P)
shopt -s nullglob dotglob
entries=("$output"/*)
[[ ${#entries[@]} == 0 ]] || fail 'output directory is not empty'
shopt -u nullglob dotglob
engine=(podman --connection "$connection")
"${engine[@]}" version --format json > "$output/engine.json"
cp "$0" "$output/build-local.sh"
cp "$script_dir/Containerfile" "$output/Containerfile"
cp "$script_dir/0001-metering-correctness.patch" "$output/0001-metering-correctness.patch"
patch_sha=$(shasum -a 256 "$output/0001-metering-correctness.patch" | awk '{print $1}')
image="localhost/showback-metering:${commit:0:7}-${patch_sha:0:12}"
builder="localhost/showback-metering-builder:${commit:0:7}-${patch_sha:0:12}"
git -C "$source_dir" archive "$commit" > "$output/source.tar"
mkdir "$output/context"
tar -xf "$output/source.tar" -C "$output/context"
GIT_CEILING_DIRECTORIES="$output" git -C "$output/context" apply --check "$output/0001-metering-correctness.patch"
GIT_CEILING_DIRECTORIES="$output" git -C "$output/context" apply "$output/0001-metering-correctness.patch"
started=$(date -u +%Y-%m-%dT%H:%M:%SZ)
code=0
runtime_code=0
builder_code=null
"${engine[@]}" build --platform linux/amd64 --pull=never \
    --label "org.opencontainers.image.source=$repository" \
    --label "org.opencontainers.image.revision=$commit" \
    --label "io.showback.patch.sha256=$patch_sha" \
    --tag "$image" --file "$output/Containerfile" "$output/context" > "$output/build.log" 2>&1 || runtime_code=$?
code=$runtime_code
if ((runtime_code==0)); then
    builder_code=0
    "${engine[@]}" build --platform linux/amd64 --pull=never --target builder \
        --tag "$builder" --file "$output/Containerfile" "$output/context" > "$output/builder.log" 2>&1 || builder_code=$?
    code=$builder_code
fi
jq -n --arg started "$started" --arg ended "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --argjson code "$code" \
    --argjson runtime_code "$runtime_code" --argjson builder_code "$builder_code" \
    --arg commit "$commit" --arg patch_sha "$patch_sha" --arg image "$image" --arg builder "$builder" \
    --arg source_sha "$(shasum -a 256 "$output/source.tar" | awk '{print $1}')" \
    --arg containerfile_sha "$(shasum -a 256 "$output/Containerfile" | awk '{print $1}')" \
    '{source_commit:$commit,source_archive_sha256:$source_sha,patch_sha256:$patch_sha,
      containerfile_sha256:$containerfile_sha,started:$started,ended:$ended,exit_code:$code,
      runtime_exit_code:$runtime_code,builder_exit_code:$builder_code,
      local_image:$image,local_builder:$builder,platform:"linux/amd64",published:false}' > "$output/build.json"
((code==0)) || fail "build failed; retained evidence: $output/build.json and logs"
"${engine[@]}" image inspect "$image" | jq '.[0] | {Id,Digest,Os,Architecture,Labels,Config:{User:.Config.User}}' > "$output/image.json"
printf 'Local image built: %s\nEvidence: %s/build.json\n' "$image" "$output"
