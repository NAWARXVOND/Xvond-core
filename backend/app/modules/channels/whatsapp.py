import json
import urllib.error
import urllib.request

from backend.app.core.error_safety import safe_error_metadata


class WhatsAppSender:

    @staticmethod
    def _provider_message_id(payload: dict) -> str | None:
        messages = payload.get("messages") if isinstance(payload, dict) else None
        if not isinstance(messages, list) or not messages:
            return None
        first = messages[0]
        if not isinstance(first, dict):
            return None
        value = str(first.get("id") or "").strip()
        return value or None

    def send_text(
        self,
        config: dict,
        to: str,
        text: str,
    ) -> dict:

        phone_number_id = config.get("phone_number_id")
        access_token = config.get("access_token")
        graph_api_version = config.get("graph_api_version")

        if not phone_number_id:
            raise ValueError("WhatsApp phone_number_id is not configured")
        if not access_token:
            raise ValueError("WhatsApp access_token is not configured")
        if not graph_api_version:
            raise ValueError("WhatsApp graph_api_version is not configured")

        url = (
            "https://graph.facebook.com/"
            + graph_api_version.strip("/")
            + "/"
            + str(phone_number_id)
            + "/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body) if body else {}
                return {
                    "success": True,
                    "status_code": response.status,
                    "provider_message_id": self._provider_message_id(parsed),
                    "delivery_certainty": "accepted",
                    "retryable": False,
                }
        except urllib.error.HTTPError as exc:
            # An HTTP response means Meta explicitly rejected this request. Do not
            # persist the response body: Graph errors can contain request details.
            return {
                "success": False,
                "status_code": exc.code,
                "delivery_certainty": "rejected",
                "retryable": int(exc.code or 0) >= 500 or int(exc.code or 0) == 429,
                "error_type": type(exc).__name__,
            }
        except Exception as exc:
            # A network/timeout exception is ambiguous: Meta may have accepted the
            # request before the connection failed. Never blindly resend it.
            return {
                "success": False,
                "delivery_certainty": "unknown",
                **safe_error_metadata(exc),
            }


whatsapp_sender = WhatsAppSender()
