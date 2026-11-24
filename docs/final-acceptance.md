# FactoryLens MVP final acceptance

**2026-11-24 · Phase 7 · Windows local acceptance.** Core workflows passed
with the limitations below. Phase 7 made zero paid LLM requests. Browser and
destructive API checks used an isolated SQLite copy. The original Phase 4.4
cloud record was reused.

## Function checklist

| Area | Actual evidence |
| --- | --- |
| Dashboard and navigation | Browser showed 2,205 UCI cycles and 255 anomalies. Opened Overview, Machine Analysis, Batch Analysis, Knowledge Base, AI Diagnostic Copilot and Maintenance Work Orders. |
| Equipment lookup | Browser found HYD-0001 and autofilled the five measurements. API confirmed pressure 160.6735 bar. |
| Single prediction | Browser scored a disposable copy of the sensor data and displayed healthy risk. Direct API returned probability 0.079939 and no Isolation Forest anomaly for HYD-0001. |
| Batch and Isolation Forest | Browser upload of the bundled CSV returned three scored rows. HYD-DEMO-03 was high risk and anomalous. |
| Knowledge base | Browser uploaded a QA TXT, opened the chunk and searched its distinctive terms. API returned 409 for the duplicate, 400 for an unsupported file and 204 for deletion. The deleted excerpt disappeared from search. Pytest covers Markdown, invalid encoding, empty and oversized files. |
| Saved cloud diagnosis | Browser reopened the original OpenLux gpt-5-mini result with four evidence excerpts and model-originated tool records. Offline snapshot verification confirmed schema, recorded data, scores, three cited IDs, excerpt text and trace structure. |
| Retrieval-only fallback and history | Browser ran a new local diagnosis on the credential-free instance. Its Fallback mode and saved diagnosis snapshot were visible after process restart. |
| Human confirmation and work orders | Browser confirmed the form required review before creating an order. The new order passed Open → In Progress → Resolved. The maintenance note and snapshot were visible after backend restart. The API rejected duplicate creation and a reverse transition with 409. Snapshot equality and SQLite integrity passed. |
| Reports | Browser downloaded and read the archived OpenLux diagnosis report and the new resolved Fallback work-order report. Confirmed provenance, state and notes. Phase 6 also downloaded and compared a standalone Fallback diagnosis report and the original cloud work-order report. |
| UI states and errors | Browser observed the filtered empty order list. Existing Vitest tests cover loading, missing-record errors and failed report downloads. Invalid diagnostic, upload and order requests are exercised in pytest. |
| Offline evaluation | Re-ran all eight retrieval cases and checked the saved UCI cloud snapshot with the evaluation script. |

## Automated checks and environment

The development workspace passed pytest **54/54**, Vitest **16/16**, Ruff,
ESLint, production build and `git diff --check`. An independent copy of the
project was installed and started on Windows with Python **3.12.14**, Node
**24.22.3** and pnpm **11.25.0**. The clean Python environment installed
`.[dev]` from official PyPI with cache reuse and passed `pip check`,
Ruff and pytest **54/54**. The
clean frontend installed 323 packages with `pnpm install --frozen-lockfile
--offline` from the existing pnpm store. Its build and Vitest **16/16** passed.
The isolated FastAPI site and Vite dev server returned HTTP 200. A cross-origin
health check returned the expected CORS header. The same-origin build served
the browser workflow.

Two app lifespans against a fresh database each reported 2,205 operating cycles,
three built-in documents and empty diagnosis and order lists. The second
startup of the browser QA database retained its saved diagnosis and order.
No cloud credential was supplied to either acceptance instance.

First attempts exposed two test-harness issues. The clean pytest invocation's
`--basetemp` parent did not exist, so 50 items that depended on temporary paths
errored during setup and 4 passed. The suite passed when rerun with an existing parent.
The first PowerShell API probe handled an array incorrectly and stopped before
deletion. The revised probe passed. Existing warnings are Starlette TestClient’s
`httpx` deprecation notice, Vite's JavaScript chunk size warning and Git's
Windows line-ending notice for `frontend/src/services/api.ts`.

## Saved live cloud evidence

Phase 4.4 used OpenLux and `gpt-5-mini` for one public HYD-0001 diagnosis.
Both Responses requests returned HTTP 200 and `completed`. Model-originated
`analyze_equipment` and `search_knowledge` ran successfully. The final response
passed Schema and citation checks and was saved and reopened in the browser.

| Request | Time | Input tokens | Output tokens | Reasoning tokens within output |
| --- | ---: | ---: | ---: | ---: |
| Tools | 7.622 s | 417 | 371 | 256 |
| Final | 18.241 s | 2,633 | 2,198 | 1,792 |
| Total | 25.863 s | 3,050 | 2,569 | 2,048 |

Usage is from the prior provider logs. The offline evaluation rechecked the
saved record and model scores. The snapshot itself does not store billing
telemetry or independently prove that external requests were made.

