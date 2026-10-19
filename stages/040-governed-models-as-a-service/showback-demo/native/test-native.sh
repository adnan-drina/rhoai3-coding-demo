#!/usr/bin/env bash
# Offline contracts only: validate saved metadata and reject synthetic invalid variants.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
fail() { echo "Native test failed: $*" >&2; exit 1; }
bash "$SCRIPT_DIR/render-integration.sh" > "$work/preview.json"
jq -e 'length==2 and all(.[];.kind=="ConfigMap" and .metadata.annotations["demo.rhoai.io/state"]=="inert-review-inputs" and
  (.data["qualification.json"]|fromjson|.schema_fields_checked and .artifact_metadata_checked and
    .metering_backend.artifact_verified==false and .live_qualified==false))' "$work/preview.json" >/dev/null
jq -e '.[0].data["candidate.json"]|fromjson|
  .config_usage_logging_behavior=="enable_switch" and (has("tenant_patch_candidate")|not) and
  .stack_candidate.spec.storageClassName=="gp3-csi" and .stack_candidate.spec.limits.global.retention.days==30 and
  .operator_candidate.startingCSV=="loki-operator.v6.6.1"' "$work/preview.json" >/dev/null
jq -e '.[1].data["candidate.json"]|fromjson|
  .profile_target.name=="payload-processing-plugins" and .profile_target.namespace=="openshift-ingress" and
  .managed_override.activation_state=="review-only-no-patch-no-restart" and
  .profile_candidate.profiles[0].plugins.response==[{pluginRef:"external-metering-streaming"}] and
  ([.profile_candidate.plugins[]|select(.type=="external-metering-streaming")|.parameters]==[.plugin_parameters]) and
  .plugin_parameters.meteringURL=="https://metering.invalid"' "$work/preview.json" >/dev/null
bash "$SCRIPT_DIR/render-integration.sh" --check
bash "$SCRIPT_DIR/render-integration.sh" --write "$work/manifests"
for file in "$work/manifests"/*.yaml; do
    yaml_json < "$file" | jq -e 'length==1 and .[0].kind=="ConfigMap"' >/dev/null
done
printf '\n' >> "$work/manifests/showback-native-loki-inputs.yaml"
if bash "$SCRIPT_DIR/render-integration.sh" --check "$work/manifests" >/dev/null 2>&1; then fail 'rendered drift accepted'; fi

# The service-offer fixture supplies the frozen identities, prices and invoice separately.
jq '.events=[] | .agreements |= map(select(.id=="external")) |
  .cost_items |= map(select(.agreement_id=="external")) |
  .adjustments |= map(select(.agreement_id=="external"))' \
  "$SCRIPT_DIR/../offers/fixtures/month.json" > "$work/base.json"
cp "$SCRIPT_DIR/examples/events.jsonl" "$work/events.jsonl"
cp "$SCRIPT_DIR/examples/capture.json" "$work/capture.json"
import() {
    local hash
    hash=$(shasum -a 256 "$work/events.jsonl" | cut -d ' ' -f 1)
    jq --arg hash "$hash" '.source_sha256=$hash' "$work/capture.json" > "$work/bound-capture.json"
    bash "$SCRIPT_DIR/import-events.sh" --events "$work/events.jsonl" --capture "$work/bound-capture.json" --offers "$work/base.json" "$@"
}
import --output "$work/imported.json"
jq -e '.events|length==1' "$work/imported.json" >/dev/null
jq -e '.events[0].quantities=={input_uncached:80,cache_read:20,output:40} and .events[0].usage_complete and
  .native_import.identical_replays==1 and .native_import.event_evidence[0].gateway_request_id==null and
  .agreements[0].usage_coverage=="complete"' "$work/imported.json" >/dev/null
jq -e --slurpfile capture "$SCRIPT_DIR/examples/capture.json" \
  '.native_import.source_contract==$capture[0].source_contract' "$work/imported.json" >/dev/null
for mutation in '.source_contract.repository="https://example.invalid/unverified"' \
  '.source_contract.commit=("a"*40)' '.source_contract.image="unverified:latest"' \
  'del(.source_contract)|.upstream_commit="0138be54eae504e9370d6c87796cfaf0e211ba45"'; do
    jq "$mutation" "$SCRIPT_DIR/examples/capture.json" > "$work/capture.json"
    if import >/dev/null 2>&1; then fail 'unbound or legacy importer source contract accepted'; fi
done
cp "$SCRIPT_DIR/examples/capture.json" "$work/capture.json"
[[ $(stat -f '%Lp' "$work/imported.json" 2>/dev/null || stat -c '%a' "$work/imported.json") == 600 ]] || fail 'private output permission'
if import --output "$work/imported.json" >/dev/null 2>&1; then fail 'evidence replacement allowed'; fi
bash "$SCRIPT_DIR/../offers/service-report.sh" --input "$work/imported.json" --output "$work/statement.json"
jq -e '.report_type=="service_offers" and .evidence_kind=="synthetic_fixture" and (.charge_lines|length)>0' "$work/statement.json" >/dev/null

# Mutate each original immediately after shasum returns its digest. The same
# validated snapshot must still produce the same report and provenance hashes.
mkdir "$work/hash-bin"
real_shasum=$(command -v shasum)
cat > "$work/hash-bin/shasum" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
"$NATIVE_TEST_REAL_SHASUM" "$@"
for hashed; do :; done
case "$NATIVE_TEST_TARGET:$hashed" in
    events:*/events.jsonl|capture:*/capture.json|capture:*/bound-capture.json|offers:*/offers.json|offers:*/base.json)
        if [[ ! -e "$NATIVE_TEST_MUTATION_MARKER" ]]; then
            printf '%s\n' '{"mutated_after_hash":true}' > "$NATIVE_TEST_ORIGINAL"
            : > "$NATIVE_TEST_MUTATION_MARKER"
        fi
        ;;
