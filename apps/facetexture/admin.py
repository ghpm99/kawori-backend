from django.contrib import admin
from facetexture.models import Facetexture, BDOClass


# Register your models here.
class FacetextureConfig(admin.ModelAdmin):
    pass


class BDOClassConfig(admin.ModelAdmin):
    pass


admin.site.register(Facetexture, FacetextureConfig)
admin.site.register(BDOClass, BDOClassConfig)
