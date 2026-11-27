"""Shared helpers for catalog tests."""

from django.contrib.auth.models import Permission

COST = "view_product_cost"
STOCK = "adjust_stock"


def grant(user, *codenames):
    """Gives ``catalog`` permissions and clears Django's permission caches."""
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="catalog", codename__in=codenames
        )
    )
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(attr, None)
    return user


def product_data(**overrides):
    data = {
        "sku": "YNX-BG66-UM",
        "name": "BG66 Ultimax",
        "category": "ACCESSORIES",
        "subcategory": "String",
        "brand": "Yonex",
        "model": "BG66 Ultimax",
        "supplier": "Yonex Philippines",
        "variant_description": "0.68 mm",
        "selling_price": "450.00",
        "cost_price": "320.00",
        "low_stock_threshold": 5,
        "is_active": True,
    }
    data.update(overrides)
    return data
