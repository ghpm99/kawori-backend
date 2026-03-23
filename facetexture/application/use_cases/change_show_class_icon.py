class ChangeShowClassIconUseCase:
    def execute(self, user, character_id, data, character_model):
        new_value = data.get("show")
        character = character_model.objects.filter(id=character_id, user=user).first()

        if character is None:
            return {"data": "Não foi encontrado personagem com esse ID"}, 404

        character.show = new_value
        character.save()
        return {"data": "Visibilidade atualizado com sucesso"}, 200
