from django.contrib import admin

from payment.models import Payment


# Register your models here.
class PaymentConfig(admin.ModelAdmin):
    list_display = ("id", "name", "value", "payment_date", "status", "type", "date", "fixed", "active", "user")
    pass


admin.site.register(Payment, PaymentConfig)
