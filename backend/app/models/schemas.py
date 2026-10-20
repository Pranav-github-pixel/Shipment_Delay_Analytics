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
    scheduled_days: float = Field(ge=0, le=365)
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


class PredictionResponse(BaseModel):
    delay_probability: float = Field(ge=0, le=1)
    predicted_delayed: bool
    threshold: float
    scope: str


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


class AnalyticsResponse(BaseModel):
    overview: Overview
    views: dict[str, list[AnalysisRow]]
    options: dict[str, list[str]]
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
