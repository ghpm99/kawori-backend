class NewCharacterUseCase:
    MAXIMUM_FACETEXTURE_CHARACTERS = 44

    def execute(self, user, data, character_model, bdo_class_model, class_image_fn):
        character_count = character_model.objects.filter(user=user, active=True).count()
        if character_count >= self.MAXIMUM_FACETEXTURE_CHARACTERS:
            return {
                "data": f"O limite de facetexture são {self.MAXIMUM_FACETEXTURE_CHARACTERS}!"
            }, 400

        name = data.get("name", "")
        visible_class = data.get("visible")
        class_id = data.get("classId")

        bdo_class = bdo_class_model.objects.filter(id=class_id).first()
        if bdo_class is None:
            return {"data": "Classe não encontrada"}, 400

        if character_count == 0:
            new_order = 0
        else:
            last_order = character_model.objects.filter(user=user, active=True).latest("order")
            new_order = last_order.order + 1

        image_url = class_image_fn(bdo_class.id)

        character = character_model(
            name=name,
            show=visible_class,
            image=image_url,
            order=new_order,
            upload=False,
            bdoClass=bdo_class,
            user=user,
        )
        character.save()

        character_data = {
            "id": character.id,
            "name": character.name,
            "show": character.show,
            "image": character.image,
            "order": character.order,
            "upload": character.upload,
            "class": {
                "id": character.bdoClass.id,
                "name": character.bdoClass.name,
                "abbreviation": character.bdoClass.abbreviation,
                "class_image": image_url,
            },
        }
        return {"character": character_data}, 200
