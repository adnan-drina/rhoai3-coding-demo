# Qwen-only live qualification — 2026-10-19

The optional `040-showback-demo` Application was published and deployed at `4349dd62429d15e68bb0e6935d3f1f0e617cdbc8`. Independent readback found all 21 owned resources Synced/Healthy and matching source. The existing Qwen NVFP4 checkpoint, model specification, replicas and GPU allocation were unchanged. Mistral, native Loki showback, external metering and external provider traffic were excluded.

The observed six-minute run completed **14 successful SSE requests and 1,753 tokens**, with exact response/counter agreement. The corrected allocation is **$0.34: Engineering $0.15, Support $0.07, platform idle $0.12**. This is a dated list-price estimate of allocated capacity, not an AWS invoice or full service cost.

The corrected publisher is **live and independently accepted** at `adecf57cab87982f5b5a48c966860376474f8f62`, with one Ready replica, one healthy scrape and the exact selected report. The first activation at `89036c17908519bc3ccc8d03f441f9b6cf60b7da` synced but the publisher exited with Apache CLI usage; a minimal startup-argument correction fixed it without changing the image. The earlier zero-replica readback and failed activation remain historical evidence. Later documentation-only revisions do not change these validated manifests.

## Identity, access and metering

Two new demo identities used the existing provisioner Keycloak `sso` realm and the normal OpenShift OAuth flow. Each genuine owner created its own short-lived MaaS key; owner/subscription metadata was checked server-side. No existing account password, realm/client configuration or model credential was replaced. An initial identity setup failed before inference; restricted local journals preserve the created user's identity and the subsequent explicit resume without storing credentials here.

Engineering and Support each passed isolated JSON and SSE completion probes. Every probe returned 20 tokens and increased only its owner's full-label counter by exactly 20. Missing and invalid keys both returned HTTP 401. The initial counter lookup used platform Thanos and stopped after two successful prime requests; native RHOAI Thanos supplied the canonical counters for the successful rerun. Both attempts remain counted.

- Qualification probes: 10 HTTP POSTs, eight successful completions, two authentication denials.
- Bounded workload: 14 HTTP POSTs, all successful; no retries/errors.
- Total: 24 HTTP POSTs, 22 successful completions and two denials.

No quota-exhaustion, Marketing, Mistral or forbidden team/model test is claimed. The frozen [qualification profile](../../qualification-qwen-only.json) has SHA-256 `67646252142382ec0095ce3bb8fe9426df0053c6b2bd78c2101df9be5d6f3c66`; its historical input status is deliberately unchanged. Later helper fixes were reviewed and tested offline; they are not presented as the exact source of every earlier attempt.

## Measured allocation

Period: **2026-10-19 08:42:16Z–08:48:16Z**, three two-minute windows. The workload ended and collected a trailing scrape interval; no continuing workload generator remains.

| Window | Engineering tokens | Support tokens | Estimated cost | Engineering | Support | Platform idle |
|---|---:|---:|---:|---:|---:|---:|
| Busy | 523 | 1,100 | $0.11 | $0.04 | $0.07 | $0.00 |
| Quiet | 130 | 0 | $0.11 | $0.11 | $0.00 | $0.00 |
| Idle | 0 | 0 | $0.12 | $0.00 | $0.00 | $0.12 |
| Total | 653 | 1,100 | **$0.34** | **$0.15** | **$0.07** | **$0.12** |

Engineering made five requests and Support nine. Receipt totals were 1,305 input plus 448 output tokens. Two other existing consumer series stayed in the denominator and had zero usage throughout. Other-consumer and unresolved allocations are both zero in the corrected report. Engineering pays the whole quiet window because it was the only consumer then; the 70/30 token allowance does not set the bill split. Fractional-cent carry preserves exact reconciliation across windows.

One observed allocated `g7e.2xlarge` RTX PRO 6000 worker in `us-east-2` is priced at **$3.36312/hour**, from the retained AWS public Linux On-Demand snapshot retrieved on 2026-10-15 (effective 2026-10-01). Six minutes gives $0.336312 before rounding. Repeated guarded cluster observations tied the model to the same node/provider/type/region; the AWS lookup failed with `NoCredentials`, so exact billed lifecycle is unverified. Earlier warmup, capacity after the report, storage, networking, shared control plane, software, tax and discounts are excluded. The full two-worker cost template was not rewritten to claim a one-model result.

## Preserved failure and correction

The first report priced $0.34 but correctly left all of it unresolved. Its 20-second boundary tolerance rejected the first sample after each boundary at +21.747 seconds. The installed native collector's Prometheus job and raw samples both established a **30-second scrape cadence**. All 16 boundary brackets had equal counter values at -8.253/+21.747 seconds; adjacent sample steps were 30 seconds, with no reset, gap or boundary activity.

The explicit correction changed boundary tolerance from 20 to 30 seconds, preserving the 45-second maximum-gap limit and equal-flank/reset/duplicate checks. It replayed unchanged scenario, run, receipts and samples without another inference run. Independent recalculation confirmed the result. Sampled counters still cannot establish unsampled sub-scrape billing detail.

| Artifact | Original | Corrected |
|---|---|---|
| Report ID | `showback-1792399336-60885-6425` | `showback-1792399336-60885-6425-r2-cadence30` |
| Canonical report SHA-256 | `d9c83fefc99ceb1cbd6f064b9946f357da9533fe7d47e18a5cf03cfeb1b1d259` | `b1d090696543beb0842108c528b7734cedc108789d14f6254eaa698fae26f44a` |
| Bundle manifest SHA-256 | `0bb2986e600d2d3c79e34b0e33b060b2e70dfe5a5b5307db77d2a154c38e59c9` | `7db19c1f61dafa6a61c18e7fb7e690674cef5a2b9225cbb9560a040e2d22b259` |
| Allocation complete | No; $0.34 unresolved | Yes; $0.15 / $0.07 / $0.12 |

