# FactoryLens reports and offline evaluation

## Markdown reports

Open a diagnosis or work order and select **Download Markdown Report**.
The backend reads stored fields and formats them into a UTF-8 Markdown
attachment. It adds the generation timestamp in UTC. The work order report
uses the saved diagnostic snapshot along with the current status and notes.

| API endpoint | File |
| --- | --- |
| `GET /api/v1/diagnostics/{diagnosis_id}/report` | `factorylens-diagnosis-<id>.md` |
| `GET /api/v1/work-orders/{work_order_id}/report` | `factorylens-work-order-<id>.md` |

Both endpoints return HTTP 404 for unknown records. Successful responses use
`Content-Type: text/markdown; charset=utf-8` and
`Content-Disposition: attachment` with a server-generated filename. Multiline
text and evidence are fenced as literal text. Fallback reports say that
generative diagnosis did not complete. Exports access local records and
require zero LLM requests.

## Reproduce the evaluation

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_maintenance
```

To verify a previously saved cloud diagnosis for a public UCI cycle, point
the script at a local database copy. The archive is opened read-only, and
retrieval and baseline ML run in an independent temporary database.

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate_maintenance --snapshot-db "path-to-local-copy.db" --diagnosis-id "saved-diagnosis-id"
```

The JSON output lists each query, returned locations and scores, any failed
expectations, and optional snapshot checks. A nonzero exit code signals a
requested snapshot check failed or the evaluation could not run. Retrieval
expectation misses are reported in the JSON.

## Recorded retrieval results

The [case file](../scripts/maintenance_eval_cases.json) defines eight
English development cases against the three bundled educational documents.
The positive cases each specify one expected filename and heading. Two cases
expect an empty result. There is no independently held-out test set.

| Metric | Observed result | Calculation |
| --- | --- | --- |
| Hit@3 | 6/6, 1.00 | Share of positive queries with the expected file and heading in the top three. |
| MRR@3 | 1.00 | Mean reciprocal rank of the first matching file and heading for the six positive queries. A miss contributes zero. |
| Expected-empty cases | 1/2 | Share of the expected-empty queries that produced no excerpts. |
| Overall expectations | 7/8 | Positive hits plus correct empty results. |

Pressure, oil temperature, motor power, flow, vibration, and general
inspection each hit at rank one. The exoplanet query returned no match.
The manufacturer torque question returned three generic hydraulic excerpts.
Its top score was 0.208470 for *Pressure abnormalities*. Shared terms such
as pressure and valve can retrieve general guidance for a question whose
requested specification is absent. This is a known evaluation failure.

The dataset does not exhaustively label relevant excerpts. Hit@3 and MRR@3
report targeted relevance, and full fragment-level Recall is unavailable.
The corpus is small, the queries use vocabulary close to the documents, and
success here does not establish generalization to novel queries or industrial
sites.

## Archived cloud diagnosis

The evaluated Phase 4.4 record is `6850c4f650e741b0ad2ffb1b9b52adb2` for
`HYD-0001`, routed through OpenLux to `gpt-5-mini`. Its schema, five
measurements, ML scores and flags, citation IDs, four excerpt texts, and tool
trace consistency all passed. The findings reference three distinct excerpts.
The archived trace identifies model-originated `analyze_equipment` and
`search_knowledge` calls. The actual provider response logs from Phase 4.4
corroborated both calls. The snapshot alone can verify trace structure.

Archived provider telemetry from Phase 4.4, with no fresh cloud calls:

| Stage | Time | Input | Output | Reasoning (included in output) |
| --- | ---: | ---: | ---: | ---: |
| Tool selection | 7.622 s | 417 | 371 | 256 |
| Final generation | 18.241 s | 2,633 | 2,198 | 1,792 |
| Total | 25.863 s | 3,050 | 2,569 | 2,048 |

Both requests returned completed responses. Provider usage is an archived
log observation. It is not a field in the stored diagnostic snapshot.
Existing Mock tests check incomplete-response handling and source-accurate
fallback behavior. Download tests also verify a report with no evidence.

## Human diagnostic review checklist

Use the saved report and assess one cause or recommended check at a time.

1. Confirm the device ID, source, and measured variables and units. For UCI,
   treat the ID as a recorded test-rig cycle.
2. Locate each cited excerpt in the report. Underline the exact text that
   supports the finding and note any part of the claim absent from the text.
3. Record **supported**, **partially supported**, or **unsupported** for each
   finding, with a short reason. Uncertain cases should remain unresolved
   until a qualified reviewer checks the evidence.
4. Check that explanations remain hypotheses. Verify that a conditional
   example such as low pressure is not presented as a measured abnormality
   without supporting observations. A model score does not confirm a fault.
5. Check that suggested inspections respect source limits and avoid
   unsourced manufacturer instructions or thresholds.
6. Where evidence is missing, record the needed manual, inspection or
   time-series data. Document whether the diagnosis is suitable for
   educational review and why.

The automated checks establish record, schema and citation consistency.
On 2026-11-24, the project owner completed a
[ChatGPT-assisted semantic review](groundedness-review.md) of this one saved
case. The result was **2/4 supported**, **2/4 partially supported** and
**0/4 unsupported**. Both hypotheses need operating-condition prerequisites.
The ML summary was consistent with the stored prediction, and the review
identified no fabricated sensor readings or explicit claims of confirmed
component faults. The outcome supports educational demonstration of this
case. Real-world industrial validity remains unverified.
