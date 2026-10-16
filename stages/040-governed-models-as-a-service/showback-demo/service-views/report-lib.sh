#!/usr/bin/env bash
# Internal offline report helpers shared by the renderer and statement exporter; no network or cluster calls.

canonical_path() {
    local path="$1" target count=0
    while [[ -L "$path" ]]; do
        count=$((count + 1))
        [[ $count -le 40 ]] || { log_error 'Symlink cycle'; return 1; }
        target=$(readlink "$path")
        case "$target" in /*) path="$target" ;; *) path="$(dirname "$path")/$target" ;; esac
    done
    printf '%s/%s\n' "$(cd -P "$(dirname "$path")" && pwd)" "$(basename "$path")"
}

assert_output_path() {
    local output="$1" input
    shift
    [[ ! -d "$output" ]] || { log_error 'Output must be a file'; return 1; }
    mkdir -p "$(dirname "$output")"
    output=$(canonical_path "$output")
    for input in "$@"; do
        [[ -z "$input" ]] && continue
        [[ "$output" != "$(canonical_path "$input")" ]] || {
            log_error 'Output aliases an input or another output'; return 1;
        }
    done
}

atomic_copy() {
    local source="$1" destination="$2" temporary
    temporary=$(mktemp "$(dirname "$destination")/.service-view.XXXXXX")
    if ! cp "$source" "$temporary" || ! mv -f "$temporary" "$destination"; then
        rm -f "$temporary"
        return 1
    fi
}

snapshot_json() {
    cp "$1" "$2"
    jq -en --stream '
      reduce inputs as $event ({closed:{},leaves:0};
        if ($event|length)==2 then $event[0] as $path
          | reduce range(0;($path|length)+1) as $n (.;
              if .closed[($path[0:$n]|tojson)] then error("duplicate key/document") else . end)
          | .closed[($path|tojson)]=true | .leaves+=1
        else .closed[($event[0][0:-1]|tojson)]=true end)
      | select(.leaves>0)' "$2" >/dev/null || { log_error 'Ambiguous JSON'; return 1; }
    jq -se 'length == 1 and (.[0]|type) == "object"' "$2" >/dev/null || {
        log_error 'Expected exactly one JSON object'; return 1;
    }
}

json_sha256() {
    jq -cS . "$1" | shasum -a 256 | awk '{print $1}'
}

validate_report() {
    # Keep financial validation at the report's source of truth, including exact rounding and correction linkage.
    bash "$SCRIPT_DIR/../offers/service-report.sh" --check-report "$1" >/dev/null
}
