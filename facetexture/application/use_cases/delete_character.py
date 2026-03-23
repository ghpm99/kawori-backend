class DeleteCharacterUseCase:
    def execute(self, user, character_id, character_model):
        character = character_model.objects.filter(id=character_id, user=user).first()

        if character is None:
            return {"data": "Não foi encontrado personagem com esse ID"}, 404

        character.active = False
        character.save()
        return {"data": "Personagem deletado com sucesso"}, 200
