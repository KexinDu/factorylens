from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .config import LLMProvider
from .knowledge_api import SearchResult
from .schemas import MachineInput, PredictionResult

DeviceID = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DiagnosticRequest(BaseModel):
    device_id: DeviceID
    question: Question
    use_openai: bool = False
    expected_provider: LLMProvider | None = None


class EquipmentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceID


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    top_k: Annotated[int, Field(ge=1, le=4)]


class CitedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str
    references: list[str]


class GeneratedDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: str
    possible_causes: list[CitedFinding]
    recommended_checks: list[CitedFinding]
    uncertainty: str
    limitations: list[str]


class Evidence(SearchResult):
    reference_id: str


class ToolExecution(BaseModel):
    tool: str
    status: Literal["ok", "no_match", "rejected", "error"]
    origin: Literal["backend", "model"]
    order: int
    elapsed_ms: int
    arguments: dict[str, int | str]
    result_summary: str


class DiagnosticSummary(BaseModel):
    diagnosis_id: str
    created_at: str
    device_id: str
    question: str
    mode: Literal["openai", "retrieval_only"]
    llm_provider: LLMProvider = "openai"
    openai_model: str | None


class Diagnosis(DiagnosticSummary):
    source: str
    observed_signals: MachineInput
    model_findings: PredictionResult
    summary: str
    possible_causes: list[CitedFinding]
    recommended_checks: list[CitedFinding]
    evidence_references: list[Evidence]
    uncertainty: str
    limitations: list[str]
    trace: list[ToolExecution]
