#!/usr/bin/env bash
# Offline source/evidence validation; only temporary files are written. No cluster, HTTP, image pulls or load.
# Usage: stages/040-governed-models-as-a-service/showback-demo/validate.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
(( $# == 0 )) || { sed -n 's/^# Usage: //p' "$0" >&2; exit 1; }
for prerequisite in bash jq curl ruby shasum kustomize; do
    command -v "$prerequisite" >/dev/null || { record "$prerequisite available" missing; validation_summary; exit 1; }
done
umask 077
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# HTTP tests install their own mocks. Any accidental real transport is refused here.
mkdir "$WORK_DIR/bin"
cat >"$WORK_DIR/bin/oc" <<'SH'
#!/usr/bin/env bash
printf '%s\n' blocked >>"$SHOWBACK_BLOCKED_TRANSPORT"
exit 99
SH
for transport in curl kubectl aws wget; do cp "$WORK_DIR/bin/oc" "$WORK_DIR/bin/$transport"; done
chmod +x "$WORK_DIR/bin/"*
export SHOWBACK_BLOCKED_TRANSPORT="$WORK_DIR/blocked-transports"
export PATH="$WORK_DIR/bin:$PATH"

shell_sources() {
    local file
    while IFS= read -r file; do bash -n "$file" || return 1; done < <(find "$SCRIPT_DIR" -type f -name '*.sh' -print)
    [[ -z "$(find "$SCRIPT_DIR" -type f -name '*.py' -print)" ]] || return 1
    if grep -REn --include='*.sh' --include='*.yaml' \
        '(^|[[:space:]/])python[0-9]*([[:space:]]|$)|\.py([[:space:]"/]|$)' \
        "$SCRIPT_DIR" >"$WORK_DIR/non-shell"; then return 1; fi
}
if shell_sources; then record 'Shell-only source and syntax' pass
else record 'Shell-only source and syntax' 'Non-shell source or invalid syntax'; fi
for suite in "$SCRIPT_DIR"/tests/test-*.sh; do
    if bash "$suite"; then record "$(basename "$suite")" pass
    else record "$(basename "$suite")" failed; fi
done
for suite in "$SCRIPT_DIR/analysis/test-analysis.sh" "$SCRIPT_DIR/offers/test-offers.sh" \
    "$SCRIPT_DIR/native/test-native.sh" "$SCRIPT_DIR/service-views/test-views.sh"; do
    if [[ -f "$suite" ]] && bash "$suite"; then record "$(basename "$(dirname "$suite")") offline contract" pass
    else record "$(basename "$(dirname "$suite")") offline contract" failed; fi
done
if "$SCRIPT_DIR/render-access.sh" --check "$SCRIPT_DIR/manifests" \
    && "$SCRIPT_DIR/generate-dashboards.sh" --check; then record 'Generated resources match shell sources' pass
else record 'Generated resources match shell sources' failed; fi
if "$SCRIPT_DIR/run-workload.sh" >"$WORK_DIR/preview.json" \
    && "$SCRIPT_DIR/run-workload.sh" --mode access-probe >"$WORK_DIR/access-preview.json"; then
    record 'Previews require no transport or credentials' pass
else record 'Previews require no transport or credentials' failed; fi

integration() {
    "$SCRIPT_DIR/collect-usage.sh" prepare \
        --run "$SCRIPT_DIR/fixtures/run.json" --receipts "$SCRIPT_DIR/fixtures/receipts.jsonl" \
        --samples "$SCRIPT_DIR/fixtures/samples.json" --metering "$SCRIPT_DIR/fixtures/metering.json" \
        --intervals "$SCRIPT_DIR/fixtures/instance-intervals.json" --output "$WORK_DIR/evidence.json" || return 1
    "$SCRIPT_DIR/allocate.sh" --input "$WORK_DIR/evidence.json" --output "$WORK_DIR/report.json" || return 1
    "$SCRIPT_DIR/publish-report.sh" --report "$WORK_DIR/report.json" --output "$WORK_DIR/report.prom" || return 1
    "$SCRIPT_DIR/archive.sh" pack --report "$WORK_DIR/report.json" \
        --file "$WORK_DIR/evidence.json" --file "$WORK_DIR/report.prom" --output "$WORK_DIR/bundle" || return 1
    "$SCRIPT_DIR/archive.sh" verify "$WORK_DIR/bundle" || return 1
    jq -e '.evidence_kind=="synthetic_fixture" and .total_cents==135 and .allocation_complete
        and .totals_by_consumer.platform_idle==45 and ([.totals_by_consumer[]]|add)==135' \
        "$WORK_DIR/report.json" >/dev/null || return 1
    grep '^showback_report_cost_cents{' "$WORK_DIR/report.prom" >/dev/null
}
if integration; then record 'Synthetic close: 135 cents, including 45 cents idle' pass
else record 'Synthetic close: 135 cents, including 45 cents idle' failed; fi
if [[ ! -e "$SHOWBACK_BLOCKED_TRANSPORT" ]]; then record 'No unmocked cluster or HTTP calls attempted' pass
else record 'No unmocked cluster or HTTP calls attempted' failed; fi
printf '%s\n' 'Not validated against a live cluster. Nothing deployed, started or pulled.'
validation_summary