esac
SH
chmod +x "$work/hash-bin/shasum"
cp "$work/base.json" "$work/saved-base.json"
cp "$work/bound-capture.json" "$work/saved-capture.json"
for target in events capture offers; do
    cp "$SCRIPT_DIR/examples/events.jsonl" "$work/events.jsonl"
    cp "$work/saved-capture.json" "$work/bound-capture.json"
    cp "$work/saved-base.json" "$work/base.json"
    case "$target" in
        events) original="$work/events.jsonl" ;;
        capture) original="$work/bound-capture.json" ;;
        offers) original="$work/base.json" ;;
    esac
    PATH="$work/hash-bin:$PATH" NATIVE_TEST_REAL_SHASUM="$real_shasum" NATIVE_TEST_TARGET="$target" \
      NATIVE_TEST_ORIGINAL="$original" NATIVE_TEST_MUTATION_MARKER="$work/$target-mutated" \
      bash "$SCRIPT_DIR/import-events.sh" --events "$work/events.jsonl" --capture "$work/bound-capture.json" \
      --offers "$work/base.json" > "$work/$target-snapshot.json"
    [[ -f "$work/$target-mutated" ]] || fail "mutation did not run: $target"
    jq -e '.mutated_after_hash==true' "$original" >/dev/null
    jq -e --slurpfile expected "$work/imported.json" '.==$expected[0]' "$work/$target-snapshot.json" >/dev/null
done
cp "$SCRIPT_DIR/examples/events.jsonl" "$work/events.jsonl"
cp "$work/saved-capture.json" "$work/bound-capture.json"
cp "$work/saved-base.json" "$work/base.json"

for mutation in '.requests[0].stream_done_observed=false' '.requests[0].final_usage_observed=false' '.requests[0].billing_categories_verified=false'; do
    jq "$mutation" "$SCRIPT_DIR/examples/capture.json" > "$work/capture.json"
    import > "$work/incomplete.json"
    jq -e '.events[0].usage_complete==false and .events[0].quantities=={} and .agreements[0].usage_coverage=="missing"' "$work/incomplete.json" >/dev/null
done
cp "$SCRIPT_DIR/examples/capture.json" "$work/capture.json"
for mutation in '.data.cached_input_tokens=101' '.data.total_tokens=141' '.data.cache_creation_tokens=5' '.data.prompt_tokens=-1' '.data.audio_tokens=10'; do
    jq -c "$mutation" "$SCRIPT_DIR/examples/events.jsonl" > "$work/events.jsonl"
    import > "$work/incomplete.json"
    jq -e '.events[0].usage_complete==false and .agreements[0].usage_coverage=="missing"' "$work/incomplete.json" >/dev/null
done
for mutation in '.data.user="unknown"' '.data.model="unknown"' '.type="inference.request.error"'; do
    jq -c "$mutation" "$SCRIPT_DIR/examples/events.jsonl" > "$work/events.jsonl"
    import > "$work/quarantine.json"
    jq -e '.events==[] and (.native_import.quarantined|length)==1 and .agreements[0].usage_coverage=="missing"' "$work/quarantine.json" >/dev/null
