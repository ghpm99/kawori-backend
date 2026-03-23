class CreateTagUseCase:
    def validate_uniqueness(self, user, tag_model, name):
        tag_in_database = tag_model.objects.filter(name=name, user=user).first()
        if tag_in_database is not None:
            return {"msg": "Tag já existe"}, 404

        return None, None

    def create(self, user, tag_model, name, color):
        tag_model.objects.create(name=name, color=color, user=user)
        return {"msg": "Tag inclusa com sucesso"}, 200
