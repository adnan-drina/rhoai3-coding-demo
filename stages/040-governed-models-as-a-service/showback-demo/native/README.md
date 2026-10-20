# External metering inputs

This folder supports the continuous external metering in the component's `metering/` folder:

| Source | Purpose |
|---|---|
| `provider-pricing.json` | Versioned public list prices per external model, context band and token category; copied unchanged to `metering/provider-pricing.json` |
| `backend/` | Patches, Containerfile and build/publish scripts for the metering backend; see [backend/README.md](backend/README.md) |
| `test-backend-local.sh` | Runtime probe for a locally running backend and database (explicit, local only) |
| `import-events.sh`, `normalize-events.jq`, `examples/` | Offline import of captured events into a monthly service-offer input |
| `test-native.sh` | Offline importer tests, run by `../validate.sh` |

## How capture works

RHOAI 3.5 ships the IPP `external-metering-streaming` plugin (Developer Preview). For each external-model response it posts one CloudEvent with the authenticated MaaS user, subscription, model and token counts. Red Hat documents the plugin but no backend, so the demo runs a patched build of the community Noyitz metering service in a metering-only mode: it stores each event once (by source and event ID) in PostgreSQL, freezes a price estimate from the catalog version in force, and exposes current-month gauges on `/metrics` for the RHOAI dashboards. MaaS subscriptions keep controlling access and token limits.

Known limits of the shipped producer: one delivery attempt with no retry queue, absent usage counters arrive as zero, and a response without usage may emit no event. The ledger is therefore captured-event showback, not a complete request or invoice ledger.

## Prices

Each catalog entry names its provider, model, category (uncached input, cache read, cache write, output), context band, `price_version`, source URL and verification date. A price change needs a new catalog version and new `price_version` values; the backend refuses a changed file that reuses a version, and earlier events keep their frozen estimates. NVIDIA's hosted Nemotron endpoint is recorded as a free prototype. Models without a price stay unpriced rather than zero.

## Import captured events

The importer turns saved events into the `events` of a monthly offer input:

```bash
bash import-events.sh \
  --events /absolute/path/to/events.jsonl \
  --capture /absolute/path/to/capture.json \
  --offers /absolute/path/to/month-with-empty-events.json \
  --output /absolute/path/to/new-native-month.json
bash ../offers/service-report.sh \
  --input /absolute/path/to/new-native-month.json \
  --output /absolute/path/to/new-statement.json
```

The capture manifest binds the events file hash, the provider/model-to-agreement mapping, the interval and independent completion evidence. Identical source/ID replays collapse, conflicting copies fail and unknown identities are quarantined. Missing events or token fields never become zero usage. OpenAI cache reads are subtracted from input, and reasoning tokens already included in output are not added twice. Event IDs are new UUIDs, not gateway request IDs, so events do not join automatically to workload receipts.
