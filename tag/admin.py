from django.contrib import admin

from tag.models import Tag


# Register your models here.
class TagConfig(admin.ModelAdmin):
    list_display = ("id", "name", "user")
    pass


admin.site.register(Tag, TagConfig)
