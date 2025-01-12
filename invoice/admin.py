from django.contrib import admin

from invoice.models import Invoice


# Register your models here.
class InvoiceConfig(admin.ModelAdmin):
    list_display = ("id", "name", "value", "value_open", "value_closed", "status", "type", "fixed", "active", "user")
    pass


admin.site.register(Invoice, InvoiceConfig)
