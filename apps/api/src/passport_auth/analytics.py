from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from passport_auth.core.config import Settings


@dataclass(frozen=True)
class PublicAuthAnalyticsEvent:
    event_type: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    auth_method: str = ""
    status: str = "success"
    user_id: str = ""
    email: str = ""
    redirect_url: str = ""
    origin: str = ""
    reason: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


class AnalyticsSink(Protocol):
    def record_public_auth_event(self, event: PublicAuthAnalyticsEvent) -> None: ...


class AnalyticsReader(Protocol):
    def summary(self) -> dict[str, Any]: ...


class NoopAnalyticsSink:
    def record_public_auth_event(self, event: PublicAuthAnalyticsEvent) -> None:
        return None


def disabled_analytics_summary() -> dict[str, Any]:
    return {
        "enabled": False,
        "reason": "Analytics are only recorded in production with ClickHouse enabled.",
        "overview": {
            "dau": 0,
            "wau": 0,
            "mau": 0,
            "signups": 0,
            "logins": 0,
            "login_success_rate": 0.0,
            "failures": 0,
            "refreshes": 0,
            "active_users": 0,
        },
        "retention": [
            {"label": "Week 1", "value": 0.0},
            {"label": "Week 2", "value": 0.0},
            {"label": "Week 3", "value": 0.0},
            {"label": "Week 4", "value": 0.0},
        ],
        "methods": [],
        "recent_events": [],
    }


class NoopAnalyticsReader:
    def summary(self) -> dict[str, Any]:
        return disabled_analytics_summary()


