
import hashlib
import hmac
import json

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
)

from sqlalchemy import text
from sqlalchemy.exc import (
    IntegrityError,
)

from backend.app.core.config_secrets import reveal_config
from backend.app.models.company_module import CompanyModule

from backend.app.core.agent_runtime import (
    agent_runtime,
)
from backend.app.core.database.connection import (
    SessionLocal,
)

from backend.app.modules.audit.service import (
    audit_service,
)
from backend.app.modules.channels.models import (
    AgentChannel,
)
from backend.app.modules.channels.whatsapp import (
    whatsapp_sender,
)
from backend.app.modules.channels.whatsapp_models import (
    WhatsAppInboundMessage,
    WhatsAppSession,
)


router = APIRouter(
    prefix="/webhooks/whatsapp",
    tags=["WhatsApp Webhook"],
)


def get_whatsapp_channels(
    db,
):

    return (
        db.query(
            AgentChannel
        )
        .join(
            CompanyModule,
            CompanyModule.company_id
            == AgentChannel.company_id,
        )
        .filter(
            AgentChannel.channel_type
            == "whatsapp",
            AgentChannel.enabled
            .is_(True),
            CompanyModule.module_name
            == "channels",
            CompanyModule.enabled
            .is_(True),
        )
        .all()
    )


def find_channel_by_phone_number_id(
    db,
    phone_number_id: str,
):

    return next(
        (
            channel
            for channel
            in get_whatsapp_channels(
                db
            )
            if str(
                (
                    reveal_config(
                    channel.config
                )
                ).get(
                    "phone_number_id",
                    "",
                )
            )
            == str(
                phone_number_id
            )
        ),
        None,
    )


def verify_signature(
    raw_body: bytes,
    signature: str | None,
    app_secret: str | None,
):

    if not app_secret:
        return False

    if not signature:
        return False

    expected = (
        "sha256="
        + hmac.new(
            app_secret.encode(
                "utf-8"
            ),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected,
        signature,
    )


def claim_message(
    db,
    message_id: str,
    company_id: int,
    agent_id: int,
    wa_id: str,
) -> bool:

    item = (
        WhatsAppInboundMessage(
            external_message_id=
                message_id,
            company_id=
                company_id,
            agent_id=
                agent_id,
            wa_id=
                wa_id,
        )
    )

    db.add(item)

    try:

        # Commit BEFORE running the agent.
        # Unique constraint becomes the
        # atomic idempotency lock.
        db.commit()

        return True

    except IntegrityError:

        db.rollback()

        return False


def release_message_claim(
    db,
    message_id: str,
):

    item = (
        db.query(
            WhatsAppInboundMessage
        )
        .filter(
            WhatsAppInboundMessage
            .external_message_id
            == message_id
        )
        .first()
    )

    if item is not None:
        db.delete(item)

    db.commit()


def lock_contact(
    db,
    agent_id: int,
    wa_id: str,
):

    # PostgreSQL transaction-level lock.
    # Messages from the same WhatsApp
    # contact are processed sequentially.
    key = (
        f"xvond-whatsapp:"
        f"{agent_id}:"
        f"{wa_id}"
    )

    db.execute(
        text(
            "SELECT "
            "pg_advisory_xact_lock("
            "hashtext(:key)"
            ")"
        ),
        {
            "key": key,
        },
    )


@router.get("")
def verify_webhook(
    mode: str | None = Query(
        default=None,
        alias="hub.mode",
    ),
    verify_token: str | None = Query(
        default=None,
        alias="hub.verify_token",
    ),
    challenge: str | None = Query(
        default=None,
        alias="hub.challenge",
    ),
):

    db = SessionLocal()

    try:

        if mode != "subscribe":
            raise HTTPException(
                status_code=403,
                detail=(
                    "Invalid webhook mode"
                ),
            )

        if not verify_token:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Verify token required"
                ),
            )

        for channel in (
            get_whatsapp_channels(
                db
            )
        ):

            config = (
                reveal_config(
                    channel.config
                )
            )

            stored_token = str(
                config.get(
                    "verify_token",
                    "",
                )
            )

            if (
                stored_token
                and hmac.compare_digest(
                    stored_token,
                    str(
                        verify_token
                    ),
                )
            ):
                return int(
                    challenge
                    or "0"
                )

        raise HTTPException(
            status_code=403,
            detail=(
                "Invalid verify token"
            ),
        )

    finally:
        db.close()


