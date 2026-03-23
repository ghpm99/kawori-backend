from django.db import transaction


class MergeContractsUseCase:
    def execute(
        self,
        user,
        contract_model,
        invoice_model,
        contract_id,
        payload,
        update_contract_value_fn,
    ):
        contract = contract_model.objects.filter(id=contract_id, user=user).first()
        if contract is None:
            return {"msg": "Contract not found"}, 404

        contracts = payload.get("contracts") or []
        with transaction.atomic():
            for contract_to_merge_id in contracts:
                if contract_to_merge_id == contract.id:
                    continue
                invoices = invoice_model.objects.filter(
                    contract=contract_to_merge_id, user=user, active=True
                ).all()
                for invoice in invoices:
                    invoice.contract = contract
                    invoice.save()
                contract_model.objects.filter(
                    id=contract_to_merge_id, user=user
                ).delete()

            update_contract_value_fn(contract)

        return {"msg": "Contratos mesclados com sucesso!"}, 200
