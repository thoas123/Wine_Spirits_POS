from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from accounts.models import Role
from shops.models import Shop


ADMIN_ROLES = {Role.ADMINISTRATOR}
MANAGER_ROLES = {Role.SHOP_MANAGER}
CASHIER_ROLES = {Role.CASHIER}


class Capability:
    MANAGE_USERS = 'manage_users'
    ASSIGN_STAFF_TO_SHOPS = 'assign_staff_to_shops'
    MANAGE_SHOPS = 'manage_shops'
    MANAGE_CATEGORIES = 'manage_categories'
    MANAGE_PRODUCTS = 'manage_products'
    CHANGE_PRODUCT_PRICES = 'change_product_prices'
    VIEW_INVENTORY = 'view_inventory'
    MODIFY_INVENTORY = 'modify_inventory'
    RECEIVE_STOCK = 'receive_stock'
    VIEW_SALES = 'view_sales'
    CREATE_POS_SALES = 'create_pos_sales'
    MANAGE_EXPENSES = 'manage_expenses'
    VIEW_BUSINESS_REPORTS = 'view_business_reports'
    VIEW_SHOP_REPORTS = 'view_shop_reports'


ROLE_CAPABILITIES = {
    Role.ADMINISTRATOR: {
        Capability.MANAGE_USERS,
        Capability.ASSIGN_STAFF_TO_SHOPS,
        Capability.MANAGE_SHOPS,
        Capability.MANAGE_CATEGORIES,
        Capability.MANAGE_PRODUCTS,
        Capability.CHANGE_PRODUCT_PRICES,
        Capability.VIEW_INVENTORY,
        Capability.MODIFY_INVENTORY,
        Capability.RECEIVE_STOCK,
        Capability.VIEW_SALES,
        Capability.CREATE_POS_SALES,
        Capability.MANAGE_EXPENSES,
        Capability.VIEW_BUSINESS_REPORTS,
        Capability.VIEW_SHOP_REPORTS,
    },
    Role.SHOP_MANAGER: {
        Capability.VIEW_INVENTORY,
        Capability.MODIFY_INVENTORY,
        Capability.RECEIVE_STOCK,
        Capability.VIEW_SALES,
        Capability.CREATE_POS_SALES,
        Capability.MANAGE_EXPENSES,
        Capability.VIEW_SHOP_REPORTS,
    },
    Role.CASHIER: {
        Capability.VIEW_INVENTORY,
        Capability.VIEW_SALES,
        Capability.CREATE_POS_SALES,
        Capability.VIEW_SHOP_REPORTS,
    },
}


def is_business_admin(user):
    return bool(user and user.is_authenticated and user.role in ADMIN_ROLES)


def has_capability(user, capability):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return capability in ROLE_CAPABILITIES.get(user.role, set())


def get_accessible_shops(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Shop.objects.none()
    if is_business_admin(user):
        return Shop.objects.all()
    return Shop.objects.filter(
        staff_assignments__user=user,
        staff_assignments__is_active=True,
    ).distinct()


def has_shop_access(user, shop):
    if shop is None:
        return is_business_admin(user)
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_business_admin(user):
        return True
    return user.shop_assignments.filter(shop=shop, is_active=True).exists()


def filter_queryset_by_shop_access(user, queryset, shop_lookup='shop', include_business_wide=False):
    if is_business_admin(user):
        return queryset

    accessible_shops = get_accessible_shops(user)
    lookup = f'{shop_lookup}__in'
    scoped_filter = Q(**{lookup: accessible_shops})

    if include_business_wide:
        null_lookup = f'{shop_lookup}__isnull'
        scoped_filter |= Q(**{null_lookup: True})

    return queryset.filter(scoped_filter)


def get_object_shop(obj):
    if hasattr(obj, 'shop'):
        return obj.shop
    if hasattr(obj, 'sale'):
        return obj.sale.shop
    if hasattr(obj, 'stock_receive'):
        return obj.stock_receive.shop
    return None


def assert_shop_access(user, shop):
    if not has_shop_access(user, shop):
        raise PermissionDenied


def assert_capability(user, capability):
    if not has_capability(user, capability):
        raise PermissionDenied


def get_authorized_object_or_404(user, queryset, *, shop_lookup='shop', include_business_wide=False, **lookup):
    filtered_queryset = filter_queryset_by_shop_access(
        user,
        queryset,
        shop_lookup=shop_lookup,
        include_business_wide=include_business_wide,
    )
    return get_object_or_404(filtered_queryset, **lookup)


class CapabilityRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    capability = None

    def test_func(self):
        return has_capability(self.request.user, self.capability)


class AdminRoleRequiredMixin(CapabilityRequiredMixin):
    capability = Capability.MANAGE_USERS
