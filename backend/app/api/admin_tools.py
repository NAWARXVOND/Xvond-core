
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from backend.app.core.config_secrets import (
    configured_secret_fields,
    merge_config,
    public_config,
)
from backend.app.core.database.connection import (
    SessionLocal,
)
from backend.app.core.dependencies import (
    require_xvond_admin,
)

from backend.app.models.user import User
from backend.app.modules.ai_agent.models import (
    AIAgent,
)
from backend.app.modules.tools.models import (
    AgentToolAssignment,
)
from backend.app.modules.tools.registry import (
    tool_registry,
)


router = APIRouter(
    prefix="/admin/tools",
    tags=["Xvond Admin - Tools"],
)


class ToolAssignRequest(BaseModel):
    config: dict = Field(
        default_factory=dict
    )


class ToolUpdateRequest(BaseModel):
    enabled: bool | None = None
    config: dict | None = None


def serialize_assignment(
    item: AgentToolAssignment,
) -> dict:

    config = (
        item.config
        or {}
    )

    return {
        "tool_name":
            item.tool_name,

        "config":
            public_config(
                config
            ),

        "configured_secret_fields":
            configured_secret_fields(
                config
            ),

        "enabled":
            item.enabled,
    }


def get_agent_or_404(
    db,
    agent_id: int,
):

    agent = (
        db.query(AIAgent)
        .filter(
            AIAgent.id
            == agent_id
        )
        .first()
    )

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail="AI Agent not found",
        )

    return agent


@router.get("/")
def list_tools(
    current_admin: User = Depends(
        require_xvond_admin
    ),
):

    return {
        "tools": [
            {
                "name":
                    tool.name,

                "description":
                    tool.description,

                "input_schema":
                    tool.input_schema,
            }
            for tool
            in tool_registry.list()
        ]
    }


@router.post(
    "/agents/{agent_id}/{tool_name}"
)
def assign_tool(
    agent_id: int,
    tool_name: str,
    data: ToolAssignRequest,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):

    if not tool_registry.exists(
        tool_name
    ):
        raise HTTPException(
            status_code=404,
            detail="Tool not found",
        )

    db = SessionLocal()

    try:

        get_agent_or_404(
            db,
            agent_id,
        )

        existing = (
            db.query(
                AgentToolAssignment
            )
            .filter(
                AgentToolAssignment.agent_id
                == agent_id,
                AgentToolAssignment.tool_name
                == tool_name,
            )
            .first()
        )

        if existing is not None:

            existing.config = (
                merge_config(
                    existing.config,
                    data.config,
                )
            )

            existing.enabled = True

            db.commit()
            db.refresh(existing)

            result = (
                serialize_assignment(
                    existing
                )
            )

            result["status"] = (
                "updated"
            )

            return result

        assignment = (
            AgentToolAssignment(
                agent_id=
                    agent_id,
                tool_name=
                    tool_name,
                config=
                    data.config or {},
                enabled=True,
            )
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        result = (
            serialize_assignment(
                assignment
            )
        )

        result.update({
            "agent_id":
                agent_id,
            "status":
                "assigned",
        })

        return result

    finally:
        db.close()


@router.get(
    "/agents/{agent_id}/assignments"
)
def list_agent_tool_assignments(
    agent_id: int,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):

    db = SessionLocal()

    try:

        get_agent_or_404(
            db,
            agent_id,
        )

        items = (
            db.query(
                AgentToolAssignment
            )
            .filter(
                AgentToolAssignment.agent_id
                == agent_id
            )
            .order_by(
                AgentToolAssignment.id.asc()
            )
            .all()
        )

        return {
            "agent_id":
                agent_id,

            "tools": [
                serialize_assignment(
                    item
                )
                for item in items
            ],
        }

    finally:
        db.close()


@router.patch(
    "/agents/{agent_id}/{tool_name}"
)
def update_tool_assignment(
    agent_id: int,
    tool_name: str,
    data: ToolUpdateRequest,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):

    db = SessionLocal()

    try:

        get_agent_or_404(
            db,
            agent_id,
        )

        assignment = (
            db.query(
                AgentToolAssignment
            )
            .filter(
                AgentToolAssignment.agent_id
                == agent_id,
                AgentToolAssignment.tool_name
                == tool_name,
            )
            .first()
        )

        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Tool assignment not found"
                ),
            )

        if data.enabled is not None:
            assignment.enabled = (
                data.enabled
            )

        if data.config is not None:

            # Secret values that are omitted
            # from the UI remain stored.
            assignment.config = (
                merge_config(
                    assignment.config,
                    data.config,
                )
            )

        db.commit()
        db.refresh(assignment)

        result = (
            serialize_assignment(
                assignment
            )
        )

        result.update({
            "agent_id":
                agent_id,
            "status":
                "updated",
        })

        return result

    finally:
        db.close()


@router.delete(
    "/agents/{agent_id}/{tool_name}"
)
def delete_tool_assignment(
    agent_id: int,
    tool_name: str,
    current_admin: User = Depends(
        require_xvond_admin
    ),
):

    db = SessionLocal()

    try:

        get_agent_or_404(
            db,
            agent_id,
        )

        assignment = (
            db.query(
                AgentToolAssignment
            )
            .filter(
                AgentToolAssignment.agent_id
                == agent_id,
                AgentToolAssignment.tool_name
                == tool_name,
            )
            .first()
        )

        if assignment is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Tool assignment not found"
                ),
            )

        db.delete(
            assignment
        )

        db.commit()

        return {
            "agent_id":
                agent_id,
            "tool_name":
                tool_name,
            "status":
                "unassigned",
        }

    finally:
        db.close()
