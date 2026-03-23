class GetImageClassUseCase:
    def execute(self, class_id, bdo_class_model, get_image_class_fn, io_module):
        bdo_class_order = bdo_class_model.objects.filter(id=class_id).values("class_order")

        if bdo_class_order is None:
            return {"data": "Não foi encontrado classe com esse ID"}, 404, None

        class_order = bdo_class_order[0].get("class_order", 1)
        class_image = get_image_class_fn(class_order)
        buffer = io_module.BytesIO()
        class_image.save(buffer, format="PNG")
        buffer.seek(0)
        return None, 200, buffer
