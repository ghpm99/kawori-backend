class ReorderCharacterUseCase:
    def execute(
        self, user, character_id, data, character_model, transaction_module, connection_module
    ):
        index_destination = data.get("index_destination")
        if index_destination is None:
            return {"data": "Index de destino não informado"}, 400

        character = character_model.objects.filter(id=character_id, user=user).first()
        if character is None:
            return {"data": "Não foi encontrado personagem com esse ID"}, 404

        with transaction_module.atomic():
            query = """
                UPDATE
                    facetexture_character
                SET
                    "order" = %(order)s
                WHERE
                    1 = 1
                    AND id = %(id)s
                    AND user_id = %(user)s
            """

            with connection_module.cursor() as cursor:
                cursor.execute(
                    query, {"order": index_destination, "id": character_id, "user": user.id}
                )

            query = """
                UPDATE
                    facetexture_character
                SET
                    "order" = (
                        CASE
                            WHEN %(new_order)s > %(current_order)s THEN ("order" - 1)
                            WHEN %(new_order)s < %(current_order)s THEN ("order" + 1)
                        END
                    )
                WHERE
                    1 = 1
                    AND CASE
                        WHEN %(new_order)s > %(current_order)s THEN (
                            "order" <= %(new_order)s
                            AND "order" > %(current_order)s
                        )
                        WHEN %(new_order)s < %(current_order)s THEN (
                            "order" >= %(new_order)s
                            AND "order" < %(current_order)s
                        )
                    END
                    AND id <> %(id)s
                    AND active = true
                    AND user_id = %(user)s
            """

            with connection_module.cursor() as cursor:
                cursor.execute(
                    query,
                    {
                        "current_order": character.order,
                        "new_order": index_destination,
                        "id": character_id,
                        "user": user.id,
                    },
                )

        characters = character_model.objects.filter(user=user, active=True).all().order_by("order")
        payload = [{"id": character.id, "order": character.order} for character in characters]
        return {"data": payload}, 200
