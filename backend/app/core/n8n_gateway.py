from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx

from backend.app.core.config.settings import settings

logger = logging.getLogger("xvond.n8n")


class N8NGatewayError(RuntimeError):
    pass


class N8NActionGateway:
    """Outbound gateway from Xvond Core to the self-hosted n8n workflow entrypoint."""

    def __init__(self) -> None:
        self.enabled = settings.N8N_ENABLED
        self.webhook_url = settings.N8N_WEBHOOK_URL
        self.shared_secret = settings.N8N_SHARED_SECRET
        self.timeout_seconds = settings.N8N_TIMEOUT_SECONDS
        self.max_retries = settings.N8N_MAX_RETRIES

    def configured(self) -> bool:
        return bool(self.enabled and self.webhook_url and self.shared_secret)

    def execute(
        self,
        *,
        company_id: int,
        agent_id: int,
        action: str,
        data: dict[str, Any] | None = None,
        conversation_id: int | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise N8NGatewayError("n8n workflow execution is disabled")
        if not self.webhook_url:
            raise N8NGatewayError("N8N_WEBHOOK_URL is not configured")
        if not self.shared_secret:
            raise N8NGatewayError("N8N_SHARED_SECRET is not configured")

        normalized_action = str(action or "").strip()
        if not normalized_action:
            raise N8NGatewayError("n8n action is required")

        request_id = str(request_id or uuid.uuid4())
        payload = {
            "request_id": request_id,
            "company_id": company_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "action": normalized_action,
            "data": data or {},
        }
        headers = {
            "Content-Type": "application/json",
            "X-Xvond-N8N-Secret": self.shared_secret,
            "X-Xvond-Request-ID": request_id,
        }

        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = httpx.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                result = response.json()
                if not isinstance(result, dict):
                    raise N8NGatewayError("n8n returned a non-object response")
                if str(result.get("request_id") or request_id) != request_id:
                    raise N8NGatewayError("n8n response request_id mismatch")
                result.setdefault("request_id", request_id)
                result.setdefault("action", normalized_action)
                return result
            except (httpx.HTTPError, ValueError, N8NGatewayError) as exc:
                last_error = exc
                logger.warning(
                    "n8n workflow call failed",
                    extra={
                        "request_id": request_id,
                        "action": normalized_action,
                        "attempt": attempt,
                        "attempts": attempts,
                    },
                )
                if attempt < attempts:
                    time.sleep(min(0.25 * attempt, 1.0))

        raise N8NGatewayError(f"n8n workflow execution failed: {last_error}")


n8n_gateway = N8NActionGateway()
