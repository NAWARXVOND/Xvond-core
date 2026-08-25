from pathlib import Path

SOURCE = Path("backend/app/api/whatsapp_webhook.py").read_text(encoding="utf-8")


def test_unknown_phone_numbers_are_not_queued():
    assert "matched_channels == 0" in SOURCE
    assert '"unknown_phone_number_id"' in SOURCE


def test_failed_delivery_releases_claim_for_worker_retry():
    assert "whatsapp.reply_retry_scheduled" in SOURCE
    assert "release_message_claim(" in SOURCE
    assert "WhatsApp reply delivery failed" in SOURCE


def test_failed_delivery_rolls_back_business_actions_before_retry():
    failure_position = SOURCE.index('if not send_result.get("success"):', SOURCE.index("reply_text"))
    rollback_position = SOURCE.index("db.rollback()", failure_position)
    release_position = SOURCE.index("release_message_claim(", rollback_position)
    retry_position = SOURCE.index("WhatsApp reply delivery failed", release_position)

    assert failure_position < rollback_position < release_position < retry_position
    assert "commit=False" in SOURCE
