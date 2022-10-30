from django.contrib import admin
from facetexture.models import Facetexture, BDOClass, PreviewBackground


# Register your models here.
class FacetextureConfig(admin.ModelAdmin):
    list_display = ('user', 'characters')
    pass


class BDOClassConfig(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    pass


class PreviewBackgroundConfig(admin.ModelAdmin):
    pass


admin.site.register(Facetexture, FacetextureConfig)
admin.site.register(BDOClass, BDOClassConfig)
admin.site.register(PreviewBackground, PreviewBackgroundConfig)
