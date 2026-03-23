from django.db import transaction


class ResetBudgetAllocationUseCase:
    def execute(self, user, budget_model, default_budgets):
        with transaction.atomic():
            budget_list = budget_model.objects.filter(user=user)
            for budget in budget_list:
                for default_budget in default_budgets:
                    if budget.tag.name.lower() == default_budget["name"].lower():
                        budget.allocation_percentage = default_budget[
                            "allocation_percentage"
                        ]
                        budget.save()
                        break

        return {"msg": "Orçamentos resetados com sucesso"}, 200
