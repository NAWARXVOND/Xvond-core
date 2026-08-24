import json
import urllib.request
import urllib.error


class WhatsAppSender:

    def send_text(
        self,
        config: dict,
        to: str,
        text: str,
    ) -> dict:

        phone_number_id = config.get(
            "phone_number_id"
        )

        access_token = config.get(
            "access_token"
        )

        graph_api_version = config.get(
            "graph_api_version"
        )

        if not phone_number_id:
            raise ValueError(
                "WhatsApp phone_number_id is not configured"
            )

        if not access_token:
            raise ValueError(
                "WhatsApp access_token is not configured"
            )

        if not graph_api_version:
            raise ValueError(
                "WhatsApp graph_api_version is not configured"
            )

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
            "text": {
                "body": text,
            },
        }

        request = urllib.request.Request(
            url=url,
            data=json.dumps(
                payload
            ).encode("utf-8"),
            headers={
                "Authorization":
                    f"Bearer {access_token}",
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=20,
            ) as response:

                body = response.read().decode(
                    "utf-8"
                )

                return {
                    "success": True,
                    "status_code":
                        response.status,
                    "response":
                        json.loads(body)
                        if body
                        else {},
                }

        except urllib.error.HTTPError as exc:

            body = exc.read().decode(
                "utf-8",
                errors="replace",
            )

            return {
                "success": False,
                "status_code": exc.code,
                "error": body,
            }

        except Exception as exc:

            return {
                "success": False,
                "error": str(exc),
            }


whatsapp_sender = WhatsAppSender()
