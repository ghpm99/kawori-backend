from django.contrib import admin

from financial.models import Month


# Register your models here.
class MonthConfig(admin.ModelAdmin):
    list_display = ("id", "status", "month", "year", "total")


admin.site.register(Month, MonthConfig)
