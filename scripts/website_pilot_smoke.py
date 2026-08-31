import argparse
import json
import sys

import httpx


def fail(message, payload=None):
    print(f"FAIL: {message}", file=sys.stderr)
    if payload is not None:
        print(json.dumps(payload, indent=2, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)


def request(client, method, path, **kwargs):
    response = client.request(method, path, timeout=20, **kwargs)
    try:
        payload = response.json()
    except Exception:
        payload = {"text": response.text}
    if response.status_code >= 400:
        fail(f"{method} {path} -> {response.status_code}", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description="Run an end-to-end Xvond Website AI pilot smoke check")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--company-id", required=True, type=int)
    parser.add_argument("--agent-id", required=True, type=int)
    parser.add_argument("--domain", required=True)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    with httpx.Client(base_url=base_url, follow_redirects=True) as client:
        login = request(
            client,
            "POST",
            "/auth/login",
            json={"email": args.email, "password": args.password},
        )
        token = login.get("access_token")
        if not token:
            fail("Login succeeded without access_token", login)
        client.headers.update({"Authorization": f"Bearer {token}"})

        before = request(
            client,
            "GET",
            f"/admin/delivery-readiness/companies/{args.company_id}/agents/{args.agent_id}",
        )
        print("Initial lifecycle:", before.get("lifecycle"))
        print("Initial blockers:", before.get("blockers") or [])

        website = request(
            client,
            "PUT",
            f"/admin/website-channel/agents/{args.agent_id}",
            json={
                "allowed_domain": args.domain,
                "widget_name": "Xvond Pilot",
                "welcome_message": "مرحباً، كيف يمكنني مساعدتك؟",
                "position": "right",
                "accent_color": "#111827",
                "launcher_label": "Chat",
            },
        )
        channel_id = website.get("channel_id")
        if not channel_id:
            fail("Website configuration did not return channel_id", website)

        setup = request(
            client,
            "GET",
            f"/admin/delivery-readiness/companies/{args.company_id}/agents/{args.agent_id}",
        )
        if not setup.get("setup_ready"):
            fail("Pilot is not ready to go live", setup)

        live = request(
            client,
            "POST",
            f"/admin/delivery-readiness/companies/{args.company_id}/agents/{args.agent_id}/go-live",
        )
        if live.get("lifecycle") != "live":
            fail("Employee did not enter live lifecycle", live)

        request(client, "POST", f"/admin/website-channel/{channel_id}/activate")

        final = request(
            client,
            "GET",
            f"/admin/delivery-readiness/companies/{args.company_id}/agents/{args.agent_id}",
        )
        if not final.get("ready_for_customer"):
            fail("Employee is live but not ready for customer", final)

        widget = client.get(f"/channels/website/{channel_id}/widget.js", timeout=20)
        if widget.status_code != 200 or "__xvondWidget" not in widget.text:
            fail(
                "Public widget endpoint is not serving the live widget",
                {"status_code": widget.status_code, "body": widget.text[:500]},
            )

        print("PASS: Website pilot is live and ready for customer")
        print(json.dumps({
            "company_id": args.company_id,
            "agent_id": args.agent_id,
            "channel_id": channel_id,
            "ready_for_customer": True,
            "embed_code": website.get("embed_code"),
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
