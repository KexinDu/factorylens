from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
LLMProvider = Literal["openai", "openlux"]
LLM_BASE_URLS = {"openai": "https://api.openai.com/v1", "openlux": "https://api.openlux.ai/v1"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    model_path: Path = ROOT / "ml/artifacts/classifier.joblib"
    anomaly_model_path: Path = ROOT / "ml/artifacts/anomaly_model.joblib"
    metadata_path: Path = ROOT / "ml/artifacts/model_metadata.json"
    data_path: Path = ROOT / "data/processed/hydraulic_cycles.csv"
    database_path: Path = ROOT / "data/machineguard.db"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080"
    )
    log_level: str = "INFO"
    prediction_threshold: float | None = None
    warning_threshold: float = 0.25
    high_risk_threshold: float = 0.60
    max_upload_bytes: int = 2_000_000
    openai_api_key: SecretStr | None = None
    openlux_api_key: SecretStr | None = None
    llm_provider: LLMProvider = "openai"
    openai_base_url: str = ""
    openai_model: str = "gpt-4.1-mini"
    llm_tool_max_output_tokens: int = Field(default=1200, ge=16, le=4000)
    llm_final_max_output_tokens: int = Field(default=4000, ge=16, le=8000)
    knowledge_max_upload_bytes: int = Field(default=131_072, ge=1, le=524_288)
    knowledge_chunk_length: int = Field(default=800, ge=200, le=2000)
    knowledge_chunk_overlap: int = Field(default=100, ge=0)

    @model_validator(mode="after")
    def validate_knowledge_chunks(self):
        if self.knowledge_chunk_overlap > self.knowledge_chunk_length // 2:
            raise ValueError("Knowledge chunk overlap must be at most half the chunk length.")
        return self

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def llm_connection(self) -> tuple[str, SecretStr | None]:
        expected = LLM_BASE_URLS[self.llm_provider]
        url = self.openai_base_url.strip().rstrip("/") or expected
        if url != expected:
            raise ValueError("OPENAI_BASE_URL does not match the selected LLM_PROVIDER.")
        if self.openai_api_key and self.openlux_api_key:
            if self.openai_api_key.get_secret_value().strip() == (
                self.openlux_api_key.get_secret_value().strip()
            ):
                raise ValueError("Configure separate credentials for OpenAI and OpenLux.")
        key = self.openai_api_key if self.llm_provider == "openai" else self.openlux_api_key
        return url, key


settings = Settings()
