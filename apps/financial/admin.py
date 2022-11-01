from django.contrib import admin
from financial.models import Contract, Invoice, Month, Payment, Tag


# Register your models here.
@admin.display(description='name')
class ContractConfig(admin.ModelAdmin):
    list_display = ('id', 'name', 'value', 'value_open', 'value_closed',
                    'user')
    pass


class InvoiceConfig(admin.ModelAdmin):
    list_display = ('id', 'name', 'value', 'value_open', 'value_closed',
                    'status', 'type',  'fixed', 'active', 'user')
    pass


class PaymentConfig(admin.ModelAdmin):
    list_display = ('id', 'name', 'value', 'payment_date',
                    'status', 'type', 'date', 'fixed', 'active', 'user')
    pass


class TagConfig(admin.ModelAdmin):
    list_display = ('id', 'name', 'user')
    pass

class MonthConfig(admin.ModelAdmin):
    list_display = ('id', 'status', 'month', 'year', 'total')
    pass

admin.site.register(Contract, ContractConfig)
admin.site.register(Invoice, InvoiceConfig)
admin.site.register(Payment, PaymentConfig)
admin.site.register(Tag, TagConfig)
admin.site.register(Month, MonthConfig)
