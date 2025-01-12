from django.contrib import admin

from contract.models import Contract


# Register your models here.
@admin.display(description="name")
class ContractConfig(admin.ModelAdmin):
    list_display = ("id", "name", "value", "value_open", "value_closed", "user")
    pass


admin.site.register(Contract, ContractConfig)
