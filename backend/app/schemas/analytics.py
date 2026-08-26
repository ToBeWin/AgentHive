from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsTotals(BaseModel):
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    success_rate: float = 0.0


class ModelUsageItem(BaseModel):
    model_key: str
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


class DailyUsageItem(BaseModel):
    date: date
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


class DepartmentUsageItem(BaseModel):
    department_id: UUID | None = None
    department_name: str
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


class UserUsageItem(BaseModel):
    user_id: UUID | None = None
    user_name: str
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


class AgentUsageItem(BaseModel):
    agent_id: UUID | None = None
    agent_name: str
    agent_key: str | None = None
    tokens: int = 0
    cost_usd: float = 0.0
    requests: int = 0


class AnalyticsOverviewResponse(BaseModel):
    totals: AnalyticsTotals = Field(default_factory=AnalyticsTotals)
    model_usage: list[ModelUsageItem] = Field(default_factory=list)
    daily_usage: list[DailyUsageItem] = Field(default_factory=list)
    department_usage: list[DepartmentUsageItem] = Field(default_factory=list)
    user_usage: list[UserUsageItem] = Field(default_factory=list)
    agent_usage: list[AgentUsageItem] = Field(default_factory=list)
    generated_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)
