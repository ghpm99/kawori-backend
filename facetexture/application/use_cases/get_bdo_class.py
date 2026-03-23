class GetBDOClassUseCase:
    def execute(self, validated_data, bdo_class_model, class_image_url_fn):
        filters = {}
        class_id = validated_data.get("id")

        if class_id:
            filters["id"] = class_id

        bdo_classes = bdo_class_model.objects.filter(**filters).all()

        payload = [
            {
                "id": bdo_class.id,  # type: ignore
                "name": bdo_class.name,
                "abbreviation": bdo_class.abbreviation,
                "class_image": class_image_url_fn(bdo_class.id),  # type: ignore
            }
            for bdo_class in bdo_classes
        ]
        payload.sort(key=lambda item: item["name"])
        return {"class": payload}
