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


class NoopAnalyticsSink:
    def record_public_auth_event(self, event: PublicAuthAnalyticsEvent) -> None:
        return None


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


def create_analytics_sink(settings: Settings) -> AnalyticsSink:
    if settings.app_env != "production" or not settings.clickhouse_url:
        return NoopAnalyticsSink()
    return ClickHouseAnalyticsSink(settings.clickhouse_url)


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