class ClickHouseAnalyticsSink:
    def __init__(self, clickhouse_url: str) -> None:
        self.clickhouse_url = clickhouse_url
        self._table_ready = False

    def record_public_auth_event(self, event: PublicAuthAnalyticsEvent) -> None:
        try:
            self._ensure_table()
            self._post_query(
                "INSERT INTO auth_events FORMAT JSONEachRow\n"
                + json.dumps(
                    {
                        "occurred_at": clickhouse_datetime(event.occurred_at),
                        "event_type": event.event_type,
                        "auth_method": event.auth_method,
                        "status": event.status,
                        "user_id": event.user_id,
                        "email": event.email,
                        "redirect_url": event.redirect_url,
                        "origin": event.origin,
                        "reason": event.reason,
                        "properties_json": json.dumps(event.properties, sort_keys=True),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
        except OSError:
            return None

    def _ensure_table(self) -> None:
        if self._table_ready:
            return

        self._post_query(
            """
CREATE TABLE IF NOT EXISTS auth_events
(
    occurred_at DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    auth_method LowCardinality(String),
    status LowCardinality(String),
    user_id String,
    email String,
    redirect_url String,
    origin String,
    reason String,
    properties_json String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(occurred_at)
ORDER BY (occurred_at, event_type, user_id)
TTL occurred_at + INTERVAL 12 MONTH DELETE
""".strip()
        )
        self._table_ready = True

    def _post_query(self, query: str) -> None:
        endpoint, auth_header = clickhouse_request_target(self.clickhouse_url)
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        if auth_header:
            headers["Authorization"] = auth_header
        request = urllib.request.Request(
            endpoint,
            data=query.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            response.read()


class ClickHouseAnalyticsReader:
    def __init__(self, clickhouse_url: str) -> None:
        self.clickhouse_url = clickhouse_url

    def summary(self) -> dict[str, Any]:
        try:
            overview = self._overview()
            return {
                "enabled": True,
                "reason": "",
                "overview": overview,
                "retention": self._retention(),
                "methods": self._methods(),
                "recent_events": self._recent_events(),
            }
        except OSError:
            summary = disabled_analytics_summary()
            summary["reason"] = "ClickHouse analytics are configured but currently unreachable."
            return summary

    def _overview(self) -> dict[str, Any]:
        rows = self._query_rows(
            """
SELECT
    uniqIf(
        user_id,
        user_id != ''
        AND event_type IN ('login_success', 'token_refresh', 'active_user')
        AND occurred_at >= now() - INTERVAL 1 DAY
    ) AS dau,
    uniqIf(
        user_id,
        user_id != ''
        AND event_type IN ('login_success', 'token_refresh', 'active_user')
        AND occurred_at >= now() - INTERVAL 7 DAY
    ) AS wau,
    uniqIf(
        user_id,
        user_id != ''
        AND event_type IN ('login_success', 'token_refresh', 'active_user')
        AND occurred_at >= now() - INTERVAL 30 DAY
    ) AS mau,
    countIf(
        event_type = 'registration_completed'
        AND status = 'success'
        AND occurred_at >= now() - INTERVAL 30 DAY
    ) AS signups,
    countIf(
        event_type = 'login_success'
        AND status = 'success'
        AND occurred_at >= now() - INTERVAL 30 DAY
    ) AS logins,
    countIf(status = 'failure' AND occurred_at >= now() - INTERVAL 30 DAY) AS failures,
    countIf(
        event_type = 'token_refresh'
        AND status = 'success'
        AND occurred_at >= now() - INTERVAL 30 DAY
    ) AS refreshes,
    uniqIf(user_id, user_id != '' AND occurred_at >= now() - INTERVAL 30 DAY) AS active_users,
    round(
        if(
            countIf(
                event_type IN ('login_success', 'login_failure')
                AND occurred_at >= now() - INTERVAL 30 DAY
            ) = 0,
            0,
            countIf(
                event_type = 'login_success'
                AND status = 'success'
                AND occurred_at >= now() - INTERVAL 30 DAY
            )
            / countIf(
                event_type IN ('login_success', 'login_failure')
                AND occurred_at >= now() - INTERVAL 30 DAY
            )
            * 100
        ),
        1
    ) AS login_success_rate
FROM auth_events
FORMAT JSONEachRow
""".strip()
        )
        row = rows[0] if rows else {}
        return {
            "dau": int(row.get("dau") or 0),
            "wau": int(row.get("wau") or 0),
            "mau": int(row.get("mau") or 0),
            "signups": int(row.get("signups") or 0),
            "logins": int(row.get("logins") or 0),
            "login_success_rate": float(row.get("login_success_rate") or 0.0),
            "failures": int(row.get("failures") or 0),
            "refreshes": int(row.get("refreshes") or 0),
            "active_users": int(row.get("active_users") or 0),
        }

    def _retention(self) -> list[dict[str, Any]]:
        try:
            rows = self._query_rows(
                """
WITH cohorts AS
(
    SELECT user_id, min(occurred_at) AS registered_at
    FROM auth_events
    WHERE event_type = 'registration_completed'
      AND status = 'success'
      AND user_id != ''
      AND occurred_at >= now() - INTERVAL 120 DAY
    GROUP BY user_id
)
SELECT
    concat('Week ', toString(week_number)) AS label,
    round(
        if(
            countDistinct(cohorts.user_id) = 0,
            0,
            uniqIf(
                auth_events.user_id,
                auth_events.event_type IN ('login_success', 'token_refresh', 'active_user')
                AND auth_events.occurred_at >= cohorts.registered_at + toIntervalWeek(week_number)
                AND auth_events.occurred_at
                    < cohorts.registered_at + toIntervalWeek(week_number + 1)
            ) / countDistinct(cohorts.user_id) * 100
        ),
        1
    ) AS value
FROM cohorts
CROSS JOIN (SELECT arrayJoin([1, 2, 3, 4]) AS week_number)
LEFT JOIN auth_events ON auth_events.user_id = cohorts.user_id
GROUP BY week_number
ORDER BY week_number
FORMAT JSONEachRow
""".strip()
            )
        except OSError:
            return disabled_analytics_summary()["retention"]

        by_label = {str(row.get("label")): float(row.get("value") or 0.0) for row in rows}
        return [
            {"label": f"Week {week}", "value": by_label.get(f"Week {week}", 0.0)}
            for week in range(1, 5)
        ]

    def _methods(self) -> list[dict[str, Any]]:
        rows = self._query_rows(
            """
SELECT auth_method AS method, count() AS count
FROM auth_events
WHERE event_type = 'login_success'
  AND status = 'success'
  AND auth_method != ''
  AND occurred_at >= now() - INTERVAL 30 DAY
GROUP BY auth_method
ORDER BY count DESC
LIMIT 8
FORMAT JSONEachRow
""".strip()
        )
        return [
            {"method": str(row.get("method") or "unknown"), "count": int(row.get("count") or 0)}
            for row in rows
        ]

    def _recent_events(self) -> list[dict[str, Any]]:
        rows = self._query_rows(
            """
SELECT
    event_type,
    auth_method,
    status,
    email,
    reason,
    formatDateTime(occurred_at, '%FT%TZ', 'UTC') AS occurred_at
FROM auth_events
ORDER BY occurred_at DESC
LIMIT 12
FORMAT JSONEachRow
""".strip()
        )
        return [
            {
                "event_type": str(row.get("event_type") or ""),
                "auth_method": str(row.get("auth_method") or ""),
                "status": str(row.get("status") or ""),
                "email": str(row.get("email") or ""),
                "occurred_at": str(row.get("occurred_at") or ""),
                "reason": str(row.get("reason") or ""),
            }
            for row in rows
        ]

    def _query_rows(self, query: str) -> list[dict[str, Any]]:
        endpoint, auth_header = clickhouse_request_target(self.clickhouse_url)
        headers = {"Content-Type": "text/plain; charset=utf-8"}
        if auth_header:
            headers["Authorization"] = auth_header
        request = urllib.request.Request(
            endpoint,
            data=query.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            body = response.read().decode("utf-8")

        rows: list[dict[str, Any]] = []
        for line in body.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def create_analytics_sink(settings: Settings) -> AnalyticsSink:
    if settings.app_env != "production" or not settings.clickhouse_url:
        return NoopAnalyticsSink()
    return ClickHouseAnalyticsSink(settings.clickhouse_url)


def create_analytics_reader(settings: Settings) -> AnalyticsReader:
    if settings.app_env != "production" or not settings.clickhouse_url:
        return NoopAnalyticsReader()
    return ClickHouseAnalyticsReader(settings.clickhouse_url)


def should_record_public_auth_analytics(
    settings: Settings,
    *,
    redirect_url: str = "",
    origin: str = "",
) -> bool:
    if settings.app_env != "production":
        return False

    for url in (redirect_url, origin):
        if url and is_local_or_insecure_url(url):
            return False

    return True


def is_local_or_insecure_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme and parsed.scheme.lower() != "https":
        return True

    host = (parsed.hostname or "").lower()
    return (
        host == "localhost"
        or host.endswith(".localhost")
        or host == "::1"
        or host.startswith("127.")
    )


def clickhouse_request_target(clickhouse_url: str) -> tuple[str, str]:
    parsed = urllib.parse.urlsplit(clickhouse_url)
    if not parsed.scheme or not parsed.netloc:
        return clickhouse_url, ""

    host = parsed.hostname or ""
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"

    query = parsed.query
    database = parsed.path.strip("/")
    if database:
        query = urllib.parse.urlencode(
            [*urllib.parse.parse_qsl(query, keep_blank_values=True), ("database", database)]
        )

    endpoint = urllib.parse.urlunsplit((parsed.scheme, netloc, "/", query, ""))
    if not parsed.username:
        return endpoint, ""

    username = urllib.parse.unquote(parsed.username)
    password = urllib.parse.unquote(parsed.password or "")
    credentials = f"{username}:{password}"
    token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return endpoint, f"Basic {token}"


def clickhouse_datetime(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
