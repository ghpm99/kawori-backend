class GetAllContractsUseCase:
    def execute(self, user, contract_model, paginate_fn, contract_id, page, page_size):
        filters = {}
        if contract_id:
            filters["id"] = contract_id

        contracts_query = contract_model.objects.filter(**filters, user=user).order_by(
            "id"
        )
        data = paginate_fn(contracts_query, page, page_size)

        contracts = [
            {
                "id": contract.id,
                "name": contract.name,
                "value": float(contract.value or 0),
                "value_open": float(contract.value_open or 0),
                "value_closed": float(contract.value_closed or 0),
            }
            for contract in data.get("data")
        ]

        data["data"] = contracts
        return {"data": data}
