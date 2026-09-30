#!/usr/bin/env bash
# Build the ws-080 workspace image with Hermes runtime patches 0001..N (N = the
# number of patches in stages/080-ai-autonomous-migration/hermes-runtime/patches),
# the outcome-board authority unchanged (commit bb66b50e, identity C), the typed
# repair executor built from the golden's pinned sources (step 2b), and the
# patched tree stamped in /opt/rhoai3/080.pins; optionally push to quay.
#
#   bash stages/080-ai-autonomous-migration/hermes-runtime/build-recipe/build-080-runtime-image.sh <expected-patched-tree>
#   bash stages/080-ai-autonomous-migration/hermes-runtime/build-recipe/build-080-runtime-image.sh <expected-patched-tree> --push
#
# This directory is the canonical, versioned build recipe (Dockerfile,
# .dockerignore, scripts/, devfile-fragments/). The build context stays the
# gitignored workspace-images/ directory, which also holds generated caches and
# downloaded inputs under out/; step 0 syncs the recipe into it and refuses a
# context whose recipe files differ afterwards, and step 6 prints the context
# identity (recipe, patches and staged inputs) that the release records.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"; cd "$R"
RECIPE=stages/080-ai-autonomous-migration/hermes-runtime/build-recipe
W=workspace-images
TREE="${1:?expected patched tree (git write-tree of base + all patches)}"
PUSH=0; [ "${2:-}" = "--push" ] && PUSH=1
BASE_SHA=fcbd1076a93841fa88855acce810e342a5b78101
COMMIT=bb66b50e98b2d87fe94d524e80c0aa7c277a13a4
C=c974f26de54e3cb8048b069bca2aa7759ef2a217514d56d2b86064ad3d0d7fbc
PREFIX_HERMES=stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes
PATCHES=stages/080-ai-autonomous-migration/hermes-runtime/patches
QUAY=quay.io/rhoai3-coding-demo/rhoai3-ws-080
N="$(ls "$PATCHES"/*.patch | wc -l | tr -d ' ')"

