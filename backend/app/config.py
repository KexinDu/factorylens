from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


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

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
