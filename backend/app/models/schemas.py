from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)


class SaveQueryRequest(QueryRequest):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[\w .()-]+$")


class QueryResponse(BaseModel):
    columns: list[str]
    data: list[dict[str, Any]]
    truncated: bool
    limit: int


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    order_date: datetime
    scheduled_days: int = Field(ge=0, le=7)
    quantity: int = Field(ge=1, le=1000000)
    net_sales: float = Field(ge=0, le=1000000000)
    item_count: int = Field(ge=1, le=100000)
    market: str = Field(min_length=1, max_length=100)
    region: str = Field(min_length=1, max_length=100)
    customer_segment: str = Field(min_length=1, max_length=100)
    payment_type: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid_quantity(self):
        if self.quantity < self.item_count:
            raise ValueError("Quantity must be at least the number of item lines")
        if self.order_date.tzinfo is not None:
            raise ValueError("Use a local business datetime without a timezone, matching the dataset")
        return self


class ExplanationIdentity(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    model_name: str
    model_version: str
    dataset_fingerprint: str


class GlobalImportanceRow(BaseModel):
    feature: str
    label: str
    columns: list[str]
    importance: float
    std: float = Field(ge=0)


class GlobalExplanation(ExplanationIdentity):
    method: str
    metric: str
    scope: str
    grouping: str
    rows: int = Field(ge=2)
    repeats: int = Field(ge=1)
    baseline_score: float = Field(ge=0, le=1)
    limitations: str
    features: list[GlobalImportanceRow]
    start: str
    end: str
    shap: "ShapGlobal"


class ShapGlobalRow(GlobalImportanceRow):
    signed_mean: float


class ShapGlobal(ExplanationIdentity):
    method: str
    metric: str
    output_space: Literal['probability', 'log_odds']
    scope: str
    rows: int = Field(ge=1)
    reference_rows: int = Field(ge=1)
    base_value: float
    max_additivity_error: float = Field(ge=0)
    encoded_feature_names: list[str]
    variation: str
    limitations: str
    features: list[ShapGlobalRow]


class LocalImportanceRow(BaseModel):
    feature: str
    label: str
    columns: list[str]
    observed_values: dict[str, str | float]
    contribution: float


class LocalExplanation(ExplanationIdentity):
    method: str
    approximate: bool
    scope: str
    interpretation: str
    limitations: str
    reference_rows: int = Field(ge=1)
    features: list[LocalImportanceRow]
    output_space: Literal['probability', 'log_odds']
    base_value: float
    output_probability: float = Field(ge=0, le=1)
    additivity_error: float = Field(ge=0)


class Recommendation(BaseModel):
    rule_id: str
    title: str
    action: str
    trigger: str
    feature: str | None
    shap_value: float | None


class PredictionResponse(ExplanationIdentity):
    delay_probability: float = Field(ge=0, le=1)
    predicted_delayed: bool
    threshold: float
    scope: str
    local_explanation: LocalExplanation
    recommendations: list[Recommendation]


class SummaryRequest(PredictionRequest):
    expected_model_version: str = Field(min_length=1, max_length=80)


class SummaryResponse(ExplanationIdentity):
    summary: str
    provider: str
    assistant_model: str
    notice: str


class NaturalQueryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=5, max_length=2000)


class NaturalQueryResponse(QueryResponse):
    generated_sql: str
    question: str
    provider: str
    assistant_model: str


class Overview(BaseModel):
    total_orders: int
    delayed_orders: int
    delay_rate: float | None
    on_time_rate: float | None
    average_shipping_days: float | None
    average_scheduled_days: float | None
    average_delay_days: float | None


class AnalysisRow(BaseModel):
    label: str
    total_orders: int
    delayed_orders: int
    delay_rate: float
    average_delay_days: float


class HeatmapCell(BaseModel):
    region: str
    shipping_mode: str
    total_orders: int = Field(ge=1)
    delayed_orders: int = Field(ge=0)
    delay_rate: float = Field(ge=0, le=1)


class AnalyticsResponse(BaseModel):
    overview: Overview
    views: dict[str, list[AnalysisRow]]
    options: dict[str, list[str]]
    definition: str
    heatmap: list[HeatmapCell]


class GeographicCountry(BaseModel):
    country: str
    code: str
    source_labels: list[str]
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    total_orders: int = Field(ge=1)
    delayed_orders: int = Field(ge=0)
    delay_rate: float = Field(ge=0, le=1)


class UnmappedCountry(BaseModel):
    country: str
    total_orders: int = Field(ge=1)
    delayed_orders: int = Field(ge=0)


class GeographicResponse(BaseModel):
    total_orders: int = Field(ge=0)
    delayed_orders: int = Field(ge=0)
    countries: list[GeographicCountry]
    unmapped: list[UnmappedCountry]
    unmapped_orders: int = Field(ge=0)
    unmapped_delayed_orders: int = Field(ge=0)
    svg: str
    dataset_job_id: str | None
    location_scope: str
    source: str
    definition: str


class JobStatus(BaseModel):
    id: str | None = None
    state: Literal["idle", "running", "completed", "failed"]
    stage: str
    error: str | None = None


class ModelReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    state: Literal["trained", "loaded", "unavailable"]
    message: str | None = None


class SystemStatus(BaseModel):
    mode: Literal["local", "hdfs"]
    source: str
    job: JobStatus
    data_ready: bool
    quality: dict[str, Any] | None
    model: ModelReport


class IngestResponse(BaseModel):
    job: JobStatus
