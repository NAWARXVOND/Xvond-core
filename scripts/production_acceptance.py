import argparse
import json
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from backend.app.core.ai.engine import ai_engine
from backend.app.core.ai.provider_policy import runtime_selections
from backend.app.core.config.settings import settings
from backend.app.core.database.connection import SessionLocal
from backend.app.core.readiness import company_readiness
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.channels.whatsapp_queue import whatsapp_job_queue
from backend.app.modules.providers.models import AIModelRecord, AIProviderRecord


def check_release(company_id: int, agent_id: int | None = None, live_ai: bool = False) -> dict:
    checks = {}
    db = SessionLocal()
    agent = None
    route = []
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}

        configured_revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
        checks["migrations"] = {
            "ok": len(heads) == 1 and configured_revision == heads[0],
            "database_revision": configured_revision,
            "expected_head": heads[0] if len(heads) == 1 else heads,
        }

        try:
            redis_ok = whatsapp_job_queue.client is not None and bool(whatsapp_job_queue.client.ping())
        except Exception:
            redis_ok = False
        checks["redis"] = {"ok": redis_ok}

        loaded = set(ai_engine.list_providers()) - {"mock"}
        rows = (
            db.query(AIModelRecord, AIProviderRecord)
            .join(AIProviderRecord, AIProviderRecord.name == AIModelRecord.provider_name)
            .filter(
                AIModelRecord.enabled.is_(True),
                AIProviderRecord.enabled.is_(True),
            )
            .all()
        )
        eligible = [
            {"provider": model.provider_name, "model": model.model_name}
            for model, provider in rows
            if provider.name in loaded
        ]
        checks["ai_providers"] = {
            "ok": bool(eligible),
            "runtime_loaded": sorted(loaded),
            "eligible_models": eligible,
        }

        readiness = company_readiness(db, company_id)
        checks["company"] = {
            "ok": bool(
                readiness
                and readiness.get("setup_ready")
                and readiness.get("company", {}).get("active")
            ),
            "readiness": readiness,
        }

        if agent_id is not None:
            agent = db.query(AIAgent).filter(
                AIAgent.id == agent_id,
                AIAgent.company_id == company_id,
            ).first()
            if agent is None:
                checks["routing"] = {"ok": False, "error": "AI employee not found"}
            else:
                try:
                    route = runtime_selections(db, company_id, agent.provider, agent.model)
                    checks["routing"] = {
                        "ok": bool(route),
                        "route": [
                            {"provider": x.provider, "model": x.model, "reason": x.reason}
                            for x in route
                        ],
                    }
                except Exception as exc:
                    route = []
                    checks["routing"] = {"ok": False, "error": str(exc)[:500]}

        if live_ai:
            if agent_id is None:
                checks["live_ai"] = {"ok": False, "error": "--agent-id is required with --live-ai"}
            elif agent is None:
                checks["live_ai"] = {"ok": False, "error": "AI employee not found"}
            elif not route:
                checks["live_ai"] = {"ok": False, "error": "No eligible real AI route is available"}
            else:
                try:
                    selection = route[0]
                    result = ai_engine.generate(
                        provider_name=selection.provider,
                        system_prompt=(
                            "You are a production health-check endpoint. "
                            "Reply with exactly XVOND_OK and nothing else."
                        ),
                        user_message="Return XVOND_OK.",
                        model=selection.model,
                        tools=None,
                    )
                    response = (result.text or "").strip()
                    checks["live_ai"] = {
                        "ok": response == "XVOND_OK",
                        "provider": selection.provider,
                        "model": selection.model,
                        "response": response[:200],
                        "customer_runtime_used": False,
                    }
                except Exception as exc:
                    db.rollback()
                    checks["live_ai"] = {"ok": False, "error": str(exc)[:500]}
    except Exception as exc:
        db.rollback()
        checks["database"] = {"ok": False, "error": str(exc)[:500]}
    finally:
        db.close()

    checks["environment"] = {"ok": settings.is_production, "value": settings.APP_ENV}
    checks["overall_ok"] = all(
        item.get("ok", False)
        for key, item in checks.items()
        if key != "overall_ok"
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Xvond before activating a real customer.")
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument("--agent-id", type=int)
    parser.add_argument(
        "--live-ai",
        action="store_true",
        help="Send one real billable provider health-check request without creating a customer conversation.",
    )
    args = parser.parse_args()
    report = check_release(
        company_id=args.company_id,
        agent_id=args.agent_id,
        live_ai=args.live_ai,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())