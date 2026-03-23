class ChangeCharacterNameUseCase:
    def execute(self, user, character_id, data, character_model):
        new_name = data.get("name")
        character = character_model.objects.filter(id=character_id, user=user).first()

        if character is None:
            return {"data": "Não foi encontrado personagem com esse ID"}, 404

        character.name = new_name
        character.save()
        return {"data": "Nome atualizado com sucesso"}, 200
