from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from passport_auth.api.v1.dashboard_auth import get_current_dashboard_user, require_owner
from passport_auth.setup.store import OwnerAccount

router = APIRouter(prefix="/dashboard/analytics", tags=["dashboard-analytics"])


class AnalyticsOverview(BaseModel):
    dau: int
    wau: int
    mau: int
    signups: int
    logins: int
    login_success_rate: float
    failures: int
    refreshes: int
    active_users: int


class RetentionMetric(BaseModel):
    label: str
    value: float


class MethodMetric(BaseModel):
    method: str
    count: int


class RecentAnalyticsEvent(BaseModel):
    event_type: str
    auth_method: str
    status: str
    email: str
    occurred_at: str
    reason: str


class AnalyticsSummaryResponse(BaseModel):
    enabled: bool
    reason: str
    overview: AnalyticsOverview
    retention: list[RetentionMetric]
    methods: list[MethodMetric]
    recent_events: list[RecentAnalyticsEvent]


@router.get("/summary")
def get_analytics_summary(
    request: Request,
    owner: Annotated[OwnerAccount, Depends(get_current_dashboard_user)],
) -> AnalyticsSummaryResponse:
    require_owner(owner)
    return AnalyticsSummaryResponse.model_validate(request.app.state.analytics_reader.summary())
