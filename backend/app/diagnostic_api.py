import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response

from .config import settings
from .diagnostic_agent import DiagnosticRun
from .diagnostic_schemas import Diagnosis, DiagnosticRequest, DiagnosticSummary
from .maintenance_reports import report_download

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


@router.post("", response_model=Diagnosis, status_code=201)
async def run_diagnosis(payload: DiagnosticRequest, request: Request):
    state = request.app.state
    if payload.use_openai and payload.expected_provider not in {None, state.llm_provider}:
        raise HTTPException(409, "The cloud provider changed. Reload the page to review it.")
    run = DiagnosticRun(
        state.models, state.knowledge, payload.device_id,
        tool_output_tokens=settings.llm_tool_max_output_tokens,
        final_output_tokens=settings.llm_final_max_output_tokens,
    )
    try:
        result = await run.diagnose(
            payload, state.openai_client, state.openai_model, state.llm_provider
        )
    except KeyError as exc:
        raise HTTPException(404, "The selected equipment was not found.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await asyncio.to_thread(state.diagnostic_history.save, result)
    return result


@router.get("", response_model=list[DiagnosticSummary])
def history(
    request: Request, limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return request.app.state.diagnostic_history.list(limit, offset)


@router.get("/config")
def diagnostic_config(request: Request):
    return {"provider": request.app.state.llm_provider}


@router.get("/{diagnosis_id}", response_model=Diagnosis)
def get_diagnosis(diagnosis_id: str, request: Request):
    result = request.app.state.diagnostic_history.get(diagnosis_id)
    if result is None:
        raise HTTPException(404, "Diagnosis not found.")
    return result


@router.get("/{diagnosis_id}/report", response_class=Response,
            responses={200: {"content": {"text/markdown": {}}}})
def download_diagnosis_report(diagnosis_id: str, request: Request):
    return report_download(get_diagnosis(diagnosis_id, request))
