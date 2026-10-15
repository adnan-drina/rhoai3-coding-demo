#!/usr/bin/env bash
# Repository gate for the demo stages (offline; the review command before any deploy).
#   Static: each stages/NNN-slug/ holds a README, an executable validate.sh and, for a GitOps stage, an executable
#   deploy.sh, and no other top-level script; every Argo CD component Application is named, labelled and placed as
#   gitops/applications/<name>.yaml -> gitops/stages/<stage>/<name>/ with a documented README; each stage renders as
#   the disjoint union of its components; Stage 010 delegations match the hook Jobs that write them; no YAML file
#   repeats a mapping key; every declared sync option survives its render; stage scripts never call the argocd CLI;
#   every shell script parses.
#   --live: the static gate, then each stage validate.sh in directory order (needs oc and .env).
# Usage: scripts/validate-stage-flow.sh [--live]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
LIVE=false
case "${1:-}" in
    --live) LIVE=true ;;
    "") ;;
    *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
esac
for cmd in oc jq ruby git; do command -v "$cmd" >/dev/null || { log_error "$cmd is required"; exit 1; }; done
cd "$REPO_ROOT"
ERRORS=0
fail() { echo -e "${RED}[FAIL]${NC} $*" >&2; ERRORS=$((ERRORS + 1)); }
READMES='["## Why","## What","## How","## Validation","## Alignment with official guidance","## References"]'
DEST='{"server":"https://kubernetes.default.svc","namespace":"openshift-gitops"}'

log_step "Stage layout"
gitops_stages=()
previous=""
for dir in stages/*/; do
    name=$(basename "$dir")
    [[ "$name" =~ ^([0-9]{3})-.+ ]] || { fail "stage directory must be NNN-slug: stages/$name"; continue; }
    id=${BASH_REMATCH[1]}
    [[ "$id" > "$previous" ]] || fail "stage ids must be unique and ascending: $id after $previous"
    previous=$id
    [[ -f "$dir/README.md" ]] || fail "stages/$name/README.md is missing"
    [[ -x "$dir/validate.sh" ]] || fail "stages/$name/validate.sh is missing or not executable"
    # One deploy script and one validate script per stage; nothing else at the stage's top level.
    while IFS= read -r extra; do
        fail "stages/$name/$extra: a stage holds only deploy.sh and validate.sh as scripts"
    done < <(find "$dir" -maxdepth 1 -type f \( -name '*.sh' -o -name '*.py' \) ! -name deploy.sh ! -name validate.sh -exec basename {} \;)
    if [[ -f "$dir/deploy.sh" ]]; then
        [[ -x "$dir/deploy.sh" ]] || fail "stages/$name/deploy.sh is not executable"
        gitops_stages+=("$name")
        [[ -f "gitops/stages/$name/kustomization.yaml" ]] || fail "gitops/stages/$name/kustomization.yaml is missing"
        compgen -G "gitops/applications/$id-*.yaml" >/dev/null || fail "stage $id has no component Applications gitops/applications/$id-*.yaml"
    fi
done
for dir in gitops/stages/*/; do
    name=$(basename "$dir")
    [[ -f "stages/$name/deploy.sh" ]] || fail "gitops/stages/$name has no matching stages/$name/deploy.sh (workflow-only stages omit GitOps)"
done

