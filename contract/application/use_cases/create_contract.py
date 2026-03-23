class CreateContractUseCase:
    def execute(self, user, contract_model, payload):
        contract = contract_model(name=payload.get("name"), user=user)
        contract.save()

        return {
            "data": {
                "id": contract.id,
                "name": contract.name,
                "value": float(contract.value or 0),
                "value_open": float(contract.value_open or 0),
                "value_closed": float(contract.value_closed or 0),
            }
        }
