from django.contrib import admin
from financial.models import Payment


# Register your models here.
class PaymentConfig(admin.ModelAdmin):
    pass


admin.site.register(Payment, PaymentConfig)
