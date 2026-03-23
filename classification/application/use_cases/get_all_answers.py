class GetAllAnswersUseCase:
    def execute(self, user, answer_model):
        answer_list = answer_model.objects.filter(user=user).order_by("-id")

        data = [
            {
                "id": answer.id,
                "question": answer.question.question_text,
                "vote": answer.vote,
                "bdo_class": answer.bdo_class.abbreviation,
                "combat_style": answer.combat_style,
                "created_at": answer.created_at,
            }
            for answer in answer_list
        ]

        return {"data": data}, 200
