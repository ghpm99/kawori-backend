from django.contrib import admin
from facetexture.models import Facetexture, BDOClass, PreviewBackground, Character


# Register your models here.
class FacetextureConfig(admin.ModelAdmin):
    list_display = ('user', 'characters')
    pass


class CharacterConfig(admin.ModelAdmin):
    list_display = ('id', 'name', 'image')
    pass


class BDOClassConfig(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    pass


class PreviewBackgroundConfig(admin.ModelAdmin):
    pass


admin.site.register(Facetexture, FacetextureConfig)
admin.site.register(Character, CharacterConfig)
admin.site.register(BDOClass, BDOClassConfig)
admin.site.register(PreviewBackground, PreviewBackgroundConfig)
