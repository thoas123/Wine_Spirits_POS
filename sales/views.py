from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.authorization import (
    Capability,
    assert_capability,
    filter_queryset_by_shop_access,
    get_authorized_object_or_404,
)
from inventory.models import ShopInventory
from shops.models import Shop

from .models import PaymentMethod, Sale
from .services import PosError, complete_sale


def get_sale_shop_queryset(user):
    return filter_queryset_by_shop_access(user, Shop.objects.filter(is_active=True), shop_lookup='id')


@login_required
@require_http_methods(['GET', 'POST'])
def pos(request):
    assert_capability(request.user, Capability.CREATE_POS_SALES)
    shops = get_sale_shop_queryset(request.user).order_by('name')
    selected_shop = None

    shop_id = request.POST.get('shop') if request.method == 'POST' else request.GET.get('shop')
    if shop_id:
        selected_shop = get_object_or_404(shops, pk=shop_id)
    elif shops.count() == 1:
        selected_shop = shops.first()

    if request.method == 'POST':
        if selected_shop is None:
            raise PermissionDenied

        cart_lines = []
        product_ids = request.POST.getlist('product_id')
        quantities = request.POST.getlist('quantity')
        for product_id, quantity in zip(product_ids, quantities):
            if int(quantity or 0) > 0:
                cart_lines.append({'product_id': product_id, 'quantity': quantity})

        try:
            sale = complete_sale(
                user=request.user,
                shop=selected_shop,
                cart_lines=cart_lines,
                payment_method=request.POST.get('payment_method') or PaymentMethod.CASH,
                amount_received=request.POST.get('amount_received'),
                reference_number=request.POST.get('reference_number', ''),
            )
        except PosError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f'Sale {sale.receipt_number} completed.')
            return redirect('sales:receipt', pk=sale.pk)

    inventories = ShopInventory.objects.none()
    if selected_shop is not None:
        inventories = (
            ShopInventory.objects.select_related('product', 'product__category')
            .filter(shop=selected_shop, product__is_active=True, quantity__gt=0)
            .order_by('product__name')
        )

    return render(
        request,
        'sales/pos.html',
        {
            'shops': shops,
            'selected_shop': selected_shop,
            'inventories': inventories,
            'payment_methods': PaymentMethod.choices,
        },
    )


@login_required
def receipt(request, pk):
    assert_capability(request.user, Capability.VIEW_SALES)
    sale = get_authorized_object_or_404(
        request.user,
        Sale.objects.select_related('shop', 'cashier').prefetch_related('items', 'payments'),
        pk=pk,
    )
    return render(request, 'sales/receipt.html', {'sale': sale})
