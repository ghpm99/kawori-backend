class GetBDOClassUseCase:
    def execute(
        self,
        bdo_class_model,
        get_bdo_class_image_url_fn,
        get_bdo_class_symbol_url_fn,
    ):
        bdo_classes = bdo_class_model.objects.order_by("abbreviation")

        bdo_class = [
            {
                "id": item.id,
                "name": item.name,
                "abbreviation": item.abbreviation,
                "class_image": get_bdo_class_image_url_fn(item.id),
                "class_symbol": get_bdo_class_symbol_url_fn(item.id),
                "color": item.color if item.color else "",
            }
            for item in bdo_classes
        ]

        return {"class": bdo_class}, 200
