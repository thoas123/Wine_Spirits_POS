from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.authorization import Capability, assert_capability, has_shop_access
from inventory.models import InventoryMovement, MovementType, ShopInventory

from .models import Payment, PaymentMethod, Sale, SaleItem


class PosError(Exception):
    """Raised when a sale cannot be completed."""


def generate_receipt_number():
    date_part = timezone.localdate().strftime('%Y%m%d')
    return f'POS-{date_part}-{uuid4().hex[:6].upper()}'


def normalize_cart_lines(cart_lines):
    normalized = {}
    for line in cart_lines:
        product_id = int(line.get('product_id') or 0)
        quantity = int(line.get('quantity') or 0)
        if product_id <= 0 or quantity <= 0:
            raise PosError('Cart contains an invalid product or quantity.')
        normalized[product_id] = normalized.get(product_id, 0) + quantity
    if not normalized:
        raise PosError('Cart is empty.')
    return normalized


def complete_sale(*, user, shop, cart_lines, payment_method, amount_received=None, reference_number=''):
    assert_capability(user, Capability.CREATE_POS_SALES)
    if not has_shop_access(user, shop):
        raise PermissionDenied

    payment_method = payment_method or PaymentMethod.CASH
    valid_methods = {choice[0] for choice in PaymentMethod.choices}
    if payment_method not in valid_methods:
        raise PosError('Choose a valid payment method.')

    quantities_by_product = normalize_cart_lines(cart_lines)
    amount_received = Decimal(amount_received or 0)
    reference_number = (reference_number or '').strip()

    with transaction.atomic():
        inventories = (
            ShopInventory.objects.select_for_update()
            .select_related('product')
            .filter(shop=shop, product_id__in=quantities_by_product.keys(), product__is_active=True)
        )
        inventory_by_product = {inventory.product_id: inventory for inventory in inventories}

        missing_ids = set(quantities_by_product) - set(inventory_by_product)
        if missing_ids:
            raise PosError('One or more products are not stocked in this shop.')

        subtotal = Decimal('0.00')
        tax_amount = Decimal('0.00')
        sale_items = []

        for product_id, quantity in quantities_by_product.items():
            inventory = inventory_by_product[product_id]
            product = inventory.product
            if inventory.quantity < quantity:
                raise PosError(f'Insufficient stock for {product.name}.')

            line_total = product.selling_price * quantity
            line_tax = line_total * product.tax_rate / Decimal('100')
            subtotal += line_total
            tax_amount += line_tax
            sale_items.append((inventory, product, quantity, line_total))

        total_amount = subtotal + tax_amount
        if payment_method == PaymentMethod.CASH and amount_received < total_amount:
            raise PosError('Cash received is less than the sale total.')

        sale = Sale.objects.create(
            receipt_number=generate_receipt_number(),
            shop=shop,
            cashier=user,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
        )

        for inventory, product, quantity, line_total in sale_items:
            SaleItem.objects.create(
                sale=sale,
                product=product,
                product_name=product.name,
                quantity=quantity,
                unit_price=product.selling_price,
                buying_price=product.buying_price,
                tax_rate=product.tax_rate,
                line_total=line_total,
            )

            inventory.quantity -= quantity
            inventory.save(update_fields=['quantity', 'updated_at'])
            InventoryMovement.objects.create(
                shop=shop,
                product=product,
                movement_type=MovementType.SOLD,
                quantity=-quantity,
                balance_after=inventory.quantity,
                reference=sale.receipt_number,
                notes='POS sale',
                created_by=user,
            )

        Payment.objects.create(
            sale=sale,
            payment_method=payment_method,
            amount=total_amount,
            reference_number=reference_number,
            amount_received=amount_received if payment_method == PaymentMethod.CASH else None,
        )

    return sale


def parse_decimal(value):
    try:
        return Decimal(value or 0)
    except Exception as exc:
        raise ValidationError('Enter a valid amount.') from exc
