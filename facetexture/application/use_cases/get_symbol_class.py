class GetSymbolClassUseCase:
    def execute(self, class_id, bdo_class_model, get_symbol_class_fn, io_module):
        data = bdo_class_model.objects.filter(id=class_id).first()

        if data is None:
            return {"data": "Não foi encontrado classe com esse ID"}, 404, None

        class_image = get_symbol_class_fn(data)
        buffer = io_module.BytesIO()
        class_image.save(buffer, format="PNG")
        buffer.seek(0)
        return None, 200, buffer
