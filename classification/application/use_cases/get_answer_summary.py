class GetAnswerSummaryUseCase:
    def execute(self, answer_summary_model, process_resume_fn):
        answers = answer_summary_model.objects.all()

        data = []
        for answer in answers:
            data.append(
                {
                    "id": answer.id,
                    "bdo_class": answer.bdo_class.id,
                    "updated_at": answer.updated_at,
                    "resume": process_resume_fn(answer.resume),
                }
            )

        return {"data": data}, 200
