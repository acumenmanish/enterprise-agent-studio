import asyncio
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings

PREVIEW_LIMIT = 25
PREVIEW_FIELDS = {
    "order": (
        "order_id",
        "order_no",
        "ord_rec_date",
        "ord_cname",
        "ord_pname",
        "ord_qty",
        "proceed_qty",
        "ord_del_date",
        "job_status",
    ),
    "machine": (
        "machine_id",
        "machine_name",
        "unit_id",
        "per_day",
        "totalhrs",
        "shift_a",
        "shift_b",
        "shift_c",
        "speed_std",
        "speed_unit",
        "package",
    ),
    "operation": (
        "opt_id",
        "opt_group",
        "machine_id",
        "opt_name",
        "mc_speed",
        "based_on",
        "package",
    ),
    "schedule": (
        "wo_id",
        "operation",
        "machine_id",
        "machine",
        "to_datetime",
        "schedule_hrs",
    ),
}


class ERPConnectorError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def erp_connection_status(
    settings: Settings,
    endpoint_override: str | None = None,
    credential_override_configured: bool = False,
) -> dict[str, Any]:
    endpoint = endpoint_override or settings.erp_query_api_url
    credential_configured = credential_override_configured or bool(
        settings.erp_api_token and settings.erp_api_token.get_secret_value().strip()
    )
    return {
        "configured": bool(endpoint and endpoint.strip() and credential_configured),
        "endpoint_configured": bool(endpoint and endpoint.strip()),
        "credential_configured": credential_configured,
        "endpoint": endpoint.strip() if endpoint and endpoint.strip() else None,
        "key_source": (
            "agent-override"
            if credential_override_configured
            else "environment"
            if credential_configured
            else None
        ),
    }


def _validated_connection(
    settings: Settings,
    endpoint_override: str | None = None,
    api_token_override: str | None = None,
) -> tuple[str, str]:
    endpoint = endpoint_override or settings.erp_query_api_url
    token = api_token_override or (
        settings.erp_api_token.get_secret_value() if settings.erp_api_token else None
    )
    if not endpoint or not endpoint.strip() or not token or not token.strip():
        raise ERPConnectorError(
            "ERP API is not configured. Set ERP_QUERY_API_URL and ERP_API_TOKEN "
            "in the backend environment.",
            status_code=503,
        )

    endpoint = endpoint.strip()
    token = token.strip()
    validate_erp_endpoint(endpoint, token)
    return endpoint, token


def validate_erp_endpoint(endpoint: str, token: str) -> None:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or not parsed.path.rstrip("/").endswith("/ai_agent_query_api.php")
    ):
        raise ERPConnectorError(
            "ERP_QUERY_API_URL must be the full ai_agent_query_api.php endpoint URL.",
            status_code=503,
        )
    if parsed.scheme != "https" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ERPConnectorError(
            "ERP_QUERY_API_URL must use HTTPS except for a loopback development endpoint.",
            status_code=503,
        )


async def _select(
    client: httpx.AsyncClient,
    endpoint: str,
    token: str,
    table: str,
) -> dict[str, Any]:
    filters = {"status": "open"} if table == "order" else {}
    try:
        response = await client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Cache-Control": "no-store, no-cache",
                "Referrer-Policy": "no-referrer",
            },
            json={
                "action": "select",
                "table": table,
                "filters": filters,
                "limit": PREVIEW_LIMIT,
                "offset": 0,
            },
        )
    except httpx.TimeoutException as exc:
        raise ERPConnectorError("ERP query API timed out.") from exc
    except httpx.RequestError as exc:
        raise ERPConnectorError("ERP query API could not be reached.") from exc

    if response.status_code == 401:
        raise ERPConnectorError(
            "ERP query API rejected the bearer token. Check that the ERP session "
            "or API key is active.",
            status_code=401,
        )
    if response.status_code == 403:
        raise ERPConnectorError(
            "ERP query API denied access. Check that Smart Schedule AI Agent access is enabled.",
            status_code=403,
        )
    if response.is_error:
        raise ERPConnectorError(f"ERP query API returned HTTP {response.status_code}.")

    try:
        result = response.json()
    except ValueError as exc:
        raise ERPConnectorError("ERP query API returned invalid JSON.") from exc
    if (
        not isinstance(result, dict)
        or result.get("status") != "success"
        or result.get("table") != table
        or not isinstance(result.get("data"), list)
        or any(not isinstance(row, dict) for row in result["data"])
    ):
        raise ERPConnectorError(
            f"ERP query API returned an invalid response for the {table} alias."
        )
    return result


async def preview_erp_data(
    settings: Settings,
    endpoint_override: str | None = None,
    api_token_override: str | None = None,
) -> dict[str, Any]:
    endpoint, token = _validated_connection(settings, endpoint_override, api_token_override)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
        results = await asyncio.gather(
            *(_select(client, endpoint, token, table) for table in PREVIEW_FIELDS)
        )

    datasets = []
    for table, result in zip(PREVIEW_FIELDS, results, strict=True):
        source_rows = result["data"][:PREVIEW_LIMIT]
        records = [
            {key: row[key] for key in PREVIEW_FIELDS[table] if key in row} for row in source_rows
        ]
        total = result.get("total")
        datasets.append(
            {
                "alias": table,
                "count": len(records),
                "total": total if isinstance(total, int) and total >= 0 else len(records),
                "has_more": (
                    result.get("has_more") is True
                    or (isinstance(total, int) and total > PREVIEW_LIMIT)
                ),
                "records": records,
            }
        )

    return {
        "connected": True,
        "read_only": True,
        "preview_limit": PREVIEW_LIMIT,
        "datasets": datasets,
        "data_gaps": [
            {
                "entity": "materials / inventory",
                "available": False,
                "reason": "No inventory alias is enabled in the shared API documentation.",
            },
            {
                "entity": "maintenance",
                "available": False,
                "reason": "The API documentation marks the maintenance alias as disabled.",
            },
            {
                "entity": "changeover matrix",
                "available": False,
                "reason": "No changeover matrix alias is enabled in the shared API documentation.",
            },
        ],
    }