## Retrieval analysis

The eight original English development queries were retained. The 0.08
cosine threshold suppresses low-scoring excerpts and empty results appear
in the UI. A diagnostic without evidence cannot produce cited causes or
checks that pass the backend reference validator.

| Case | Returned scores, highest first | Result |
| --- | --- | --- |
| Pressure | 0.325679 | Expected heading first |
| Oil temperature | 0.507028, 0.103469 | Expected heading first |
| Motor power | 0.552257, 0.116971 | Expected heading first |
| Flow | 0.234910, 0.192500, 0.112197 | Expected heading first |
| Vibration | 0.412164 | Expected heading first |
| General maintenance | 0.427648 | Expected heading first |
| Exoplanets | Empty | Correct rejection |
| Manufacturer torque specification | 0.208470, 0.105295, 0.083323 | Expected-empty failure |

The rerun reproduces **7/8**, **Hit@3 6/6**, **MRR@3 1.00** and **one of two**
correct empty results. The torque question shares terms such as pressure
and valve with generic guidance. The corpus provides no requested torque
specification. A threshold above 0.208470 would reject this observed case,
but it could discard legitimate lower-scoring or secondary evidence. A
winner-margin rule also lacks support here. The strongest torque match
is separated from the runner-up by about 0.103, while the correctly matched
flow question has a margin of about 0.042. No retrieval setting changed.

Keeping generic excerpts visible while explicitly flagging missing
manufacturer-specific information is a candidate approach. Validate any
new abstention rule on more unsupported in-domain questions and independent
positive queries before adopting it. The current citation checks cannot
detect all answerability failures. This evaluation has sparse expected
headings and no independent split or exhaustive excerpt relevance labels.
It supplies neither fragment-level recall nor field generalization evidence.

## Security and integrity

| Check | Verification |
| --- | --- |
| Secrets and local artifacts | Git confirmed `.env` is ignored and untracked. Isolated DBs and result JSON are under ignored `.venv`. Scanned tracked changes and every nonignored untracked file for credential-like text, database/log/cache files and unexpected files above 1 MiB. No candidate was flagged. Reviewed QA output contains no credential value. Pattern scanning is not exhaustive secret discovery. |
| Endpoint and provider routing | Mock tests verify provider-to-URL and credential pairing, disabled redirects and retry behavior. Code review confirms fixed HTTPS provider allowlists. No live invalid endpoint was contacted. |
| Validators | Pytest covers upload checks, forged citations, invalid structured output, cross-device tools, invalid transitions and confirmation. Several HTTP rejections were also exercised on the isolated running API. |
| Untrusted content | Mock tests verify a privately uploaded instruction is excluded from the cloud corpus and undeclared tools are rejected. Code review confirms bundled-source/hash checks and read-only operations. No live adversarial LLM campaign was performed. |
| Physical and data scope | Browser showed the education disclaimer and labeled hypotheses. Code review found only local diagnosis reads, scoring, retrieval, and work-order/report operations in this path. No equipment-control interface was exercised or exists in the supplied tool registry. |

The upstream MIT license, UCI CC BY 4.0 attribution, bundled models and pnpm
lock file had empty diffs against HEAD. The candidate release keeps upstream
dashboard, equipment scoring, anomaly detection and training attribution
separate from FactoryLens knowledge, AI diagnostics, orders, reports and evaluation.

## Human review and remaining limits

The [groundedness record](groundedness-review.md) contains the four exact
model findings, three cited excerpts, actual readings and ML findings.
On 2026-11-24, the project owner completed a ChatGPT-assisted review.
The result was 2/4 supported, 2/4 partially supported and 0/4 unsupported.
The ML summary matched the recorded prediction. The reviewer identified
no fabricated readings or explicit claim of a confirmed fault. Both
hypotheses need clearer operating-condition prerequisites. This single-case
review supports an educational demonstration. Industrial diagnostic validity
remains unverified. This is a local education prototype with no per-user
authorization, site calibration, drift monitoring or prospective
industrial validation. Container/cloud deployment, Linux CI and a cache-free
registry install were not run in Phase 7.

## Phase 8 release preparation

1. Keep the completed project-owner review, its limitations and the retrieval
   failure visible in public documentation.
2. Review the complete Git diff and untracked file list. Stage only intended
   source, tests, fixtures and project documentation. Consider one cohesive
   FactoryLens implementation commit and one documentation/acceptance commit.
   Existing upstream commits remain intact. Do not reconstruct fictional
   phase-by-phase history.
3. Repeat the staged secret/large-file scan and license/data attribution
   checks. Keep local DBs, logs, downloads, credentials and test environments
   outside release commits.
4. With deployment authorization, verify the target environment and document
   its settings, persistence behavior and upload limits. Use a synthetic or
   public demonstration dataset and keep runtime secrets server-side.
5. Publish or push only after explicit approval and repository review.
   Phase 7 made no Git commit or push.
