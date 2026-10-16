#!/usr/bin/env bash
# Offline release qualification of the Stage 130 golden migration scaffold (MIGRATION-IMPROVEMENTS.md M-7): runs the
# scaffold's own qualification suites (every *.test.py and *selftest*.py under its .hermes, fixtures excluded) and its
# repeatability driver (.hermes/skills/planning/build-worklist/scripts/qualify-repeatability.py), then writes
# OUT/verdict.json with the source identity, every suite's result, the repeatability cases and the claim boundary.
# Changes only files under --out; no cluster, no model, no network beyond what a suite or producer itself needs.
# Safe to rerun (it overwrites OUT's reports). A suite that needs podman where none is on PATH, or whose last status
# line starts with SKIP, is NOT-RUN. verdict "PASS" means no suite and no repeatability case failed; it never widens a
# claim (claims.* carry the driver's MEASURED / PARTIAL / NOT-MEASURED / FAILED grading). Exit 0 PASS, 1 FAIL, 2 usage.
# Usage: stages/130-ai-autonomous-migration/qualification/qualify-release.sh --out DIR [--python PY] [--suite FILE ...] [--no-suites] [--suite-timeout SECONDS] [--no-producers] [--source DIR] [--specimen DIR] [--build-fresh DIR] [--fresh A B] [--patches A B]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
STAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCAFFOLD="$STAGE_DIR/scaffold-repo/quarkus-migration-scaffold"
DRIVER="$SCAFFOLD/.hermes/skills/planning/build-worklist/scripts/qualify-repeatability.py"

usage() { sed -n 's/^# Usage: //p' "$0" >&2; exit 2; }
OUT="" PY="" SUITE_TIMEOUT=1800 NO_SUITES=0
SUITES=()
DRIVER_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="${2:-}"; shift 2 ;;
    --python) PY="${2:-}"; shift 2 ;;
    --suite) SUITES+=("${2:-}"); shift 2 ;;
    --no-suites) NO_SUITES=1; shift ;;
    --suite-timeout) SUITE_TIMEOUT="${2:-}"; shift 2 ;;
    --no-producers) DRIVER_ARGS+=(--no-producers); shift ;;
    --source|--specimen|--build-fresh) DRIVER_ARGS+=("$1" "${2:-}"); shift 2 ;;
    --fresh|--patches) DRIVER_ARGS+=("$1" "${2:-}" "${3:-}"); shift 3 ;;
    *) usage ;;
  esac
done
[[ -n "$OUT" ]] || usage
[[ "$SUITE_TIMEOUT" =~ ^[0-9]+$ ]] || usage
if [[ -z "$PY" ]]; then
  # the worker interpreter (UDI python3 is 3.9); the host's python3 otherwise
  if command -v python3.9 >/dev/null 2>&1; then PY="python3.9"; else PY="python3"; fi
