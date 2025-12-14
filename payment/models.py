from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from invoice.models import Invoice


# Create your models here.
class Payment(models.Model):

    class Meta:
        db_table = "financial_payment"

    TYPE_CREDIT = 0
    TYPE_DEBIT = 1

    TYPES = [(TYPE_CREDIT, "credit"), (TYPE_DEBIT, "debit")]

    STATUS_OPEN = 0
    STATUS_DONE = 1

    STATUS = [(STATUS_OPEN, "open"), (STATUS_DONE, "done")]

    status = models.IntegerField(default=STATUS_OPEN, choices=STATUS)
    type = models.IntegerField(default=TYPE_CREDIT, choices=TYPES)
    name = models.TextField(max_length=255)
    description = models.TextField(max_length=1024, blank=True)
    reference = models.TextField(max_length=1024, blank=True)
    date = models.DateField()
    installments = models.IntegerField(default=1)
    payment_date = models.DateField()
    fixed = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0.0))
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def set_value(self, value):
        self.invoice.set_value(value)
        self.value = value
        self.save()

    def close_value(self):
        self.invoice.close_value(self.value)
        self.status = self.STATUS_DONE
        self.save()

    def to_dict(self, include_related: bool = False) -> dict:
        data = {
            "id": self.id,
            "status": self.status,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "reference": self.reference,
            "date": self.date.isoformat() if self.date else None,
            "installments": self.installments,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "fixed": self.fixed,
            "active": self.active,
            "value": float(self.value) if self.value is not None else None,
            "invoice_id": self.invoice_id,
            "user_id": self.user_id,
        }

        if include_related:
            if self.invoice_id:
                try:
                    data["invoice"] = self.invoice.to_dict()
                except Exception:
                    data["invoice"] = {"id": self.invoice_id}
            if self.user_id:
                try:
                    data["user"] = {"id": self.user_id, "username": self.user.username}
                except Exception:
                    data["user"] = {"id": self.user_id}

        return data
