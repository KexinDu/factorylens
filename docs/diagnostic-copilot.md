# FactoryLens AI Diagnostic Copilot

## Run locally

Install the updated Python dependencies from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pip check
```

For cloud mode, edit the Git-ignored .env locally. Choose one provider and
configure a model available to your project or token group that supports
Responses function calling and strict structured outputs.

| Variable | Direct OpenAI | OpenLux relay |
| --- | --- | --- |
| `LLM_PROVIDER` | `openai` (default) | `openlux` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | `https://api.openlux.ai/v1` |
| Credential | `OPENAI_API_KEY` | `OPENLUX_API_KEY` |
| `OPENAI_MODEL` example | `gpt-4.1-mini` | `gpt-5-mini`, if enabled for the token group |

The selected provider supplies the default URL when `OPENAI_BASE_URL` is
blank. The backend accepts only the selected provider's documented endpoint
and keeps its credential separate. Keep credentials out of frontend settings,
commits, browser forms, and chat. Restart the backend after configuration.
Start the backend and React dev server as described in the repository README.

For a single live check, open **AI Diagnostic Copilot**, enter `HYD-0001`, ask
“What should I check when system pressure is unusually low?”, enable
the checkbox labeled with the active provider, then run it once. Expect a saved
result labeled **OpenAI direct API** or **OpenLux API**, the model reported by
the provider, and at least one model-originated
tool call. Check that displayed readings match Machine Analysis and that cited
IDs resolve to visible excerpts. A **Retrieval-only fallback** result gives the
reason cloud generation could not complete. A successful API-mode diagnosis
verifies access to the configured model for this workflow.

Cloud mode sends the question and evidence from public UCI operating cycles and
bundled educational knowledge only. Avoid entering personal details. The
application blocks common credential and contact patterns, which is a limited
check. Manually entered equipment and uploaded documents stay local.
The SDK authenticates with the key in the HTTP authorization header.
Responses do not include the key in model input. The backend requests
`store: false` and sends no unrelated files.

## How a diagnosis runs

1. FastAPI validates the question and selected ID. The three tools are named,
   read-only backend functions with fixed parameter schemas.
2. The backend obtains the selected sensor record and runs both ML models on
   that snapshot. Later tool requests return that same snapshot for consistency.
3. If cloud mode is enabled and eligible, the model can request registered
   tools. The backend validates the name, JSON parameters and device scope,
   executes supported operations, and sends the results back with their call IDs.
4. TF-IDF returns bounded excerpts with a stable citation ID derived from each
   chunk ID. The model may supply English search terms. The backend performs
   a search itself when the model has not executed a valid search.
5. The final Responses call uses a strict output schema. The backend checks
   the parsed structure, hypothesis wording and each reference. It fills
   numeric measurements and ML scores directly from the verified snapshots.
6. The backend saves a complete copy of the diagnosis and its evidence. The UI
   shows the tool order, origin, sanitized parameters, status, elapsed time and
   result summary. The trace consists of observed execution events.

The loop permits at most two tool-selection rounds, five model-requested tool
calls, and one final generation request. Tool selection has a 20-second
limit per request and final generation has a 60-second limit, both capped
by the time remaining in the 90-second cloud deadline. The browser allows
105 seconds for the cloud flow and local processing. SDK retries are disabled.
Tool selection defaults to 1,200 output tokens and final generation to 4,000.
Set `LLM_TOOL_MAX_OUTPUT_TOKENS` (16–4,000) and
`LLM_FINAL_MAX_OUTPUT_TOKENS` (16–8,000) to override them. The backend logs
the phase, response status, incomplete reason, token counts when supplied,
and elapsed time. Incomplete responses are rejected and use the local fallback.
The backend also runs the mandatory local
snapshot tools and, if needed, a local search. Those operations and saving the
history are outside the cloud deadline.

| Tool | Parameters | Result |
| --- | --- | --- |
| `get_equipment_data` | `device_id` matching the selected device | Five recorded measurements and their source. |
| `analyze_equipment` | `device_id` matching the selected device | Classifier risk and probability, Isolation Forest flag and score, and existing model explanations. |
| `search_knowledge` | `query` of at most 300 characters and `top_k` from 1 to 4 | Ranked excerpts, score, document and chunk information, and reference ID. Excerpts in the diagnosis are capped at 900 characters. |

## HTTP and storage

| Route | Result |
| --- | --- |
| `POST /api/v1/diagnostics` | Accepts `device_id`, `question`, optional `use_openai`, and optional `expected_provider`. Returns 201, 404 for unknown equipment, 409 for changed provider, or 422 for invalid input or readings. |
| `GET /api/v1/diagnostics/config` | Returns the active provider for the consent label. |
| `GET /api/v1/diagnostics?limit=20&offset=0` | Lists history newest first. Limit can be 1 to 50. |
| `GET /api/v1/diagnostics/{diagnosis_id}` | Returns the stored snapshot or 404. |

`diagnostic_history` stores `diagnosis_id`, `created_at`, `device_id`,
`question`, `mode`, `openai_model` and `snapshot_json`. The JSON stores the
sensor readings, model analysis, final response, evidence excerpts, trace,
and provider. Older snapshots are attributed to direct OpenAI.
Later work orders can reference the diagnosis primary key. History does not
depend on knowledge table rows.

## Verification and limitations

Run pytest and Ruff from the repository root, and Vitest, ESLint and the
production build from frontend. The diagnostic pytest suite intercepts SDK
requests with an HTTP test transport. That path proves application behavior,
request serialization and validation without billable calls. A live diagnosis
separately verifies the account and provider.

The current application is a local portfolio prototype without per-user
history isolation. UCI benchmark IDs represent recorded operating cycles.
TF-IDF favors matching words and phrases, primarily in English documents.
An accepted reference proves that the cited excerpt was retrieved. A person
still needs to evaluate whether the excerpt supports the hypothesis.
Qualified personnel must verify findings before making any maintenance decision.
This phase has no embedding search, equipment control, or work orders.

OpenAI references:

- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Official Python SDK](https://github.com/openai/openai-python)
- [OpenLux Responses API](https://doc.openlux.ai/reference/v1/responses)