done
# A reused event id in a different source is a different event.
head -1 "$SCRIPT_DIR/examples/events.jsonl" > "$work/events.jsonl"
head -1 "$SCRIPT_DIR/examples/events.jsonl" | jq -c '.source="second-source"' >> "$work/events.jsonl"
jq '.requests += [(.requests[0]|.source="second-source")]' "$SCRIPT_DIR/examples/capture.json" > "$work/capture.json"
import > "$work/two-sources.json"
jq -e '(.events|length)==2 and (.events|map(.id)|unique|length)==2' "$work/two-sources.json" >/dev/null
# Missing delivery cannot be converted to complete zero-use coverage.
cp "$SCRIPT_DIR/examples/capture.json" "$work/capture.json"
: > "$work/events.jsonl"
import > "$work/missing.json"
jq -e '.agreements[0].usage_coverage=="missing" and (.native_import.missing_event_keys|length)==1' "$work/missing.json" >/dev/null
head -1 "$SCRIPT_DIR/examples/events.jsonl" > "$work/events.jsonl"
head -1 "$SCRIPT_DIR/examples/events.jsonl" | jq -c '.data.prompt_tokens=101' >> "$work/events.jsonl"
if import > "$work/rejected.json" 2>/dev/null; then fail 'conflicting duplicate accepted'; fi
[[ ! -s "$work/rejected.json" ]] || fail 'partial output on conflict'
printf '%s\n' '{"specversion":"1.0","specversion":"2.0"}' > "$work/events.jsonl"
if import >/dev/null 2>&1; then fail 'duplicate JSON key accepted'; fi

# Exercise the saved schemas and metadata, then synthetic invalid variants.
# No test changes the captured evidence or claims Kubernetes admission.
mkdir "$work/schemas"
cp "$SCRIPT_DIR/evidence/schemas/"*.json "$work/schemas/"
jq '.evidence_kind="synthetic_fixture"|.source="unit-test-copy"' "$SCRIPT_DIR/evidence/artifacts.json" > "$work/pins.json"
for name in config tenant lokistack; do
    digest=$(shasum -a 256 "$work/schemas/$name-crd.json" | cut -d ' ' -f 1)
    jq --arg key "$name-crd.json" --arg hash "$digest" '.schema_sha256[$key]=$hash' "$work/pins.json" > "$work/new-pins.json"
    mv "$work/new-pins.json" "$work/pins.json"
done
bash "$SCRIPT_DIR/render-integration.sh" --schema-dir "$work/schemas" --artifact-pins "$work/pins.json" > "$work/checked.json"
jq -e 'all(.[];.kind=="ConfigMap" and (.data["qualification.json"]|fromjson|.schema_fields_checked and .live_qualified==false and .evidence_kind=="synthetic_fixture"))' "$work/checked.json" >/dev/null
for name in tenant lokistack; do
    case "$name" in
        tenant) mutation='.spec.versions[].schema.openAPIV3Schema.properties.spec.properties.telemetry.properties.logs={properties:{captureUser:{type:"boolean"}}}' ;;
        lokistack) mutation='del(.spec.versions[].schema.openAPIV3Schema.properties.spec.properties.storageClassName)' ;;
    esac
    jq "$mutation" "$SCRIPT_DIR/evidence/schemas/$name-crd.json" > "$work/schemas/$name-crd.json"
    digest=$(shasum -a 256 "$work/schemas/$name-crd.json" | cut -d ' ' -f 1)
    jq --arg key "$name-crd.json" --arg hash "$digest" '.schema_sha256[$key]=$hash' "$work/pins.json" > "$work/new-pins.json"
    mv "$work/new-pins.json" "$work/pins.json"
    if bash "$SCRIPT_DIR/render-integration.sh" --schema-dir "$work/schemas" --artifact-pins "$work/pins.json" >/dev/null 2>&1; then
        fail "incompatible $name schema accepted"
    fi
    cp "$SCRIPT_DIR/evidence/schemas/"*.json "$work/schemas/"
    jq '.evidence_kind="synthetic_fixture"|.source="unit-test-copy"' "$SCRIPT_DIR/evidence/artifacts.json" > "$work/pins.json"
done
jq '.config_usage_logging_behavior="collector_selector"' "$work/pins.json" > "$work/selector-pins.json"
if bash "$SCRIPT_DIR/render-integration.sh" --schema-dir "$work/schemas" --artifact-pins "$work/selector-pins.json" >/dev/null 2>&1; then
    fail 'newer upstream logging semantics accepted for shipped release'
fi
printf '\n' >> "$work/schemas/config-crd.json"
if bash "$SCRIPT_DIR/render-integration.sh" --schema-dir "$work/schemas" --artifact-pins "$work/pins.json" >/dev/null 2>&1; then fail 'schema hash drift accepted'; fi
printf '%s\n' 'Native tests passed: inert inputs, schema metadata checks, snapshot hash binding, direct service reporting, identity/quarantine, source+id replay, categories and strict stream completeness.'
