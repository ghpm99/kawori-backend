class GetFacetextureConfigUseCase:
    def execute(self, user, character_model, class_image_url_fn):
        characters = (
            character_model.objects.filter(user=user, active=True).all().order_by("order")
        )

        data = []
        for character in characters:
            character_data = {
                "id": character.id,  # type: ignore
                "name": character.name,
                "show": character.show,
                "image": character.image,
                "order": character.order,
                "upload": character.upload,
                "class": {
                    "id": character.bdoClass.id,  # type: ignore
                    "name": character.bdoClass.name,
                    "abbreviation": character.bdoClass.abbreviation,
                    "class_image": class_image_url_fn(character.bdoClass.id),  # type: ignore
                },
            }
            data.append(character_data)

        return {"characters": data}
