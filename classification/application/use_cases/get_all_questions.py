class GetAllQuestionsUseCase:
    def execute(self, question_model):
        question_list = question_model.objects.order_by("id")

        data = [
            {
                "id": question.id,
                "question_text": question.question_text,
                "question_details": question.question_details,
                "pub_date": question.pub_date,
            }
            for question in question_list
        ]
        return {"data": data}, 200
