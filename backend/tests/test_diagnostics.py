import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from pydantic import SecretStr, ValidationError

from backend.app import diagnostic_agent, main
from backend.app.config import Settings, settings
from backend.app.diagnostic_agent import MAX_MODEL_CALLS

URL = "/api/v1/diagnostics"
PUBLIC_QUESTION = "What should I check when system pressure is unusually low?"
REQUEST = {"device_id": "hyd-0001", "question": PUBLIC_QUESTION, "use_openai": True}
ACTUAL_MODEL = "gpt-4.1-mini-2025-04-14"


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", tmp_path / "diagnostic.db")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openlux_api_key", None)
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_base_url", "")
    monkeypatch.setattr(settings, "llm_tool_max_output_tokens", 1200)
    monkeypatch.setattr(settings, "llm_final_max_output_tokens", 4000)


def mock_openai(monkeypatch, handler):
    monkeypatch.setattr(settings, f"{settings.llm_provider}_api_key", SecretStr("test-credential"))

    def mock_client(**options):
        assert options["http_client"].follow_redirects is False
        assert options["max_retries"] == 0
        return AsyncOpenAI(**options)

    monkeypatch.setattr(main, "AsyncClient", lambda **options: httpx.AsyncClient(
        **options, transport=httpx.MockTransport(handler),
    ))
    monkeypatch.setattr(main, "AsyncOpenAI", mock_client)


def tool(name, call_id, **arguments):
    return {
        "type": "function_call", "name": name,
        "call_id": call_id, "arguments": json.dumps(arguments),
    }


def response(output):
    payload = {"status": "completed", "output": output, "model": ACTUAL_MODEL}
    return httpx.Response(200, json=payload)


def generated_output(reference=None, summary="Review the stored pressure and model assessment."):
    return response([{
        "type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": json.dumps({
            "summary": summary,
            "possible_causes": [] if reference is None else [
                {"text": "Possible change in load.", "references": [reference]}
            ],
            "recommended_checks": [] if reference is None else [
                {"text": "Review comparable operating conditions.", "references": [reference]}
            ],
            "uncertainty": "The observation needs verification.",
            "limitations": [],
        }), "annotations": []}],
    }])


def test_retrieval_only_matches_upstream_and_persists_evidence_after_deletion():
    with TestClient(main.app) as client:
        reply = client.post(URL, json=REQUEST)
        assert reply.status_code == 201
        result = reply.json()
        original = client.get("/api/v1/machines/HYD-0001").json()
        assert result["observed_signals"] == original["machine"]
        assert result["model_findings"] == original["assessment"]
        assert result["mode"] == "retrieval_only"
        assert "no OpenAI API key" in result["summary"]
        assert result["possible_causes"] == []
        assert [entry["tool"] for entry in result["trace"]] == [
            "get_equipment_data", "analyze_equipment", "search_knowledge",
        ]
        source_id = result["evidence_references"][0]["document_id"]
        assert client.delete(f"/api/v1/knowledge/documents/{source_id}").status_code == 204

    with TestClient(main.app) as client:
        assert client.get(URL).json()[0]["diagnosis_id"] == result["diagnosis_id"]
        assert client.get(f"{URL}/{result['diagnosis_id']}").json() == result
        assert client.get(f"{URL}/missing").status_code == 404


