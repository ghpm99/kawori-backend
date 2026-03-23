class SaveDetailUseCase:
    def execute(self, user, data, facetexture_model):
        facetexture = facetexture_model.objects.filter(user=user).first()

        if facetexture is None:
            facetexture = facetexture_model(user=user, characters=data)
            facetexture.save()
            return {"msg": "Facetexture criado com sucesso"}, 201

        facetexture.characters = data
        facetexture.save()
        return {"msg": "Facetexture atualizado com sucesso"}, 200