@router.post("")
async def receive_webhook(
    request: Request,
):

    raw_body = (
        await request.body()
    )

    try:

        payload = json.loads(
            raw_body.decode(
                "utf-8"
            )
        )

    except Exception:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid JSON payload"
            ),
        )

    if (
        payload.get("object")
        != "whatsapp_business_account"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid WhatsApp "
                "webhook object"
            ),
        )

    db = SessionLocal()

    processed = []

    try:

        for entry in payload.get(
            "entry",
            [],
        ):

            for change in entry.get(
                "changes",
                [],
            ):

                value = (
                    change.get(
                        "value",
                        {},
                    )
                    or {}
                )

                metadata = (
                    value.get(
                        "metadata",
                        {},
                    )
                    or {}
                )

                phone_number_id = str(
                    metadata.get(
                        "phone_number_id",
                        "",
                    )
                )

                if not phone_number_id:
                    continue

                channel = (
                    find_channel_by_phone_number_id(
                        db,
                        phone_number_id,
                    )
                )

                if channel is None:
                    continue

                config = (
                    reveal_config(
                    channel.config
                )
                )

                signature = (
                    request.headers.get(
                        "x-hub-signature-256"
                    )
                )

                if not verify_signature(
                    raw_body,
                    signature,
                    config.get(
                        "app_secret"
                    ),
                ):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "Invalid webhook "
                            "signature"
                        ),
                    )

                for message in (
                    value.get(
                        "messages",
                        [],
                    )
                ):

                    message_id = (
                        message.get(
                            "id"
                        )
                    )

                    wa_id = (
                        message.get(
                            "from"
                        )
                    )

                    if (
                        not message_id
                        or not wa_id
                    ):
                        continue

                    claimed = (
                        claim_message(
                            db=db,
                            message_id=
                                message_id,
                            company_id=
                                channel.company_id,
                            agent_id=
                                channel.agent_id,
                            wa_id=
                                wa_id,
                        )
                    )

                    if not claimed:

                        processed.append({
                            "message_id":
                                message_id,
                            "status":
                                "duplicate",
                        })

                        continue

                    if (
                        message.get(
                            "type"
                        )
                        != "text"
                    ):

                        processed.append({
                            "message_id":
                                message_id,
                            "status":
                                "ignored_non_text",
                        })

                        continue

                    body = (
                        message.get(
                            "text",
                            {},
                        )
                        or {}
                    )

                    incoming_text = str(
                        body.get(
                            "body",
                            "",
                        )
                    ).strip()

                    if not incoming_text:

                        processed.append({
                            "message_id":
                                message_id,
                            "status":
                                "ignored_empty",
                        })

                        continue

                    try:

                        # Serialize messages for
                        # this agent/contact.
                        lock_contact(
                            db,
                            channel.agent_id,
                            wa_id,
                        )

                        session = (
                            db.query(
                                WhatsAppSession
                            )
                            .filter(
                                WhatsAppSession
                                .agent_id
                                == channel.agent_id,

                                WhatsAppSession
                                .wa_id
                                == wa_id,
                            )
                            .first()
                        )

                        if session is None:

                            conversation = (
                                agent_runtime
                                .get_or_create_conversation(
                                    db=db,
                                    company_id=
                                        channel.company_id,
                                    agent_id=
                                        channel.agent_id,
                                    conversation_id=
                                        None,
                                    message=
                                        incoming_text,
                                )
                            )

                            session = (
                                WhatsAppSession(
                                    company_id=
                                        channel.company_id,
                                    agent_id=
                                        channel.agent_id,
                                    conversation_id=
                                        conversation.id,
                                    wa_id=
                                        wa_id,
                                    phone_number_id=
                                        phone_number_id,
                                )
                            )

                            db.add(
                                session
                            )

                            db.flush()

                        result = (
                            agent_runtime.chat(
                                db=db,
                                company_id=
                                    channel.company_id,
                                agent_id=
                                    channel.agent_id,
                                message=
                                    incoming_text,
                                conversation_id=
                                    session.conversation_id,
                            )
                        )

                    except Exception as exc:

                        db.rollback()

                        # Runtime did not finish:
                        # allow Meta to retry.
                        release_message_claim(
                            db,
                            message_id,
                        )

                        audit_service.log(
                            db=db,
                            company_id=
                                channel.company_id,
                            action=
                                "whatsapp.runtime_failed",
                            resource_type=
                                "channel",
                            resource_id=
                                channel.id,
                            details={
                                "message_id":
                                    message_id,
                                "error":
                                    str(exc),
                            },
                        )

                        db.commit()

                        raise

                    reply_text = str(
                        result[
                            "response"
                        ][
                            "content"
                        ]
                    )

                    send_result = (
                        whatsapp_sender
                        .send_text(
                            config=
                                config,
                            to=
                                wa_id,
                            text=
                                reply_text,
                        )
                    )

                    audit_service.log(
                        db=db,
                        company_id=
                            channel.company_id,
                        action=(
                            "whatsapp.reply_sent"
                            if send_result.get(
                                "success"
                            )
                            else
                            "whatsapp.reply_failed"
                        ),
                        resource_type=
                            "channel",
                        resource_id=
                            channel.id,
                        details={
                            "message_id":
                                message_id,

                            "conversation_id":
                                result[
                                    "conversation_id"
                                ],

                            "success":
                                bool(
                                    send_result.get(
                                        "success"
                                    )
                                ),

                            "status_code":
                                send_result.get(
                                    "status_code"
                                ),
                        },
                    )

                    db.commit()

                    processed.append({
                        "message_id":
                            message_id,

                        "agent_id":
                            channel.agent_id,

                        "conversation_id":
                            result[
                                "conversation_id"
                            ],

                        "reply_sent":
                            bool(
                                send_result.get(
                                    "success"
                                )
                            ),
                    })

        return {
            "status":
                "ok",
            "processed":
                processed,
        }

    finally:
        db.close()
