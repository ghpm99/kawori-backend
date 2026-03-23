class AnswerByClassUseCase:
    def execute(self, bdo_class_model, answer_model):
        bdo_classes = bdo_class_model.objects.order_by("abbreviation")

        data = []
        for bdo_class in bdo_classes:
            answers_count = answer_model.objects.filter(bdo_class=bdo_class).count()
            data.append(
                {
                    "class": bdo_class.abbreviation,
                    "answers_count": answers_count,
                    "color": bdo_class.color if bdo_class.color else "",
                }
            )

        return {"data": data}, 200
