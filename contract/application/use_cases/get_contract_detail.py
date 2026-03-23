class GetContractDetailUseCase:
    def execute(self, user, contract_model, contract_id):
        contract = contract_model.objects.filter(id=contract_id, user=user).first()
        if contract is None:
            return None

        return {
            "id": contract.id,
            "name": contract.name,
            "value": float(contract.value or 0),
            "value_open": float(contract.value_open or 0),
            "value_closed": float(contract.value_closed or 0),
        }
