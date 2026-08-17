from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import render

from expenses.models import Expense
from inventory.models import ShopInventory, StockReceive
from products.models import Product
from sales.models import Sale
from shops.models import Shop

from .authorization import (
    Capability,
    assert_capability,
    get_authorized_object_or_404,
    has_capability,
)


@login_required
def home(request):
    """Render the role-appropriate landing screen."""
    if request.user.is_cashier_role:
        products = Product.objects.select_related('category').filter(is_active=True)[:12]
        return render(request, 'pos_placeholder.html', {'products': products})

    inventory_records = ShopInventory.objects.select_related('shop', 'product')
    stock_alerts = [
        item
        for item in inventory_records
        if item.quantity <= item.effective_minimum_stock
    ]
    context = {
        'total_revenue': Sale.objects.aggregate(total=Sum('total_amount'))['total'] or 0,
        'sales_count': Sale.objects.count(),
        'product_count': Product.objects.filter(is_active=True).count(),
        'shop_count': Shop.objects.filter(is_active=True).count(),
        'low_stock_count': len(stock_alerts),
        'recent_sales': Sale.objects.select_related('shop').all()[:8],
        'stock_watch': stock_alerts[:8],
    }
    return render(request, 'home.html', context)


@login_required
def staff_placeholder(request):
    assert_capability(request.user, Capability.MANAGE_USERS)
    return render(request, 'placeholder.html', {'title': 'Staff'})


@login_required
def shops_placeholder(request):
    assert_capability(request.user, Capability.MANAGE_SHOPS)
    return render(request, 'placeholder.html', {'title': 'Shops'})


@login_required
def products_placeholder(request):
    if request.method != 'GET':
        assert_capability(request.user, Capability.MANAGE_PRODUCTS)
    elif not has_capability(request.user, Capability.MANAGE_PRODUCTS):
        raise PermissionDenied
    products = Product.objects.all()
    return render(request, 'placeholder.html', {'title': 'Products', 'objects': products})


@login_required
def inventory_detail(request, pk):
    capability = Capability.MODIFY_INVENTORY if request.method != 'GET' else Capability.VIEW_INVENTORY
    assert_capability(request.user, capability)
    inventory = get_authorized_object_or_404(
        request.user,
        ShopInventory.objects.select_related('shop', 'product'),
        pk=pk,
    )
    return render(request, 'placeholder.html', {'title': 'Inventory', 'object': inventory})


@login_required
def sale_detail(request, pk):
    assert_capability(request.user, Capability.VIEW_SALES)
    sale = get_authorized_object_or_404(
        request.user,
        Sale.objects.select_related('shop', 'cashier'),
        pk=pk,
    )
    return render(request, 'placeholder.html', {'title': 'Sale', 'object': sale})


@login_required
def stock_receive_detail(request, pk):
    assert_capability(request.user, Capability.RECEIVE_STOCK)
    stock_receive = get_authorized_object_or_404(
        request.user,
        StockReceive.objects.select_related('shop', 'supplier', 'received_by'),
        pk=pk,
    )
    return render(request, 'placeholder.html', {'title': 'Stock Receiving', 'object': stock_receive})


@login_required
def expense_detail(request, pk):
    assert_capability(request.user, Capability.MANAGE_EXPENSES)
    expense = get_authorized_object_or_404(
        request.user,
        Expense.objects.select_related('shop', 'recorded_by'),
        include_business_wide=False,
        pk=pk,
    )
    return render(request, 'placeholder.html', {'title': 'Expense', 'object': expense})


@login_required
def shop_detail(request, pk):
    shop = get_authorized_object_or_404(request.user, Shop.objects.all(), shop_lookup='id', pk=pk)
    return render(request, 'placeholder.html', {'title': 'Shop', 'object': shop})


def forbidden(request, exception=None):
    return render(request, '403.html', status=403)