log_step "Component Applications"
names=""
for file in gitops/applications/*; do
    [[ "$file" == *.yaml && -f "$file" ]] || { fail "$file: gitops/applications/ holds only <Application name>.yaml files"; continue; }
    name=$(basename "$file" .yaml)
    app=$(yaml_json <"$file" | jq -c 'if length == 1 then .[0] else null end')
    [[ "$app" != null ]] || { fail "$file must hold exactly one Application"; continue; }
    id=${name:0:3}
    stage_dir=$(printf '%s\n' ${gitops_stages[@]+"${gitops_stages[@]}"} | grep "^$id-" || true)
    [[ -n "$stage_dir" ]] || { fail "$file has no matching stage deploy.sh"; continue; }
    path="gitops/stages/$stage_dir/$name"
    jq -e --arg n "$name" --arg id "$id" --arg path "$path" --argjson dest "$DEST" '.metadata.name == $n and ($n | startswith($id + "-"))
        and .metadata.labels["demo.rhoai.io/stage"] == $id and .spec.project == "rhoai-demo" and .spec.source.path == $path
        and .spec.destination == $dest' <<<"$app" >/dev/null ||
        fail "$file: name = file name with stage prefix, stage label $id, project rhoai-demo, source.path $path, destination openshift-gitops"
    grep -qx "$name" <<<"$names" && fail "$file: duplicate Application name"
    names+="$name"$'\n'
    # Each component documents why, what, how and its alignment with official guidance (.agents/rules/gitops.md).
    jq -e -n --argjson want "$READMES" --argjson got "$(grep -xE '## (Why|What|How|Validation|Alignment with official guidance|References)' \
        "$path/README.md" 2>/dev/null | jq -R . | jq -s -c .)" '$got == $want' >/dev/null ||
        fail "$path/README.md must exist with the headings $(jq -r 'join(", ")' <<<"$READMES") in that order"
    # A relative manifest-generate-paths entry resolves against source.path; each entry is "." or "/"-anchored and exists.
    mgp=$(jq -r '.metadata.annotations["argocd.argoproj.io/manifest-generate-paths"] // ""' <<<"$app")
    IFS=';' read -ra entries <<<"$mgp"
    for entry in ${entries[@]+"${entries[@]}"}; do
        case "$entry" in
            .) target=$path ;;
            /gitops/stages/*) target=${entry#/} ;;
            *) fail "$file: manifest-generate-paths entry '$entry' must be '.' or a '/gitops/stages/...' path"; continue ;;
        esac
        [[ -e "$target" ]] || fail "$file: manifest-generate-paths entry '$entry' resolves to $target, which does not exist"
    done
done

log_step "Stage renders, component ownership and Stage 010 delegations"
for name in ${gitops_stages[@]+"${gitops_stages[@]}"}; do
    "$REPO_ROOT/scripts/stage-apps.sh" check-static "${name:0:3}" || fail "Stage ${name:0:3} components do not render the stage"
done
"$REPO_ROOT/scripts/stage-apps.sh" check-delegations || fail "Stage 010 delegations differ from the hook Jobs"

log_step "Rendered manifests: duplicate YAML keys and retained sync options"
# Kustomize keeps the last of two equal mapping keys, so an earlier block (a second labels:) vanishes silently.
# Ruby's YAML parse tree (Psych) is the only parser that sees both; scaffolder skeletons ({{ }}, {% %}) are templates.
duplicates=$(find gitops/stages -name '*.yaml' -print0 | xargs -0 grep -L -e '{{' -e '{%' | tr '\n' '\0' | xargs -0 ruby -e '
    require "psych"
    def walk(node, file)
      if node.is_a?(Psych::Nodes::Mapping)
        seen = {}
        node.children.each_slice(2) do |k, _|
          next unless k.is_a?(Psych::Nodes::Scalar)
          puts "#{file}: duplicate key #{k.value.inspect} at line #{k.start_line + 1}" if seen[k.value]
          seen[k.value] = true
        end
      end
      (node.children || []).each { |c| walk(c, file) }
    end
    ARGV.each { |f| begin; walk(Psych.parse_stream(File.read(f)), f); rescue Psych::SyntaxError; end }')
[[ -z "$duplicates" ]] || while IFS= read -r line; do fail "$line"; done <<<"$duplicates"
# Every argocd.argoproj.io/sync-options value a source object declares survives in its render (a commonAnnotations
# writer replaces it, dropping Delete=false).
for kustomization in gitops/stages/*/*/kustomization.yaml; do
    component=$(dirname "$kustomization")
    sources=$(grep -rl --include='*.yaml' 'argocd.argoproj.io/sync-options' "$component" | xargs grep -L -e '{{' -e '{%' || true)
    [[ -n "$sources" ]] || continue
    rendered=$(oc kustomize "$component" 2>/dev/null | yaml_json) || { fail "$component: render failed"; continue; }
    while IFS= read -r source; do
        yaml_json <"$source" 2>/dev/null | jq -r --argjson r "$rendered" --arg c "$component" '.[]
            | select(type == "object" and (.metadata | type) == "object" and has("kind"))
            | (.metadata.annotations["argocd.argoproj.io/sync-options"] // "") as $want | select($want != "")
            | . as $d | $r[] | select(.kind == $d.kind and .metadata.name == $d.metadata.name
                and ($d.metadata.namespace == null or $d.metadata.namespace == .metadata.namespace))
            | (.metadata.annotations["argocd.argoproj.io/sync-options"] // "") as $got
            | (($want | split(",")) - ($got | split(","))) as $missing | select($missing | length > 0)
            | "\($c): \($d.kind)/\($d.metadata.name) loses \($missing | join(",")) in the render (rendered \"\($got)\")"' |
            while IFS= read -r line; do fail "$line"; done
    done <<<"$sources"
done

log_step "Stage scripts"
# Applications are applied, synced and waited for by scripts/stage-apps.sh (.agents/rules/gitops.md), never by the
# argocd CLI, whose core mode depends on the kube-context namespace and the client version.
if git grep -n -E '(^|[^A-Za-z_./-])argocd +(--core|app +(sync|wait|set|create))' -- 'stages/*/deploy.sh' 'stages/*/validate.sh' 'scripts/*.sh'; then
    fail "a stage script calls the argocd CLI; use scripts/stage-apps.sh apply/sync/wait"
fi
for script in scripts/*.sh stages/*/deploy.sh stages/*/validate.sh; do
    bash -n "$script" || fail "$script does not parse"
done

if (( ERRORS > 0 )); then
    log_error "Static validation found $ERRORS problem(s)"
    exit 1
fi
log_success "Static validation passed"
[[ "$LIVE" == true ]] || exit 0

load_env
check_oc_logged_in
log_step "Live stage validation"
max_rc=0
for dir in stages/*/; do
    log_step "Validating $(basename "$dir")"
    rc=0
    "$dir/validate.sh" || rc=$?
    # 0 passed, 2 passed with warnings or pending; anything else (1, a guard refusal) is a failure.
    if [[ $rc -ne 0 && $rc -ne 2 ]]; then
        [[ $rc -eq 1 ]] || log_error "$(basename "$dir")/validate.sh exited $rc"
        max_rc=1
    elif [[ $rc -eq 2 && $max_rc -eq 0 ]]; then
        max_rc=2
    fi
done
exit "$max_rc"
