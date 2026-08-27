from datetime import datetime

from backend.app.core.agent_runtime import agent_runtime
from backend.app.core.config_secrets import reveal_config
from backend.app.core.http_security import safe_http_request
from backend.app.modules.automation.models import AutomationRun, AutomationWorkflow
from backend.app.modules.billing.service_limits import service_limits
from backend.app.modules.integrations.models import CompanyIntegration
from backend.app.modules.tools.executor import tool_executor


class AutomationRuntime:
    def execute(
        self,
        db,
        company_id: int,
        workflow: AutomationWorkflow,
        input_data: dict | None = None,
    ):
        if workflow.company_id != company_id:
            raise ValueError("Workflow does not belong to company")
        if not workflow.enabled:
            raise ValueError("Workflow is disabled")

        original_input = dict(input_data or {})
        service_limits.record(
            db,
            company_id,
            "automation",
            "runs",
            quantity=1,
            metadata={"workflow_id": workflow.id},
        )

        run = AutomationRun(
            company_id=company_id,
            workflow_id=workflow.id,
            status="running",
            input_data=original_input,
            output_data={},
        )
        db.add(run)
        db.flush()
        run_id = run.id

        state = dict(original_input)
        step_results = []

        try:
            for index, step in enumerate(workflow.steps or []):
                result = self.execute_step(
                    db,
                    company_id,
                    step,
                    state,
                    run_id=run_id,
                    step_index=index,
                )
                step_results.append(
                    {
                        "index": index,
                        "type": step.get("type"),
                        "label": step.get("label"),
                        "result": result,
                    }
                )
                if isinstance(result, dict):
                    state.update(result)

            run.status = "success"
            run.output_data = {"state": state, "steps": step_results}
            run.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
            return run
        except Exception as original_error:
            error_message = str(original_error)[:2000]
            failed_output = {"state": state, "steps": step_results}
            db.rollback()

            usage_recorded = True
            try:
                service_limits.record(
                    db,
                    company_id,
                    "automation",
                    "runs",
                    quantity=1,
                    metadata={"workflow_id": workflow.id, "status": "failed"},
                )
            except Exception:
                # A concurrent run may have consumed the final quota slot after
                # the original transaction rolled back. Preserve the workflow
                # failure instead of masking it with an accounting race.
                usage_recorded = False
                db.rollback()

            failed_run = AutomationRun(
                company_id=company_id,
                workflow_id=workflow.id,
                status="failed",
                input_data=original_input,
                output_data={
                    **failed_output,
                    "usage_recorded": usage_recorded,
                },
                error_message=error_message,
                finished_at=datetime.utcnow(),
            )
            db.add(failed_run)
            db.commit()
            raise

    def execute_step(
        self,
        db,
        company_id: int,
        step: dict,
        state: dict,
        *,
        run_id: int,
        step_index: int,
    ):
        step_type = str(step.get("type", "")).strip().lower()

        if step_type == "transform":
            values = step.get("values") or {}
            if not isinstance(values, dict):
                raise ValueError("Transform values must be an object")
            return dict(values)

        if step_type == "condition":
            field = str(step.get("field") or "").strip()
            if not field:
                raise ValueError("Condition step requires field")
            expected = step.get("equals")
            actual = state.get(field)
            if actual != expected:
                raise ValueError(
                    f"Condition failed: {field} expected {expected!r}, got {actual!r}"
                )
            return {"condition_passed": True}

        if step_type == "ai":
            agent_id = step.get("agent_id")
            prompt = str(step.get("prompt") or step.get("label") or "").strip()
            if not agent_id:
                raise ValueError("AI step requires agent_id")
            if not prompt:
                raise ValueError("AI step requires prompt")
            response = agent_runtime.chat(
                db=db,
                company_id=company_id,
                agent_id=int(agent_id),
                message=prompt,
                commit=False,
                allow_tools=False,
            )
            return {
                "ai_response": response.get("response", {}).get("content", ""),
                "conversation_id": response.get("conversation_id"),
            }

        if step_type == "tool":
            agent_id = step.get("agent_id")
            tool_name = step.get("tool_name")
            if not agent_id or not tool_name:
                raise ValueError("Tool step requires agent_id and tool_name")
            result = tool_executor.execute(
                db=db,
                company_id=company_id,
                agent_id=int(agent_id),
                tool_name=str(tool_name),
                arguments=step.get("arguments") or {},
                approval_granted=bool(step.get("approval_granted", False)),
            )
            if not result.get("success"):
                raise ValueError(result.get("error") or "Tool execution failed")
            return {"tool_result": result.get("data")}

        if step_type == "webhook":
            integration_id = step.get("integration_id")
            if not integration_id:
                raise ValueError("Webhook step requires integration_id")
            integration = (
                db.query(CompanyIntegration)
                .filter(
                    CompanyIntegration.id == int(integration_id),
                    CompanyIntegration.company_id == company_id,
                    CompanyIntegration.integration_type == "webhook",
                    CompanyIntegration.enabled.is_(True),
                )
                .first()
            )
            if integration is None:
                raise ValueError("Enabled webhook integration not found")
            config = reveal_config(integration.config) or {}
            url = str(config.get("url") or "").strip()
            if not url:
                raise ValueError("Webhook URL is invalid")
            idempotency_key = f"xvond-automation-{company_id}-{run_id}-{step_index}-v1"
            headers = {
                "Idempotency-Key": idempotency_key,
                "X-Xvond-Idempotency-Key": idempotency_key,
            }
            if config.get("secret"):
                headers["X-Xvond-Webhook-Secret"] = str(config["secret"])
            result = safe_http_request(
                url=url,
                method="POST",
                json_data=state,
                headers=headers,
                timeout=15.0,
                max_response_bytes=250_000,
            )
            status = int(result.get("status_code") or 0)
            if not 200 <= status < 300:
                raise ValueError(f"Webhook returned HTTP {status}")
            return {
                "webhook_status": status,
                "webhook_idempotency_key": idempotency_key,
            }

        if step_type == "integration":
            raise ValueError(
                "Direct integration steps are configured through an agent tool "
                "or webhook integration"
            )

        raise ValueError(f"Unsupported automation step: {step_type}")


automation_runtime = AutomationRuntime()
