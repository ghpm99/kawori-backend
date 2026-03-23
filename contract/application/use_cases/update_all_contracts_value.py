from django.db import transaction


class UpdateAllContractsValueUseCase:
    def execute(self, user, contract_model, update_contract_value_fn):
        with transaction.atomic():
            contracts = contract_model.objects.filter(user=user)
            for contract in contracts:
                update_contract_value_fn(contract)

        return {"msg": "ok"}, 200
