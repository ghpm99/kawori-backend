from django.contrib import admin
from financial.models import Contract, Invoice, Payment, Tag


# Register your models here.
@admin.display(description='name')
class ContractConfig(admin.ModelAdmin):
    pass


class InvoiceConfig(admin.ModelAdmin):
    list_display = ('status', 'type', 'name', 'fixed', 'active', 'value', 'contract')
    pass


class PaymentConfig(admin.ModelAdmin):
    list_display = ('status', 'type', 'name', 'fixed', 'active', 'value', 'invoice')
    pass

class TagConfig(admin.ModelAdmin):
    list_display = ('id', 'name')
    pass

admin.site.register(Contract, ContractConfig)
admin.site.register(Invoice, InvoiceConfig)
admin.site.register(Payment, PaymentConfig)
admin.site.register(Tag, TagConfig)
