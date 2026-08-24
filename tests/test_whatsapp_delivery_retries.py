from pathlib import Path


SOURCE = Path(
    "backend/app/api/whatsapp_webhook.py"
).read_text(encoding="utf-8")


def test_unknown_phone_numbers_are_not_queued():
    assert "matched_channels == 0" in SOURCE
    assert '"unknown_phone_number_id"' in SOURCE


def test_failed_delivery_releases_claim_for_worker_retry():
    assert "whatsapp.reply_retry_scheduled" in SOURCE
    assert "release_message_claim(" in SOURCE
    assert "WhatsApp reply delivery failed" in SOURCE


def test_failed_delivery_rolls_back_conversation_before_retry():
    rollback_position = SOURCE.index(
        "# Roll back conversation/message writes"
    )
    release_position = SOURCE.index(
        "release_message_claim(",
        rollback_position,
    )

    assert SOURCE.index(
        "db.rollback()",
        rollback_position,
    ) < release_position
