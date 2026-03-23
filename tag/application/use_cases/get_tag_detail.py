class GetTagDetailUseCase:
    def execute(self, user, tag_model, tag_id):
        tag = tag_model.objects.filter(id=tag_id, user=user).first()
        if tag is None:
            return None

        return {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color,
        }
