#!/usr/bin/env bash
# Normalize saved native CloudEvents into service-offer input. No network or activation.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
umask 077
usage() { echo 'Usage: import-events.sh --events FILE.jsonl --capture FILE.json --offers BASE.json [--output NEW.json]' >&2; exit 2; }
fail() { echo "Native import: $*" >&2; exit 2; }
events=''; capture=''; offers=''; output=''
while (($#)); do
    case "$1" in
        --events|--capture|--offers|--output)
            (($#>=2)) || usage
            case "$1" in --events) events=$2 ;; --capture) capture=$2 ;; --offers) offers=$2 ;; --output) output=$2 ;; esac
            shift 2 ;;
        *) usage ;;
    esac
done
[[ -f "$events" && -f "$capture" && -f "$offers" ]] || usage
[[ -z "$output" || (! -e "$output" && ! -L "$output") ]] || fail 'refusing to replace evidence'
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Read each caller-owned input once. Validation, hashes and normalization use
# these same private bytes even if an export is replaced while this run proceeds.
cat < "$events" > "$work/events.jsonl"
cat < "$capture" > "$work/capture.json"
cat < "$offers" > "$work/offers.json"
events="$work/events.jsonl"
capture="$work/capture.json"
offers="$work/offers.json"
# Same duplicate-key rejection as the service accountant; each JSONL row is one document.
strict='reduce inputs as $e ({closed:{},leaves:0};
  if ($e|length)==2 then $e[0] as $p |
    reduce range(0;($p|length)+1) as $n (. ;
      if .closed[($p[0:$n]|tojson)] then error("duplicate JSON key/document") else . end) |
    if ($e[1]|type)=="number" and (($e[1]|isnan) or ($e[1]|isinfinite)) then error("nonfinite number") else . end |
    .closed[($p|tojson)]=true | .leaves+=1
  else .closed[($e[0][0:-1]|tojson)]=true end) |
  if .leaves==0 then error("empty JSON") else true end'
for file in "$capture" "$offers"; do jq -en --stream "$strict" "$file" >/dev/null || fail 'invalid metadata JSON'; done
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -n "$line" ]] || fail 'blank JSONL row'
    printf '%s\n' "$line" | jq -en --stream "$strict" >/dev/null || fail 'invalid event JSON'
done < "$events"
events_hash=$(shasum -a 256 "$events" | cut -d ' ' -f 1)
capture_hash=$(shasum -a 256 "$capture" | cut -d ' ' -f 1)
offers_hash=$(shasum -a 256 "$offers" | cut -d ' ' -f 1)
jq -n --slurpfile events "$events" --slurpfile capture "$capture" --slurpfile base "$offers" \
    --arg events_hash "$events_hash" --arg capture_hash "$capture_hash" --arg offers_hash "$offers_hash" \
    -f "$SCRIPT_DIR/normalize-events.jq" > "$work/output.json" || fail 'contract validation failed'
if [[ -z "$output" ]]; then cat "$work/output.json"
else
    # link(2) creates a new name only; a racing existing destination cannot be overwritten.
    staged=$(mktemp "$(dirname "$output")/.native-import.XXXXXX")
    cp "$work/output.json" "$staged"
    if ! link "$staged" "$output"; then rm -f "$staged"; fail 'output already exists or cannot be created'; fi
    rm -f "$staged"
fi
