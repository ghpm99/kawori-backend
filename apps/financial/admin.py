from django.contrib import admin
from financial.models import Payment


# Register your models here.
class PaymentConfig(admin.ModelAdmin):
    list_display = ('status', 'type', 'name', 'fixed', 'active', 'value')
    pass


admin.site.register(Payment, PaymentConfig)
