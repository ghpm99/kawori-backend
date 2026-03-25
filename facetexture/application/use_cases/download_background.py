class DownloadBackgroundUseCase:
    def execute(
        self,
        user,
        request_files,
        request_post,
        character_model,
        image_module,
        get_symbol_class_fn,
        verify_valid_symbol_fn,
        io_module,
        zipfile_class,
    ):
        if not request_files.get("background"):
            return {"msg": "Nao existe nenhum background"}, 400, None

        characters = (
            character_model.objects.filter(user=user, active=True)
            .order_by("order")
            .all()
        )
        if not characters:
            return {"msg": "Facetexture nao encontrado"}, 404, None

        file = request_files.get("background").file
        image = image_module.open(file)
        icon_style = request_post.get("icon_style", "P")
        if not verify_valid_symbol_fn(icon_style):
            return {"msg": "Estilo de simbolo invalido"}, 400, None

        image = image.resize(size=(920, 1157))

        width = 125
        height = 160
        count_x = 0
        count_y = 0
        backgrounds = []

        for index, character in enumerate(characters):
            x = count_x * (width + 5) + 11
            y = count_y * (height + 5) + 11

            if (index % 7) == 6:
                count_x = 0
                count_y = count_y + 1
            else:
                count_x = count_x + 1

            image_crop = image.crop((x, y, x + width, y + height)).convert("RGBA")

            if character.show is True:
                class_image = get_symbol_class_fn(
                    character.bdoClass, symbol_style=icon_style
                ).convert("RGBA")
                image_crop.paste(class_image, (10, 10), class_image)

            backgrounds.append({"name": character.name, "image": image_crop})

        with zipfile_class("export.zip", "w") as export_zip:
            for background in backgrounds:
                file_object = io_module.BytesIO()
                background["image"].save(file_object, "PNG")
                file_object.seek(0)
                export_zip.writestr(background["name"], file_object.getvalue())

        return None, 200, "export.zip"
