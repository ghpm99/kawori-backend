from django.contrib import admin

from facetexture.models import BDOClass, Character, Facetexture, PreviewBackground


# Register your models here.
class FacetextureConfig(admin.ModelAdmin):
    list_display = ("user", "characters")


class CharacterConfig(admin.ModelAdmin):
    list_display = ("id", "name", "image")


class BDOClassConfig(admin.ModelAdmin):
    list_display = ("name", "abbreviation")


class PreviewBackgroundConfig(admin.ModelAdmin):
    pass


admin.site.register(Facetexture, FacetextureConfig)
admin.site.register(Character, CharacterConfig)
admin.site.register(BDOClass, BDOClassConfig)
admin.site.register(PreviewBackground, PreviewBackgroundConfig)
