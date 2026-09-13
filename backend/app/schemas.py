from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MachineInput(BaseModel):
    machine_id: str | None = Field(default=None, max_length=64)
    pressure_bar: float = Field(ge=0, le=500, description="Mean PS1 pressure in bar")
    oil_temperature_c: float = Field(ge=-20, le=200, description="Mean TS1 temperature in °C")
    motor_power_w: float = Field(ge=0, le=20_000, description="Mean EPS1 motor power in W")
    volume_flow_lpm: float = Field(ge=0, le=500, description="Mean FS1 flow in l/min")
    vibration_mms: float = Field(ge=0, le=100, description="Mean VS1 vibration in mm/s")

    @field_validator("machine_id")
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return value.strip().upper() if value and value.strip() else None


class RiskFactor(BaseModel):
    feature: str
    impact: float


class PredictionResult(BaseModel):
    machine_id: str | None
    failure_prediction: bool
    failure_probability: float
    risk_level: Literal["healthy", "warning", "high"]
    anomaly: bool
    anomaly_score: float
    top_factors: list[RiskFactor]
    interpretation: str


class BatchResponse(BaseModel):
    count: int
    results: list[PredictionResult]


class MachineLookupResult(BaseModel):
    machine: MachineInput
    assessment: PredictionResult
    source: str
    component_condition: dict[str, int | str] | None = None


class AssetListItem(BaseModel):
    machine_id: str
    failure_probability: float
    risk_level: Literal["healthy", "warning", "high"]
    anomaly: bool
    anomaly_score: float
    source: str


class AssetListResponse(BaseModel):
    category: str
    count: int
    results: list[AssetListItem]


class FleetSummary(BaseModel):
    total: int
    healthy: int
    warning: int
    high: int
    anomalies: int
