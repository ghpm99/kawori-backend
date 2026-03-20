from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.functions import Trim

from tag.models import Tag

from .models import Budget

DEFAULT_BUDGETS = [
    {"name": "Entradas", "allocation_percentage": Decimal("0.0"), "color": "#4222d7"},
    {
        "name": "Custos fixos",
        "allocation_percentage": Decimal("40.0"),
        "color": "#1f77b4",
    },
    {"name": "Conforto", "allocation_percentage": Decimal("20.0"), "color": "#ff7f0e"},
    {"name": "Metas", "allocation_percentage": Decimal("5.0"), "color": "#2ca02c"},
    {"name": "Prazeres", "allocation_percentage": Decimal("5.0"), "color": "#d62728"},
    {
        "name": "Liberdade financeira",
        "allocation_percentage": Decimal("25.0"),
        "color": "#9467bd",
    },
    {
        "name": "Conhecimento",
        "allocation_percentage": Decimal("5.0"),
        "color": "#8c564b",
    },
]


def create_default_budgets_for_user(user: User):
    try:
        with transaction.atomic():
            for item in DEFAULT_BUDGETS:
                name = item["name"]
                pct = item.get("allocation_percentage", Decimal("0.0"))
                color = item.get("color", "#1f77b4")

                # --- TAG ---
                tag, _ = Tag.objects.annotate(trimmed_name=Trim("name")).get_or_create(
                    user=user,
                    trimmed_name__iexact=name,
                    defaults={
                        "name": name,
                        "color": color,
                    },
                )

                # Atualiza cor caso tenha mudado
                if tag.color != color:
                    tag.color = color
                    tag.save(update_fields=["color"])

                # --- BUDGET ---
                Budget.objects.update_or_create(
                    user=user,
                    tag=tag,
                    defaults={
                        "allocation_percentage": pct,
                    },
                )

    except Exception as e:
        print(f"Error creating default budgets for user {user.id}: {e}")
