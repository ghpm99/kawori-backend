class ChangeClassCharacterUseCase:
    def execute(
        self, user, character_id, data, character_model, bdo_class_model, class_image_fn
    ):
        new_class = data.get("new_class")
        character = character_model.objects.filter(id=character_id, user=user).first()

        if character is None:
            return {"data": "Não foi encontrado personagem com esse ID"}, 404

        bdo_class = bdo_class_model.objects.filter(id=new_class).first()
        if bdo_class is None:
            return {"data": "Não foi encontrado classe"}, 400

        character.bdoClass = bdo_class
        character.save()

        return {
            "class": {
                "id": bdo_class.id,
                "name": bdo_class.name,
                "abbreviation": bdo_class.abbreviation,
                "class_image": class_image_fn(bdo_class.id),
            }
        }, 200