The correction records its predecessor manifest and reason; the original artifacts are not overwritten.

## Native MLflow archive

The dedicated workspace's RoleBinding grants the existing `rhods-admins` group the native namespaced `edit` ClusterRole. Effective aggregated MLflow experiment permissions were verified before deployment. The previously proposed `mlflow-edit` ClusterRole does not exist in this environment. The broad native `edit` grant is confined to this admin workspace; no custom ClusterRole was added.

Genuine `ai-admin` uploaded both bundles to experiment `14` in workspace `showback-reporting`. Every artifact was downloaded and compared by hash, and both server-side run states are FINISHED. Genuine Engineering access to the workspace's experiment API returned **403**.

| Bundle | MLflow run | Verified files, including manifest |
|---|---|---:|
| Original | `ba7c4073c00641239cc390fc7d8d05de` | 14 |
| Corrected | `a3d9fb6b28bf47aaaa529f2571aa75aa` | 17 |

The private bundles contain raw evidence; this folder holds only sanitized summaries. The requested 400-day retention is **not enforced** by the current implementation. No MLflow browser UI test is claimed.

## Dashboard verification and limits

All eight Perses dashboards were Available with no Degraded condition. Read-only Perses API results matched their live custom-resource definitions after normalizing an omitted empty variables array. Seven operational queries returned finite Qwen series using their actual configured datasource: native RHOAI Thanos for throughput, TTFT, inter-token latency and GPU activity; platform Thanos for queue depth and DCGM framebuffer memory. The temporary API forward was closed. This initial acceptance did not test browser rendering or presenter interaction; the later check below covers the three bounded-report views.

The three bounded-report views now have the selected corrected snapshot. The actual bill panel queries return one observed report, $0.34 total, $0.15 Engineering, $0.07 Support and $0.12 platform idle, with both pricing and allocation complete. Six consumer rows are unique; Marketing, other consumers and unresolved costs are zero. The healthy `up=1` series matches the only current Ready publisher Pod. At acceptance, one historical `up=0` series still matched the recorded failed predecessor; the guarded financial panels exclude it. No data or selector was changed to conceal that failed target.

The five monthly service views have definitions but no observed monthly statements. Full-quarter continuity, actual provider invoices, accepted-task quality/tracing, three-offer live pricing, consumer dashboard isolation, enforced retention, quota exhaustion and full FP8/Mistral qualification remain open. Native Loki/external-metering inputs and the locally built backend remain inactive.

### Follow-up after the empty-dashboard report

The three supplied screenshot attachments have filesystem timestamps of 09:05:43, 09:06:00 and 09:06:17 UTC. The corrected publisher became Ready at 09:09:00 UTC and its successful scrape/report acceptance was recorded at 09:11:02 UTC. This timing is consistent with the empty views being captured during the earlier startup failure. Attachment timestamps are corroborating evidence, not guaranteed browser capture times; no browser cache fault was established.

A fresh authenticated `ai-admin` browser session with **Last 30 minutes** showed populated values in all three views: the $0.34 bill and $0.15/$0.07/$0.12 allocation, Engineering's 653 tokens and Support's abbreviated `1K` display, and the 3.363120 USD/hour model rate. The underlying Support value is 1,100 tokens. The independently checked external RHOAI-to-Perses datasource proxy returned successful, populated responses for all 43 panel queries. Current throughput, queue and GPU activity were zero; latency quantiles were NaN in the idle window. These operational values follow the time picker, whereas the closed-report gauges continue to show the selected completed run. No additional inference was generated.

The browser check also exposed a separate display defect: the native StatChart default hides a singleton series legend, leaving report metadata panels displaying only `1`. The bounded dashboards now explicitly enable legends to retain report, price, model and window context. Query expressions, datasource selection, report contents and allocation policy are unchanged. Narrow screens can still abbreviate numbers or require horizontal scrolling within multi-series panels; this is native chart behavior, not missing metering data.

## Evidence index

- [Initial source and operational-query readback](source-readback.json): first published SHA, ownership, archive grant, Qwen and native-feature state, per-datasource results.
- [Identity-bound metering probes](metering-checks.json): isolated deltas, unchanged other-team counters, denials and complete request accounting.
- [Independent financial reconciliation](financial-reconciliation.json): receipt/counter agreement, calibration, hashes and cost limits.
- [Perses API ingestion](perses-readback.json): all eight definitions, controller conditions and explicit visual-test limit.
- [Original archive acceptance](archive-original.json) and [corrected archive acceptance](archive-corrected.json): FINISHED runs, hash readback and denied team access.
- [Release source validation](source-validation.json): all 20 package gates and repository/static Stage 040 checks passed without live transport.
- [Publisher startup correction](publisher-startup-correction.json): preserved first activation failure, verified pinned-image configuration and minimal argument correction. Its pending status is historical; the focused publisher/dashboard regression and Stage 040 static gate passed after this fix.
- [Final publisher and financial-panel acceptance](publisher-live-readback.json): exact 21-resource readback at the corrected revision, one current healthy publisher, unique selected report, actual financial query results and unchanged model/native state.
- [RHOAI dashboard proxy readback](dashboard-proxy-readback.json): follow-up queries through the actual external RHOAI/Perses path, including idle-window operational limits.

AI assistance: Codex lead with implementation and independent validation delegated to GPT-6.1 Sol. Human review of the complete diff remains required before merge. These summaries distinguish observed results from source-only, estimated and pending claims.