fi
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── Repeatability driver (the scaffold's own Python) ─────────────────────────
echo "== repeatability driver" >&2
DRIVER_RC=0
"$PY" "$DRIVER" --out "$OUT/repeatability.json" ${DRIVER_ARGS[@]+"${DRIVER_ARGS[@]}"} >"$OUT/repeatability.log" 2>&1 || DRIVER_RC=$?
tail -n 3 "$OUT/repeatability.log" >&2 || true

# ── Suite list ────────────────────────────────────────────────────────────────
SUITE_LIST="$OUT/suites.txt"
: >"$SUITE_LIST"
if [[ "$NO_SUITES" -eq 0 ]]; then
  if [[ "${#SUITES[@]}" -gt 0 ]]; then
    printf '%s\n' "${SUITES[@]}" >"$SUITE_LIST"
  else
    find "$SCAFFOLD/.hermes" -path '*/fixtures' -prune -o -type f \( -name '*.test.py' -o -name '*selftest*.py' \) -print |
      LC_ALL=C sort >"$SUITE_LIST"
  fi
fi

# ── Source identity ───────────────────────────────────────────────────────────
scaffold_git() { git -C "$SCAFFOLD" "$@" 2>/dev/null || true; }
prefix="$(scaffold_git rev-parse --show-prefix)"
prefix="${prefix%/}"
tree=""
[[ -z "$prefix" ]] || tree="$(scaffold_git rev-parse "HEAD:$prefix")"
dirty=false
[[ -z "$(scaffold_git status --porcelain -- .)" ]] || dirty=true
py_version="$("$PY" --version 2>&1 | sed 's/^Python //')"
jq -n --arg commit "$(scaffold_git rev-parse HEAD)" --arg path "$prefix" --arg tree "$tree" --argjson dirty "$dirty" \
  --arg python "$PY $py_version" --arg platform "$(uname -s)-$(uname -r)-$(uname -m)" \
  '{commit: $commit, scaffold_path: $path, scaffold_tree: $tree, scaffold_dirty: $dirty, python: $python, platform: $platform}' \
  >"$WORK/identity.json"

# ── Suites ────────────────────────────────────────────────────────────────────
# run_bounded SECONDS COMMAND...: run the command, killing it after SECONDS; sets TIMED_OUT and returns its exit code.
run_bounded() {
  local limit="$1" pid watchdog rc=0
  shift
  rm -f "$WORK/timed-out"
  "$@" &
  pid=$!
  # The watchdog stops its sleep when it is itself stopped, so no sleep outlives the suite.
  ( trap 'kill "$nap" 2>/dev/null; exit 0' TERM
    sleep "$limit" & nap=$!
    wait "$nap"
    kill -TERM "$pid" 2>/dev/null && touch "$WORK/timed-out" ) &
  watchdog=$!
  wait "$pid" || rc=$?
  kill -TERM "$watchdog" 2>/dev/null || true
  wait "$watchdog" 2>/dev/null || true
  TIMED_OUT=false
  [[ ! -e "$WORK/timed-out" ]] || TIMED_OUT=true
  return "$rc"
}
: >"$WORK/results.jsonl"
echo "== suites ($(wc -l <"$SUITE_LIST" | tr -d ' ')) and verdict" >&2
while IFS= read -r line; do
  [[ -n "${line//[[:space:]]/}" ]] || continue
  suite="$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  # An absolute suite path is reported relative to the stage directory; a relative one as given.
  name="$suite"
  if [[ "$suite" == /* ]]; then
    name="$(ruby -rpathname -e 'puts Pathname.new(ARGV[0]).relative_path_from(Pathname.new(ARGV[1]))' "$suite" "$STAGE_DIR")"
  fi
  if [[ ! -f "$suite" ]]; then
    jq -nc --arg s "$name" '{suite: $s, status: "FAIL", detail: "no such suite"}' >>"$WORK/results.jsonl"
  elif grep -q podman "$suite" && ! command -v podman >/dev/null 2>&1; then
    jq -nc --arg s "$name" '{suite: $s, status: "NOT-RUN", detail: "needs podman; none on PATH"}' >>"$WORK/results.jsonl"
  else
    started=$(date +%s)
    rc=0
    PYTHONDONTWRITEBYTECODE=1 run_bounded "$SUITE_TIMEOUT" "$PY" "$suite" >"$WORK/stdout" 2>"$WORK/stderr" || rc=$?
    seconds=$(( $(date +%s) - started ))
    if [[ "$TIMED_OUT" == true ]]; then
      jq -nc --arg s "$name" --argjson t "$SUITE_TIMEOUT" --argjson sec "$seconds" \
        '{suite: $s, status: "FAIL", detail: "exceeded \($t) s", seconds: $sec}' >>"$WORK/results.jsonl"
    else
      # The last OK/FAIL/SKIP/PASS line of stdout then stderr, else the last line of the trimmed output, else "rc N".
      cat "$WORK/stdout" "$WORK/stderr" | jq -Rsc --arg s "$name" --argjson rc "$rc" --argjson sec "$seconds" '
        (gsub("\r\n?"; "\n")) as $text
        | ($text | split("\n") | map(select(test("^(OK|FAIL|SKIP|PASS)")))) as $status
        | ($text | sub("^\\s+"; "") | sub("\\s+$"; "")) as $trimmed
        | (if ($status | length) > 0 then $status[-1]
           elif $trimmed != "" then $trimmed | split("\n") | last
           else "rc \($rc)" end) as $last
        | {suite: $s, status: (if $rc != 0 then "FAIL" elif ($last | startswith("SKIP")) then "NOT-RUN" else "PASS" end),
           rc: $rc, detail: $last[0:300], seconds: $sec}' >>"$WORK/results.jsonl"
    fi
  fi
  printf '%-7s %s\n' "$(tail -n 1 "$WORK/results.jsonl" | jq -r '.status')" "$name" >&2
done <"$SUITE_LIST"

# ── Verdict ───────────────────────────────────────────────────────────────────
REPORT="$OUT/repeatability.json"
if [[ -f "$REPORT" ]]; then jq -c . "$REPORT" >"$WORK/rep.json"; else echo '{}' >"$WORK/rep.json"; fi
jq -n -S --slurpfile results "$WORK/results.jsonl" --slurpfile rep "$WORK/rep.json" --slurpfile identity "$WORK/identity.json" \
  --argjson driver_rc "$DRIVER_RC" --arg report "$REPORT" '
  $rep[0] as $rep | ($rep.cases // []) as $cases | ($rep.claim_boundary // {}) as $boundary
  | [$cases[] | select(.status == "FAIL") | .case] as $failed_cases
  | [$results[] | select(.status == "FAIL") | .suite] as $failed_suites
  | ($driver_rc == 0 and ($rep | length) > 0) as $driver_ok
  | {schema: "rhoai3.release-qualification-verdict/v1",
     verdict: (if $driver_ok and ($failed_suites | length) == 0 and ($failed_cases | length) == 0 then "PASS" else "FAIL" end),
     meaning: ("PASS: no suite and no repeatability case failed. It establishes only what claims.* grade MEASURED; "
               + "a NOT-RUN case or suite is listed, never counted as a pass."),
     identity: $identity[0],
     suites: {total: ($results | length), pass: ([$results[] | select(.status == "PASS")] | length),
              not_run: [$results[] | select(.status == "NOT-RUN")], failed: $failed_suites, results: $results},
     repeatability: {driver_rc: $driver_rc, report: (if ($rep | length) > 0 then $report else "" end),
                     pass: ([$cases[] | select(.status == "PASS")] | length),
                     not_run: [$cases[] | select(.status == "NOT-RUN") | {case, detail}],
                     failed: $failed_cases},
     claims: ($boundary.claims // ([ "repeatable_planning", "repeatable_transformations", "repeatable_migration"]
       | map({key: ., value: {status: "NOT-MEASURED",
           missing: ["the repeatability driver produced no report (rc \($driver_rc))"]}}) | from_entries)),
     claim_boundary: {covers: $boundary.covers, does_not_cover: $boundary.does_not_cover}}' >"$OUT/verdict.json"
jq -r --arg path "$OUT/verdict.json" '"\(.verdict): release qualification (suites \(.suites.pass)/\(.suites.total) pass, "
  + "\(.suites.not_run | length) not-run; repeatability \(.repeatability.pass) pass, \(.repeatability.not_run | length) not-run, "
  + "\(.repeatability.failed | length) fail); claims "
  + ([.claims | to_entries[] | "\(.key)=\(.value.status)"] | join(", ")) + " -> " + $path' "$OUT/verdict.json"
[[ "$(jq -r '.verdict' "$OUT/verdict.json")" == PASS ]]
