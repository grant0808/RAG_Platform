from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from foundry.core.config import Settings

Number = int | float


class ProviderQuotaService:
    """Fetch provider-side usage/cost data for the local /status command.

    Provider Admin APIs do not expose one identical "remaining quota" primitive.
    This service returns actual usage/cost data when admin keys are configured and
    marks provider-specific remaining quota as unavailable when the provider does
    not expose it through the APIs used here.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = httpx.Timeout(settings.provider_timeout_seconds)

    async def status(self) -> dict[str, Any]:
        period = _current_month_window()
        return {
            "period": {
                "start": period["start_iso"],
                "end": period["end_iso"],
                "bucket_width": "1d",
            },
            "openai": await self._openai_status(period),
            "anthropic": await self._anthropic_status(period),
        }

    async def _openai_status(self, period: dict[str, Any]) -> dict[str, Any]:
        api_key = _secret_value(self.settings.openai_admin_api_key)
        if not api_key:
            return _not_configured(
                "Set FOUNDRY_OPENAI_ADMIN_API_KEY to enable org usage/cost lookup."
            )

        headers = {"Authorization": f"Bearer {api_key}"}
        usage_params = {"start_time": period["start_unix"], "bucket_width": "1d"}
        cost_params = {"start_time": period["start_unix"], "bucket_width": "1d"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            usage = await _safe_get_json(
                client,
                "https://api.openai.com/v1/organization/usage/completions",
                headers=headers,
                params=usage_params,
            )
            costs = await _safe_get_json(
                client,
                "https://api.openai.com/v1/organization/costs",
                headers=headers,
                params=cost_params,
            )

        return {
            "configured": True,
            "usage": _usage_summary(
                usage,
                token_keys={
                    "input_tokens",
                    "output_tokens",
                    "input_cached_tokens",
                    "input_audio_tokens",
                    "output_audio_tokens",
                },
                request_keys={"num_model_requests"},
            ),
            "cost": _cost_summary(costs, amount_keys={"amount", "cost"}),
            "remaining": {
                "available": False,
                "reason": (
                    "OpenAI usage/cost endpoints return actual usage and cost, "
                    "not a universal remaining quota value."
                ),
            },
        }

    async def _anthropic_status(self, period: dict[str, Any]) -> dict[str, Any]:
        api_key = _secret_value(self.settings.anthropic_admin_api_key)
        if not api_key:
            return _not_configured(
                "Set FOUNDRY_ANTHROPIC_ADMIN_API_KEY to enable org usage/cost lookup."
            )

        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        report_params = {
            "starting_at": period["start_iso"],
            "ending_at": period["end_iso"],
            "bucket_width": "1d",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            usage = await _safe_get_json(
                client,
                "https://api.anthropic.com/v1/organizations/usage_report/messages",
                headers=headers,
                params=report_params,
            )
            costs = await _safe_get_json(
                client,
                "https://api.anthropic.com/v1/organizations/cost_report",
                headers=headers,
                params={
                    "starting_at": period["start_iso"],
                    "ending_at": period["end_iso"],
                },
            )
            spend_limits = await _safe_get_json(
                client,
                "https://api.anthropic.com/v1/organizations/spend_limits/effective",
                headers=headers,
                params={"limit": 100},
            )

        return {
            "configured": True,
            "usage": _usage_summary(
                usage,
                token_keys={
                    "input_tokens",
                    "output_tokens",
                    "uncached_input_tokens",
                    "cached_input_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                    "server_tool_use_input_tokens",
                    "server_tool_use_output_tokens",
                },
                request_keys={"requests", "num_model_requests", "message_count"},
            ),
            "cost": _cost_summary(costs, amount_keys={"amount", "cost", "amount_usd"}),
            "remaining": _anthropic_remaining_summary(spend_limits),
        }


async def _safe_get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any],
) -> dict[str, Any]:
    try:
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "available": False,
            "status_code": exc.response.status_code,
            "error": _provider_error_message(exc.response.status_code),
        }
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "error": f"Provider quota lookup failed: {type(exc).__name__}"}

    return {"available": True, "data": payload}


def _usage_summary(
    response: dict[str, Any],
    *,
    token_keys: set[str],
    request_keys: set[str],
) -> dict[str, Any]:
    if not response.get("available"):
        return response

    data = response.get("data", {})
    tokens = {key: int(_sum_numeric_values(data, {key})) for key in sorted(token_keys)}
    requests = {key: int(_sum_numeric_values(data, {key})) for key in sorted(request_keys)}
    total_tokens = sum(tokens.values())
    return {
        "available": True,
        "total_tokens": total_tokens,
        "tokens": {key: value for key, value in tokens.items() if value},
        "requests": {key: value for key, value in requests.items() if value},
    }


def _cost_summary(response: dict[str, Any], *, amount_keys: set[str]) -> dict[str, Any]:
    if not response.get("available"):
        return response

    data = response.get("data", {})
    total_amount = _sum_numeric_values(data, amount_keys)
    currency = _first_string_value(data, {"currency"}) or "USD"
    return {
        "available": True,
        "amount": round(total_amount, 6),
        "currency": currency.upper(),
        "note": "Provider-specific report schemas may express nested amount fields differently.",
    }


def _anthropic_remaining_summary(response: dict[str, Any]) -> dict[str, Any]:
    if not response.get("available"):
        result = dict(response)
        result["reason"] = (
            "Anthropic Spend Limits API requires Claude Enterprise and an admin key with "
            "read:spend_limits scope."
        )
        return result

    data = response.get("data", {})
    rows = _collect_dicts(data)
    limited_rows = [
        row
        for row in rows
        if _as_number(row.get("amount")) is not None
        and _as_number(row.get("period_to_date_spend")) is not None
    ]
    unlimited_count = sum(1 for row in rows if row.get("amount") is None and "amount" in row)
    amount_minor = sum(float(_as_number(row.get("amount")) or 0) for row in limited_rows)
    spend_minor = sum(
        float(_as_number(row.get("period_to_date_spend")) or 0) for row in limited_rows
    )

    return {
        "available": True,
        "amount_usd": round(amount_minor / 100, 6),
        "period_to_date_spend_usd": round(spend_minor / 100, 6),
        "remaining_usd": round((amount_minor - spend_minor) / 100, 6),
        "unlimited_limit_count": unlimited_count,
    }


def _sum_numeric_values(value: Any, keys: set[str]) -> float:
    if isinstance(value, dict):
        total = 0.0
        for key, item in value.items():
            if key in keys:
                number = _as_number(item)
                if number is None and isinstance(item, dict):
                    number = _as_number(item.get("value"))
                if number is not None:
                    total += float(number)
            total += _sum_numeric_values(item, keys)
        return total
    if isinstance(value, list):
        return sum(_sum_numeric_values(item, keys) for item in value)
    return 0.0


def _first_string_value(value: Any, keys: set[str]) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys and isinstance(item, str):
                return item
            found = _first_string_value(item, keys)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _first_string_value(item, keys)
            if found:
                return found
    return None


def _collect_dicts(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        rows.append(value)
        for item in value.values():
            rows.extend(_collect_dicts(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_collect_dicts(item))
    return rows


def _as_number(value: Any) -> Number | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _provider_error_message(status_code: int) -> str:
    if status_code in {401, 403}:
        return "Admin API key was rejected or lacks required organization usage permissions."
    return f"Provider returned HTTP {status_code}."


def _not_configured(reason: str) -> dict[str, Any]:
    return {"configured": False, "available": False, "reason": reason}


def _secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None


def _current_month_window() -> dict[str, Any]:
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return {
        "start_unix": int(start.timestamp()),
        "start_iso": _iso_z(start),
        "end_iso": _iso_z(now),
    }


def _iso_z(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
