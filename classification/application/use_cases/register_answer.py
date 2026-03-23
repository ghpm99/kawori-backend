class RegisterAnswerUseCase:
    def execute(self, payload, user, question_model, bdo_class_model, answer_model):
        question_id = payload.get("question_id")
        if not question_id:
            return {"msg": "ID da questão não informado!"}, 400

        question = question_model.objects.get(id=question_id)
        if not question:
            return {"msg": "Questão não encontrada!"}, 404

        combat_style = payload.get("combat_style")
        if not combat_style:
            return {"msg": "Estilo de combate não informado!"}, 400
        if isinstance(combat_style, int) is False:
            return {"msg": "Estilo de combate invalido"}, 400

        bdo_class_id = payload.get("bdo_class_id")
        if not bdo_class_id:
            return {"msg": "ID da classe não informado!"}, 400

        bdo_class = bdo_class_model.objects.get(id=bdo_class_id)
        if not bdo_class:
            return {"msg": "Classe não encontrada!"}, 404

        vote = payload.get("vote")
        if not vote:
            return {"msg": "Voto não informado!"}, 400
        if isinstance(vote, int) is False:
            return {"msg": "Voto deve ser um número inteiro!"}, 400

        answer_model.objects.create(
            question_id=question_id,
            bdo_class_id=bdo_class_id,
            combat_style=combat_style,
            user=user,
            vote=vote,
        )

        return {"msg": "Voto registrado com sucesso!"}, 200
