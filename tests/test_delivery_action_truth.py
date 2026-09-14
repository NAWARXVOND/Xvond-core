from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app  # noqa: F401 - registers all model metadata
from backend.app.api.admin_delivery_readiness import _action_state
from backend.app.core.database.base import Base
from backend.app.models.company import Company
from backend.app.models.company_module import CompanyModule
from backend.app.modules.ai_agent.models import AIAgent
from backend.app.modules.tools.models import AgentToolAssignment


def _database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Company(id=1, name="Action Truth", active=False))
    db.add(
        AIAgent(
            id=1,
            company_id=1,
            name="Employee",
            system_prompt="Serve the customer",
            provider="mock",
            model="mock",
            enabled=False,
        )
    )
    db.commit()
    return engine, db


def test_human_handoff_only_is_conversational_not_broken_business_action():
    engine, db = _database()
    try:
        db.add(
            AgentToolAssignment(
                agent_id=1,
                tool_name="human_handoff",
                config={"approval_required": False},
                enabled=True,
            )
        )
        db.commit()

        state = _action_state(db, 1, 1)

        assert state["requested"] is False
        assert state["ready"] is True
        assert state["enabled_count"] == 0
        assert state["issues"] == []
        assert state["requires_workflow_engine"] is False
    finally:
        db.close()
        engine.dispose()


def test_enabled_action_request_without_enabled_operation_blocks_go_live():
    engine, db = _database()
    try:
        db.add(
            AgentToolAssignment(
                agent_id=1,
                tool_name="action_request",
                config={"actions": {}},
                enabled=True,
            )
        )
        db.commit()

        state = _action_state(db, 1, 1)

        assert state["requested"] is True
        assert state["ready"] is False
        assert state["enabled_count"] == 0
        assert any("no customer operation" in issue for issue in state["issues"])
        assert state["requires_workflow_engine"] is False
    finally:
        db.close()
        engine.dispose()


def test_legacy_business_tool_blocks_go_live_until_migrated_to_actions():
    engine, db = _database()
    try:
        db.add(
            AgentToolAssignment(
                agent_id=1,
                tool_name="booking",
                config={},
                enabled=True,
            )
        )
        db.commit()

        state = _action_state(db, 1, 1)

        assert state["requested"] is True
        assert state["ready"] is False
        assert state["legacy_business_tools"] == ["booking"]
        assert any("Legacy business tools" in issue for issue in state["issues"])
    finally:
        db.close()
        engine.dispose()


def test_canonical_runtime_ready_action_requires_workflow_engine():
    engine, db = _database()
    try:
        db.add(CompanyModule(company_id=1, module_name="booking", enabled=True))
        db.add(
            AgentToolAssignment(
                agent_id=1,
                tool_name="action_request",
                config={
                    "actions": {
                        "book_appointment": {
                            "label": "Book Appointment",
                            "module": "booking",
                            "enabled": True,
                            "fields": [
                                {"key": "customer_name", "required": True},
                                {"key": "date", "required": True},
                            ],
                            "confirmation_required": True,
                            "availability": {"mode": "none"},
                            "destination": {"type": "xvond_internal"},
                        }
                    }
                },
                enabled=True,
            )
        )
        db.commit()

        state = _action_state(db, 1, 1)

        assert state["requested"] is True
        assert state["ready"] is True
        assert state["enabled_count"] == 1
        assert state["issues"] == []
        assert state["requires_workflow_engine"] is True
    finally:
        db.close()
        engine.dispose()
