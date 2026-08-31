from pathlib import Path


SMOKE = Path("scripts/website_pilot_smoke.py").read_text(encoding="utf-8")


def test_smoke_authenticates_with_real_admin_login():
    assert '"/auth/login"' in SMOKE
    assert 'Authorization' in SMOKE
    assert 'Bearer {token}' in SMOKE


def test_smoke_runs_real_delivery_lifecycle():
    assert '/admin/website-channel/agents/{args.agent_id}' in SMOKE
    assert '/admin/delivery-readiness/companies/{args.company_id}/agents/{args.agent_id}' in SMOKE
    assert '/go-live' in SMOKE
    assert '/admin/website-channel/{channel_id}/activate' in SMOKE
    assert 'ready_for_customer' in SMOKE


def test_smoke_verifies_public_widget_after_activation():
    assert '/channels/website/{channel_id}/widget.js' in SMOKE
    assert '__xvondWidget' in SMOKE
    assert 'PASS: Website pilot is live and ready for customer' in SMOKE
