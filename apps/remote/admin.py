from django.contrib import admin
from remote.models import Config, Screenshot


# Register your models here.
class ConfigAdmin(admin.ModelAdmin):
    pass


admin.site.register(Config, ConfigAdmin)


class ScreenshotAdmin(admin.ModelAdmin):
    pass


admin.site.register(Screenshot, ScreenshotAdmin)
