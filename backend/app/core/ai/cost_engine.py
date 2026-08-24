from decimal import Decimal

from backend.app.modules.providers.models import AIModelRecord


class AICostEngine:

    def calculate(
        self,
        db,
        provider_name: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Decimal:

        model = (
            db.query(AIModelRecord)
            .filter(
                AIModelRecord.provider_name
                == provider_name,
                AIModelRecord.model_name
                == model_name,
                AIModelRecord.enabled.is_(True),
            )
            .first()
        )

        if model is None:
            return Decimal("0")

        input_cost = (
            Decimal(input_tokens)
            / Decimal("1000000")
            * model.input_price_per_million
        )

        output_cost = (
            Decimal(output_tokens)
            / Decimal("1000000")
            * model.output_price_per_million
        )

        return input_cost + output_cost


ai_cost_engine = AICostEngine()