echo "== 0. sync the versioned recipe into the build context ($W)"
mkdir -p "$W/scripts" "$W/devfile-fragments" "$W/out"
cp "$RECIPE/Dockerfile" "$RECIPE/.dockerignore" "$W/"
cp "$RECIPE"/scripts/* "$W/scripts/"
cp "$RECIPE"/devfile-fragments/* "$W/devfile-fragments/"
for f in Dockerfile .dockerignore $(cd "$RECIPE" && ls scripts/* devfile-fragments/*); do
  cmp -s "$RECIPE/$f" "$W/$f" || { echo "STOP: $W/$f differs from the versioned recipe"; exit 1; }
done
echo "   recipe synced and verified"

echo "== 1. verify the series: base ${BASE_SHA:0:12} + ${N} patches -> ${TREE:0:12}"
V="$(mktemp -d)"; trap 'rm -rf "$V"' EXIT
git -C "$V" init -q && git -C "$V" remote add origin https://github.com/NousResearch/hermes-agent.git
git -C "$V" fetch -q --depth 1 origin "$BASE_SHA" && git -C "$V" checkout -q FETCH_HEAD
for p in "$PATCHES"/*.patch; do git -C "$V" apply --index "$R/$p"; done
got="$(git -C "$V" write-tree)"
[ "$got" = "$TREE" ] || { echo "STOP: patched tree $got != expected $TREE"; exit 1; }
echo "   series OK: $got"

echo "== 2. stage patches and the authority tree"
rm -rf "$W/out/hermes-runtime-patches"; mkdir -p "$W/out/hermes-runtime-patches"
cp "$PATCHES"/*.patch "$W/out/hermes-runtime-patches/"
rm -rf "$W/out/outcome-authority"
got="$(PYTHONDONTWRITEBYTECODE=1 python3 stages/080-ai-autonomous-migration/hermes-runtime/outcome-authority/stage-outcome-authority.py \
        --repo . --commit "$COMMIT" --prefix "$PREFIX_HERMES" --out "$W/out/outcome-authority" | tail -1)"
[ "$got" = "$C" ] || { echo "STOP: staged authority identity $got != C $C"; exit 1; }

echo "== 2b. build the typed repair executor from the pinned sources (V26-1; pins.json typed_repair)"
TR="$PREFIX_HERMES/skills/migration/fix-until-green/typed-repair"
TR_SHA="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["pins"]["typed_repair"]["executor"]["jar_sha256"])' "$PREFIX_HERMES/pins.json")"
rm -rf "$W/out/typed-repair"; mkdir -p "$W/out/typed-repair"
# the build directory is outside .hermes (a build inside it is release drift); its recipe tests run here
mvn -B -q -f "$TR/pom.xml" -Dtyped-repair.build.dir="$R/$W/out/typed-repair/build" package
mvn -B -q -f "$TR/pom.xml" dependency:list -DincludeScope=runtime -Dsort=true -DoutputFile="$R/$W/out/typed-repair/deps.txt"
python3 "$TR/scripts/license-inventory.py" "$W/out/typed-repair/deps.txt" --check > "$W/out/typed-repair/licenses.json"
cp "$W/out/typed-repair/build/typed-repair-1.0.0.jar" "$W/out/typed-repair/typed-repair.jar"
got="$(sha256sum "$W/out/typed-repair/typed-repair.jar" | cut -d' ' -f1)"
[ "$got" = "$TR_SHA" ] || { echo "STOP: typed repair jar $got != pinned $TR_SHA (a different JDK or input: re-pin deliberately)"; exit 1; }
echo "   typed repair executor ${got:0:12} staged ($(wc -c < "$W/out/typed-repair/typed-repair.jar") bytes, licenses checked)"

echo "== 3. the versioned recipe must already name this tree and patch count (no in-place rewrite)"
grep -q "^ARG HERMES_PATCHED_TREE=$TREE$" "$W/Dockerfile" || { echo "STOP: recipe Dockerfile does not pin tree $TREE"; exit 1; }
grep -q "hermes-runtime-patches/\*.patch | wc -l)\" -eq $N " "$W/Dockerfile" || { echo "STOP: recipe Dockerfile does not require $N patches"; exit 1; }
grep -q "^ARG TYPED_REPAIR_JAR_SHA256=$TR_SHA$" "$W/Dockerfile" || { echo "STOP: recipe Dockerfile does not pin typed repair jar $TR_SHA"; exit 1; }
echo "   recipe pins tree $TREE, $N patches and typed repair jar ${TR_SHA:0:12}"

echo "== 4. build (amd64 under emulation; cached layers help)"
podman machine start >/dev/null 2>&1 || true   # already running is not an error
podman info >/dev/null 2>&1 || { echo "STOP: podman is not reachable (podman machine start failed); nothing was built"; exit 1; }
OUTCOME_AUTHORITY_CODE_SHA256="$C" bash "$W/scripts/build-workspace-images.sh"

IMG=localhost/rhoai3-ws-080:unreleased
echo "== 5. read back in the built image"
# (the patch count below must equal N)
podman run --rm --platform linux/amd64 --entrypoint /bin/bash --user 1001040000:0 "$IMG" -c '
  grep "^hermes.patched_tree=" /opt/rhoai3/080.pins
  grep "^outcome_authority.code_sha256=" /opt/rhoai3/080.pins
  grep "^typed_repair.jar_sha256=" /opt/rhoai3/080.pins
  wc -l < /opt/rhoai3/hermes-runtime-patches.sha256' | tee "$W/out/runtime-readback.txt"
grep -q "^typed_repair.jar_sha256=$TR_SHA$" "$W/out/runtime-readback.txt" || { echo "STOP: typed repair stamp != $TR_SHA"; exit 1; }
grep -q "^hermes.patched_tree=$TREE$" "$W/out/runtime-readback.txt" || { echo "STOP: stamp != $TREE"; exit 1; }
grep -q "^outcome_authority.code_sha256=$C$" "$W/out/runtime-readback.txt" || { echo "STOP: authority stamp changed"; exit 1; }
[ "$(tail -1 "$W/out/runtime-readback.txt" | tr -d ' ')" = "$N" ] || { echo "STOP: baked patch count != $N"; exit 1; }
echo "   READ-BACK OK (Hermes $TREE, $N patches, authority C)"

echo "== 6. build context identity (record this in the release)"
( cd "$W" && { sha256sum Dockerfile .dockerignore scripts/*.py scripts/*.sh devfile-fragments/*; \
  find out/hermes-runtime-patches out/outcome-authority out/web_dist -type f -print0 | sort -z | xargs -0 sha256sum; \
  sha256sum out/mta-*-cli-linux-amd64.zip out/typed-repair/typed-repair.jar; } ) > "$W/out/build-context.sha256"
echo "   context identity $(sha256sum < "$W/out/build-context.sha256" | cut -c1-64) ($(wc -l < "$W/out/build-context.sha256") files)"

if [ "$PUSH" = 1 ]; then
  TAG="080-runtime-${TREE:0:8}"
  podman push --digestfile "$W/out/ws-080-${TAG}.digest" "$IMG" "docker://${QUAY}:${TAG}"
  echo "== pushed ${QUAY}:${TAG} digest $(cat "$W/out/ws-080-${TAG}.digest")"
else
  echo "== not pushed (run again with --push)"
fi
