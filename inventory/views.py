from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.authorization import (
    Capability,
    assert_capability,
    filter_queryset_by_shop_access,
    get_authorized_object_or_404,
    has_capability,
)
from products.models import Category

from .forms import InventoryAdjustmentForm
from .models import InventoryMovement, ShopInventory
from .services import (
    InsufficientStock,
    InventoryError,
    StockStatus,
    adjust_stock,
    get_stock_status,
    get_stock_status_label,
)


def paginate(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page'))


def inventory_queryset_for_user(user):
    return filter_queryset_by_shop_access(
        user,
        ShopInventory.objects.select_related('shop', 'product', 'product__category'),
    )


def movement_queryset_for_user(user):
    return filter_queryset_by_shop_access(
        user,
        InventoryMovement.objects.select_related('shop', 'product', 'created_by'),
    )


def apply_inventory_filters(queryset, request, user):
    search = request.GET.get('q', '').strip()
    shop_id = request.GET.get('shop', '').strip()
    category_id = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()
    product_status = request.GET.get('product_status', '').strip()

    if search:
        queryset = queryset.filter(
            Q(product__name__icontains=search)
            | Q(product__brand__icontains=search)
            | Q(product__sku__icontains=search)
        )

    if shop_id:
        accessible_shop_ids = {str(pk) for pk in user.get_accessible_shops().values_list('pk', flat=True)}
        if shop_id in accessible_shop_ids:
            queryset = queryset.filter(shop_id=shop_id)
        else:
            queryset = queryset.none()

    if category_id:
        queryset = queryset.filter(product__category_id=category_id)

    if product_status == 'active':
        queryset = queryset.filter(product__is_active=True)
    elif product_status == 'inactive':
        queryset = queryset.filter(product__is_active=False)

    if status:
        matching_ids = [
            inventory.pk for inventory in queryset
            if get_stock_status(inventory.quantity, inventory.effective_minimum_stock) == status
        ]
        queryset = queryset.filter(pk__in=matching_ids)

    return queryset, {
        'q': search,
        'shop': shop_id,
        'category': category_id,
        'status': status,
        'product_status': product_status,
    }


def decorate_inventory_rows(inventories):
    for inventory in inventories:
        status = inventory.stock_status
        inventory.stock_status_code = status
        inventory.stock_status_label = get_stock_status_label(status)


@login_required
def inventory_list(request):
    assert_capability(request.user, Capability.VIEW_INVENTORY)
    inventories, filters = apply_inventory_filters(
        inventory_queryset_for_user(request.user),
        request,
        request.user,
    )
    page_obj = paginate(request, inventories.order_by('shop__name', 'product__name'))
    decorate_inventory_rows(page_obj.object_list)

    return render(
        request,
        'inventory/inventory_list.html',
        {
            'page_obj': page_obj,
            'filters': filters,
            'shops': request.user.get_accessible_shops().order_by('name'),
            'categories': Category.objects.order_by('name'),
            'stock_status_options': (
                (StockStatus.IN_STOCK, 'In stock'),
                (StockStatus.LOW_STOCK, 'Low stock'),
                (StockStatus.OUT_OF_STOCK, 'Out of stock'),
            ),
            'can_adjust_inventory': has_capability(request.user, Capability.MODIFY_INVENTORY),
        },
    )


@login_required
def inventory_detail(request, pk):
    if request.method != 'GET':
        raise PermissionDenied
    assert_capability(request.user, Capability.VIEW_INVENTORY)
    inventory = get_authorized_object_or_404(
        request.user,
        ShopInventory.objects.select_related('shop', 'product', 'product__category'),
        pk=pk,
    )
    status = inventory.stock_status
    movements = movement_queryset_for_user(request.user).filter(
        shop=inventory.shop,
        product=inventory.product,
    )

    return render(
        request,
        'inventory/inventory_detail.html',
        {
            'inventory': inventory,
            'stock_status_code': status,
            'stock_status_label': get_stock_status_label(status),
            'page_obj': paginate(request, movements, per_page=10),
            'can_adjust_inventory': has_capability(request.user, Capability.MODIFY_INVENTORY),
        },
    )


@login_required
def movement_list(request):
    if request.user.is_cashier_role:
        raise PermissionDenied
    assert_capability(request.user, Capability.VIEW_INVENTORY)

    movements = movement_queryset_for_user(request.user)
    search = request.GET.get('q', '').strip()
    shop_id = request.GET.get('shop', '').strip()
    movement_type = request.GET.get('movement_type', '').strip()

    if search:
        movements = movements.filter(
            Q(product__name__icontains=search)
            | Q(product__brand__icontains=search)
            | Q(product__sku__icontains=search)
            | Q(reference__icontains=search)
        )
    if shop_id:
        accessible_shop_ids = {str(pk) for pk in request.user.get_accessible_shops().values_list('pk', flat=True)}
        if shop_id in accessible_shop_ids:
            movements = movements.filter(shop_id=shop_id)
        else:
            movements = movements.none()
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    return render(
        request,
        'inventory/movement_list.html',
        {
            'page_obj': paginate(request, movements, per_page=15),
            'shops': request.user.get_accessible_shops().order_by('name'),
            'movement_types': InventoryMovement._meta.get_field('movement_type').choices,
            'filters': {'q': search, 'shop': shop_id, 'movement_type': movement_type},
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def inventory_adjust(request, pk=None):
    if not has_capability(request.user, Capability.MODIFY_INVENTORY):
        raise PermissionDenied

    inventory = None
    if pk is not None:
        inventory = get_authorized_object_or_404(
            request.user,
            ShopInventory.objects.select_related('shop', 'product'),
            pk=pk,
        )

    form = InventoryAdjustmentForm(request.POST or None, user=request.user, inventory=inventory)

    if request.method == 'POST' and form.is_valid():
        try:
            result = adjust_stock(
                user=request.user,
                shop=form.cleaned_data['shop'],
                product=form.cleaned_data['product'],
                quantity=form.cleaned_data['quantity'],
                direction=form.cleaned_data['direction'],
                reason=form.cleaned_data['reason'],
                reference=form.cleaned_data['reference'],
            )
        except InsufficientStock as exc:
            form.add_error('quantity', str(exc))
        except InventoryError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f'Inventory adjusted from {result.previous_quantity} to {result.new_quantity}.',
            )
            return redirect('inventory:detail', pk=result.inventory.pk)

    return render(
        request,
        'inventory/inventory_adjust.html',
        {'form': form, 'inventory': inventory},
    )
