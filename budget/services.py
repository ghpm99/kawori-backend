from decimal import Decimal
from django.db.models.signals import post_save
from django.db.models.functions import Trim
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from tag.models import Tag, BudgetTag
from django.db import transaction

from .models import Budget

DEFAULT_BUDGETS = [
    {"name": "Custos fixos", "allocation_percentage": Decimal("40.0"), "color": "#1f77b4"},
    {"name": "Conforto", "allocation_percentage": Decimal("20.0"), "color": "#ff7f0e"},
    {"name": "Metas", "allocation_percentage": Decimal("5.0"), "color": "#2ca02c"},
    {"name": "Prazeres", "allocation_percentage": Decimal("5.0"), "color": "#d62728"},
    {"name": "Liberdade financeira", "allocation_percentage": Decimal("25.0"), "color": "#9467bd"},
    {"name": "Conhecimento", "allocation_percentage": Decimal("5.0"), "color": "#8c564b"},
]


def create_default_budgets_for_user(user: User):

    if Budget.objects.filter(user=user).exists():
        return

    try:
        with transaction.atomic():
            for item in DEFAULT_BUDGETS:
                name = item.get("name", "")
                pct = item.get("allocation_percentage", Decimal("0.0"))
                color = item.get("color", "#1f77b4")

                tag = (
                    Tag.objects.annotate(trimmed_name=Trim("name")).filter(trimmed_name__iexact=name, user=user).first()
                )

                if tag is None:
                    tag = Tag.objects.create(name=name, color=color, user=user)
                else:
                    tag.color = color
                    tag.save()

                budget = Budget.objects.create(user=user, allocation_percentage=pct)

                BudgetTag.objects.create(budget=budget, tag=tag)

    except Exception as e:
        print(f"Error creating default budgets for user {user.id}: {e}")
        pass
