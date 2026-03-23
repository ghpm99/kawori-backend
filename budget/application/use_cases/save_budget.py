from django.db import transaction


class SaveBudgetUseCase:
    def execute(self, user, budget_model, payload):
        with transaction.atomic():
            for item in payload.get("data", []):
                budget = budget_model.objects.filter(
                    id=item.get("id"), user=user
                ).first()
                if budget:
                    budget.allocation_percentage = item.get(
                        "allocation_percentage", budget.allocation_percentage
                    )
                    budget.save()

        return {"msg": "Orçamento atualizado com sucesso"}, 200
