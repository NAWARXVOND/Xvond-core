import argparse
import json
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.ai.engine import ai_engine
from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.core.readiness import company_readiness
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue
from backend.app.modules.providers.models import (
    AIModelRecord,
    AIProviderRecord,
)


def check_release(
    company_id: int,
    agent_id: int | None = None,
    live_ai: bool = False,
) -> dict:
    checks = {}
    db = SessionLocal()

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {
            "ok": True,
        }

        configured_revision = (
            db.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar()
        )
        heads = ScriptDirectory.from_config(
            Config("alembic.ini")
        ).get_heads()
        migrations_ok = (
            len(heads) == 1
            and configured_revision == heads[0]
        )
        checks["migrations"] = {
            "ok": migrations_ok,
            "database_revision": configured_revision,
            "expected_head": heads[0] if len(heads) == 1 else heads,
        }

        try:
            redis_ok = (
                whatsapp_job_queue.client is not None
                and bool(whatsapp_job_queue.client.ping())
            )
        except Exception:
            redis_ok = False

        checks["redis"] = {
            "ok": redis_ok,
        }

        groq_provider = (
            db.query(AIProviderRecord)
            .filter(
                AIProviderRecord.name == "groq",
                AIProviderRecord.enabled.is_(True),
            )
            .first()
        )
        groq_models = (
            db.query(AIModelRecord)
            .filter(
                AIModelRecord.provider_name == "groq",
                AIModelRecord.enabled.is_(True),
            )
            .order_by(AIModelRecord.model_name.asc())
            .all()
        )
        groq_ok = (
            "groq" in ai_engine.list_providers()
            and groq_provider is not None
            and bool(groq_models)
        )
        checks["groq"] = {
            "ok": groq_ok,
            "runtime_loaded": "groq" in ai_engine.list_providers(),
            "enabled_models": [
                item.model_name
                for item in groq_models
            ],
        }

        readiness = company_readiness(
            db,
            company_id,
        )
        checks["company"] = {
            "ok": bool(
                readiness
                and readiness.get("setup_ready")
                and readiness.get("company", {}).get("active")
            ),
            "readiness": readiness,
        }

        if live_ai:
            if agent_id is None:
                checks["live_ai"] = {
                    "ok": False,
                    "error": "--agent-id is required with --live-ai",
                }
            else:
                try:
                    result = agent_runtime.chat(
                        db=db,
                        company_id=company_id,
                        agent_id=agent_id,
                        message=(
                            "Production acceptance check. "
                            "Reply with exactly XVOND_OK."
                        ),
                    )
                    response = (
                        result.get("response", {})
                        .get("content", "")
                        .strip()
                    )
                    checks["live_ai"] = {
                        "ok": "XVOND_OK" in response,
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "response": response[:200],
                    }
                except Exception as exc:
                    db.rollback()
                    checks["live_ai"] = {
                        "ok": False,
                        "error": str(exc)[:500],
                    }

    except Exception as exc:
        db.rollback()
        checks["database"] = {
            "ok": False,
            "error": str(exc)[:500],
        }
    finally:
        db.close()

    checks["environment"] = {
        "ok": settings.is_production,
        "value": settings.APP_ENV,
    }
    checks["overall_ok"] = all(
        item.get("ok", False)
        for key, item in checks.items()
        if key != "overall_ok"
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Xvond before activating a real customer.",
    )
    parser.add_argument(
        "--company-id",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--agent-id",
        type=int,
    )
    parser.add_argument(
        "--live-ai",
        action="store_true",
        help="Send one real billable AI request.",
    )
    args = parser.parse_args()

    report = check_release(
        company_id=args.company_id,
        agent_id=args.agent_id,
        live_ai=args.live_ai,
    )
    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
