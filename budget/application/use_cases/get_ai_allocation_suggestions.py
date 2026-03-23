class GetAIAllocationSuggestionsUseCase:
    def execute(self, user, period, build_budget_allocation_suggestions_fn):
        return build_budget_allocation_suggestions_fn(user=user, period=period)