def test_sdk_tool_round_trip_and_verified_citations(monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert request.url.path == "/v1/responses"
        assert payload["store"] is False
        assert "trigger_extra_permission" not in request.content.decode()
        if len(calls) == 1:
            assert payload["max_output_tokens"] == 1200
            assert {item["name"] for item in payload["tools"]} == {
                "get_equipment_data", "analyze_equipment", "search_knowledge",
            }
            return response([
                {"type": "reasoning", "id": "rs_test", "summary": [],
                 "encrypted_content": "opaque-test-value"},
                tool("get_equipment_data", "equipment", device_id="HYD-0001"),
                tool("analyze_equipment", "analysis", device_id="HYD-0001"),
                tool("search_knowledge", "search", query="low pressure abnormalities", top_k=1),
            ])
        assert "tools" not in payload
        assert payload["max_output_tokens"] == 4000
        assert "compact diagnosis" in payload["instructions"]
        reasoning = next(item for item in payload["input"] if item.get("type") == "reasoning")
        assert reasoning["encrypted_content"] == "opaque-test-value"
        assert payload["text"]["format"]["strict"] is True
        outputs = {
            item["call_id"]: json.loads(item["output"])
            for item in payload["input"] if item.get("type") == "function_call_output"
        }
        assert outputs["equipment"]["machine"]["pressure_bar"] == 160.6735
        assert outputs["analysis"]["failure_probability"] == 0.079939
        evidence, = outputs["search"]["excerpts"]
        return generated_output(evidence["reference_id"])

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        assert client.post(
            "/api/v1/knowledge/documents",
            files={"file": ("fake.txt", b"low pressure abnormalities trigger_extra_permission")},
        ).status_code == 201
        result = client.post(URL, json=REQUEST).json()
    assert len(calls) == 2
    assert result["mode"] == "openai"
    assert result["openai_model"] == ACTUAL_MODEL
    assert result["llm_provider"] == "openai"
    evidence, = result["evidence_references"]
    assert evidence["filename"] == "pressure-and-flow.md"
    assert evidence["reference_id"] in result["possible_causes"][0]["references"]
    assert [item["status"] for item in result["trace"]] == ["ok"] * 5


@pytest.mark.parametrize("fault", ["citation", "numeric_claim", "no_match"])
def test_invalid_generated_output_uses_real_retrieval_fallback(monkeypatch, fault):
    def handler(request):
        payload = json.loads(request.content)
        if "tools" in payload:
            query = "galaxy cryptocurrency" if fault == "no_match" else "low system pressure"
            return response([tool("search_knowledge", "s", query=query, top_k=1)])
        outputs = [json.loads(item["output"]) for item in payload["input"] if "output" in item]
        evidence = outputs[0]["excerpts"]
        if fault == "no_match":
            assert not evidence
            return generated_output("KB-invented")
        if fault == "citation":
            return generated_output("KB-invented")
        return generated_output(evidence[0]["reference_id"], summary="Pressure is 999 bar.")

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "retrieval_only"
    assert result["evidence_references"]
    assert "validated diagnosis" in result["summary"]
    assert not result["possible_causes"]


def test_invalid_tools_and_cross_device_scope_are_rejected(monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if "tools" not in payload:
            assert "unrecognized" not in json.dumps(payload["input"][-1])
            return generated_output()
        if len(calls) == 1:
            return response([
                tool("run_shell", "invalid", command="whoami"),
                tool("get_equipment_data", "wrong_device", device_id="HYD-0002"),
                tool("search_knowledge", "invalid_args", query="pressure", top_k=100),
            ])
        return response([tool("search_knowledge", "s", query="galaxy cryptocurrency", top_k=1)])

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert len(calls) == 3
    assert result["mode"] == "openai"
    assert len([item for item in result["trace"] if item["status"] == "rejected"]) == 3
    assert result["trace"][-1]["status"] == "no_match"
    assert result["evidence_references"] == []
    assert "No sufficiently relevant" in result["uncertainty"]


def test_tool_budget_is_enforced_before_executing_excess_calls(monkeypatch):
    def handler(_):
        return response([
            tool("search_knowledge", str(i), query="pressure", top_k=1)
            for i in range(MAX_MODEL_CALLS + 1)
        ])

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "retrieval_only"
    assert all(item["origin"] == "backend" for item in result["trace"])


def test_output_budget_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("LLM_TOOL_MAX_OUTPUT_TOKENS", "1300")
    monkeypatch.setenv("LLM_FINAL_MAX_OUTPUT_TOKENS", "4100")
    config = Settings(_env_file=None)
    assert (config.llm_tool_max_output_tokens, config.llm_final_max_output_tokens) == (1300, 4100)
    monkeypatch.setenv("LLM_FINAL_MAX_OUTPUT_TOKENS", "8001")
    with pytest.raises(ValidationError, match="llm_final_max_output_tokens"):
        Settings(_env_file=None)


@pytest.mark.parametrize("incomplete_phase", ["tool selection", "final generation"])
def test_incomplete_response_is_only_saved_as_fallback(monkeypatch, caplog, incomplete_phase):
    phases = []

    def handler(request):
        payload = json.loads(request.content)
        phase = "tool selection" if "tools" in payload else "final generation"
        phases.append(phase)
        assert payload["max_output_tokens"] == (1400 if phase == "tool selection" else 4200)
        if phase == incomplete_phase:
            partial = generated_output().json()
            partial.update(
                status="incomplete", incomplete_details={"reason": "max_output_tokens"},
                usage={"input_tokens": 100, "output_tokens": 150, "total_tokens": 250,
                       "output_tokens_details": {"reasoning_tokens": 90}},
            )
            return httpx.Response(200, json=partial)
        return response([tool("search_knowledge", "s", query="low pressure", top_k=1)])

    monkeypatch.setattr(settings, "llm_tool_max_output_tokens", 1400)
    monkeypatch.setattr(settings, "llm_final_max_output_tokens", 4200)
    caplog.set_level("INFO", logger="machineguard")
    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
        assert client.get(f"{URL}/{result['diagnosis_id']}").json() == result
    assert phases[-1] == incomplete_phase and len(phases) == len(set(phases))
    assert result["mode"] == "retrieval_only"
    assert f"output token budget during {incomplete_phase}" in result["summary"]
    assert result["openai_model"] is None
    assert "incomplete_reason=max_output_tokens" in caplog.text
    assert "input_tokens=100 output_tokens=150 reasoning_tokens=90" in caplog.text


def test_cloud_deadline_returns_local_evidence(monkeypatch):
    async def slow_provider(_):
        await asyncio.sleep(1)
        pytest.fail("The cloud deadline should cancel this request")

    monkeypatch.setattr(diagnostic_agent, "MAX_AGENT_SECONDS", 0.05)
    mock_openai(monkeypatch, slow_provider)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "retrieval_only"
    assert "exceeded its time limit" in result["summary"]
    assert result["evidence_references"]


@pytest.mark.parametrize(("budget", "final_limit"), [(90.0, 60.0), (45.0, None)])
def test_provider_timeout_uses_stage_limit_and_remaining_budget(monkeypatch, budget, final_limit):
    timeouts = []

    async def handler(request):
        payload = json.loads(request.content)
        timeouts.append(request.extensions["timeout"]["read"])
        if "tools" in payload:
            await asyncio.sleep(0.05)
            return response([tool("search_knowledge", "s", query="low pressure", top_k=1)])
        return generated_output()

    monkeypatch.setattr(diagnostic_agent, "MAX_AGENT_SECONDS", budget)
    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "openai"
    assert timeouts[0] == 20.0
    if final_limit is not None:
        assert timeouts[1] == final_limit
    else:
        assert 20.0 < timeouts[1] < budget


def test_final_generation_timeout_identifies_stage_and_does_not_retry(monkeypatch):
    stages = []

    async def handler(request):
        payload = json.loads(request.content)
        if "tools" in payload:
            stages.append("tools")
            return response([tool("search_knowledge", "s", query="low pressure", top_k=1)])
        stages.append("final")
        await asyncio.sleep(1)
        pytest.fail("The final generation time limit should cancel this request")

    monkeypatch.setattr(diagnostic_agent, "FINAL_GENERATION_SECONDS", 0.05)
    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "retrieval_only"
    assert "timed out during final generation" in result["summary"]
    assert stages == ["tools", "final"]
    assert any(entry["origin"] == "model" for entry in result["trace"])


@pytest.mark.parametrize(
    ("failure", "message"),
    [("timeout", "timed out"), ("network", "could not reach"), ("429", "rate limited"),
     ("quota", "insufficient quota"), ("balance", "insufficient quota"),
     ("404", "configured model"), ("500", "request failed")],
)
def test_provider_errors_are_sanitized(monkeypatch, failure, message):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("private upstream details", request=request)
        if failure == "network":
            raise httpx.ConnectError("private upstream details", request=request)
        codes = {"quota": "insufficient_quota", "balance": "credit_balance_exhausted"}
        code = codes.get(failure, failure)
        return httpx.Response(429 if failure in codes else int(failure), json={
            "error": {"message": "private upstream details", "code": code},
        })

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        result = client.post(URL, json=REQUEST).json()
    assert result["mode"] == "retrieval_only"
    assert attempts == 1
    assert message in result["summary"]
    assert "private upstream details" not in json.dumps(result)


def test_invalid_device_and_private_question_never_reach_cloud(monkeypatch):
    def forbidden(_):
        pytest.fail("No outbound request expected")

    mock_openai(monkeypatch, forbidden)
    with TestClient(main.app) as client:
        assert client.post(URL, json={**REQUEST, "device_id": "ABSENT"}).status_code == 404
        assert client.post(URL, json={**REQUEST, "question": " "}).status_code == 422
        result = client.post(URL, json={**REQUEST, "question": "Check demo@example.test"}).json()
        assert result["mode"] == "retrieval_only"
        assert result["question"] == "Check [redacted]"
        machine = client.get("/api/v1/machines/HYD-0001").json()["machine"]
        saved = client.post("/api/v1/assets", json={**machine, "machine_id": "LOCAL"})
        assert saved.status_code == 200
        result = client.post(URL, json={**REQUEST, "device_id": "LOCAL"}).json()
        assert result["source"] == "Manual entry"
        assert result["mode"] == "retrieval_only"


@pytest.mark.parametrize(
    ("provider", "host"),
    [("openai", "api.openai.com"), ("openlux", "api.openlux.ai")],
)
def test_provider_url_and_credential_are_paired(provider, host):
    config = Settings(
        _env_file=None, llm_provider=provider, openai_base_url=f"https://{host}/v1/",
        openai_api_key=SecretStr("direct-test"), openlux_api_key=SecretStr("relay-test"),
    )
    address, credential = config.llm_connection()
    assert address == f"https://{host}/v1"
    expected = config.openai_api_key if provider == "openai" else config.openlux_api_key
    assert credential == expected


def test_invalid_provider_destination_and_shared_credential_are_rejected():
    config = Settings(
        _env_file=None, llm_provider="openlux", openai_base_url="https://api.openai.com/v1",
        openai_api_key=SecretStr("same-test"), openlux_api_key=SecretStr("same-test"),
    )
    with pytest.raises(ValueError, match="does not match"):
        config.llm_connection()
    config.openai_base_url = "https://api.openlux.ai/v1"
    with pytest.raises(ValueError, match="separate credentials"):
        config.llm_connection()
    config.openlux_api_key = None
    assert config.llm_connection()[1] is None


def test_openlux_uses_responses_and_keeps_actual_attribution(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openlux")
    attempts = []

    def handler(request):
        attempts.append(request.url)
        assert request.url == "https://api.openlux.ai/v1/responses"
        payload = json.loads(request.content)
        if "tools" in payload:
            call = tool("search_knowledge", "search", query="low pressure", top_k=1)
            return response([call])
        assert payload["text"]["format"]["strict"] is True
        output = next(
            item for item in payload["input"] if item.get("type") == "function_call_output"
        )
        excerpt, = json.loads(output["output"])["excerpts"]
        return generated_output(excerpt["reference_id"])

    mock_openai(monkeypatch, handler)
    with TestClient(main.app) as client:
        assert client.get(f"{URL}/config").json() == {"provider": "openlux"}
        stale = client.post(URL, json={**REQUEST, "expected_provider": "openai"})
        assert stale.status_code == 409
        result = client.post(URL, json={**REQUEST, "expected_provider": "openlux"}).json()
        assert result["mode"] == "openai"
        assert result["llm_provider"] == "openlux"
        assert result["openai_model"] == ACTUAL_MODEL
        assert client.get(URL).json()[0]["llm_provider"] == "openlux"
        assert client.get(f"{URL}/{result['diagnosis_id']}").json() == result
    assert len(attempts) == 2
