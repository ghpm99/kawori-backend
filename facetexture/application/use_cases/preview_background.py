class PreviewBackgroundUseCase:
    def execute(
        self,
        user,
        request_files,
        request_post,
        character_model,
        image_module,
        image_ops_module,
        get_symbol_class_fn,
        verify_valid_symbol_fn,
        math_module,
    ):
        if not request_files.get("background"):
            return {"msg": "Nao existe nenhum background"}, 400, None

        characters = character_model.objects.filter(user=user, active=True).order_by("order").all()
        if not characters:
            return {"msg": "Facetexture nao encontrado"}, 400, None

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
        height_background = math_module.ceil(characters.__len__() / 7)
        background = image_module.new(mode="RGB", size=(930, height_background * 170))

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

            if character.name.__len__() < 20:
                image_crop = image_ops_module.expand(
                    image_crop, border=(3, 3, 3, 3), fill="red"
                )
                background.paste(im=image_crop, box=(x - 3, y - 3))
            else:
                background.paste(im=image_crop, box=(x, y))

        return None, 200, background
