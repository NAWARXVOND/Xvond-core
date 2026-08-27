from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from fastapi import HTTPException


VAPI_API_BASE = "https://api.vapi.ai"


def vapi_api_key() -> str:
    return str(os.getenv("VAPI_API_KEY") or "").strip()


def ensure_vapi_configured() -> str:
    api_key = vapi_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="VAPI_API_KEY is not configured on the Xvond server",
        )
    return api_key


def vapi_request(method: str, path: str, payload: dict | None = None):
    api_key = ensure_vapi_configured()
    url = VAPI_API_BASE + "/" + str(path or "").lstrip("/")
    body = None
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Vapi API error ({exc.code}): {raw[:800]}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Vapi API request failed: {exc}",
        ) from exc


def create_custom_llm_credential(api_key: str) -> dict:
    return vapi_request(
        "POST",
        "/credential",
        {"provider": "custom-llm", "apiKey": api_key},
    )


def create_assistant(payload: dict) -> dict:
    return vapi_request("POST", "/assistant", payload)


def update_assistant(assistant_id: str, payload: dict) -> dict:
    return vapi_request("PATCH", f"/assistant/{assistant_id}", payload)


def list_phone_numbers() -> list[dict]:
    payload = vapi_request("GET", "/phone-number")
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results", "phoneNumbers"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def get_phone_number(phone_number_id: str) -> dict:
    return vapi_request("GET", f"/phone-number/{phone_number_id}")


def attach_assistant_to_phone(phone_number_id: str, assistant_id: str) -> dict:
    return vapi_request(
        "PATCH",
        f"/phone-number/{phone_number_id}",
        {"assistantId": assistant_id},
    )
