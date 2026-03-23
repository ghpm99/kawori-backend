class SaveTagUseCase:
    def execute(self, user, tag_model, tag_id, payload):
        tag = tag_model.objects.filter(id=tag_id, user=user).first()
        if tag is None:
            return None, {"msg": "Tag não encontrada"}, 404

        tag.name = payload.get("name")
        tag.color = payload.get("color")
        tag.save()

        return tag, {"msg": "Tag atualizado com sucesso"}, 200
