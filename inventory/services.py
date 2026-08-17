from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction

from core.authorization import has_capability, has_shop_access, Capability

from .models import InventoryMovement, MovementType, ShopInventory


class InventoryError(Exception):
    """Base class for inventory domain errors."""


class InventoryRecordNotFound(InventoryError):
    pass


class InvalidQuantity(InventoryError):
    pass


class InsufficientStock(InventoryError):
    pass


class MissingAdjustmentReason(InventoryError):
    pass


class StockStatus:
    IN_STOCK = 'in_stock'
    LOW_STOCK = 'low_stock'
    OUT_OF_STOCK = 'out_of_stock'


STOCK_STATUS_LABELS = {
    StockStatus.IN_STOCK: 'In stock',
    StockStatus.LOW_STOCK: 'Low stock',
    StockStatus.OUT_OF_STOCK: 'Out of stock',
}


class MovementDirection:
    IN = 'in'
    OUT = 'out'


INCREASE_MOVEMENT_TYPES = {
    MovementType.RECEIVED,
    MovementType.ADJUSTMENT,
    MovementType.TRANSFER_IN,
}

DECREASE_MOVEMENT_TYPES = {
    MovementType.SOLD,
    MovementType.DAMAGED,
    MovementType.WRITTEN_OFF,
    MovementType.TRANSFER_OUT,
}


@dataclass(frozen=True)
class InventoryChangeResult:
    inventory: ShopInventory
    movement: InventoryMovement
    previous_quantity: int
    new_quantity: int


def get_stock_status(quantity, minimum_stock_level):
    """
    Stock status boundary:
    - quantity <= 0: out of stock
    - quantity <= minimum threshold: low stock
    - otherwise: in stock
    """
    if quantity <= 0:
        return StockStatus.OUT_OF_STOCK
    if quantity <= minimum_stock_level:
        return StockStatus.LOW_STOCK
    return StockStatus.IN_STOCK


def get_stock_status_label(status):
    return STOCK_STATUS_LABELS[status]


def validate_quantity(quantity):
    if quantity is None or quantity <= 0:
        raise InvalidQuantity('Quantity must be greater than zero.')
    return int(quantity)


def assert_inventory_shop_access(user, shop):
    if not has_shop_access(user, shop):
        raise PermissionDenied


def assert_can_adjust_inventory(user, shop):
    if not has_capability(user, Capability.MODIFY_INVENTORY):
        raise PermissionDenied
    assert_inventory_shop_access(user, shop)


def get_inventory_for_update(shop, product):
    try:
        return ShopInventory.objects.select_for_update().get(shop=shop, product=product)
    except ShopInventory.DoesNotExist as exc:
        raise InventoryRecordNotFound('Inventory record was not found for this shop and product.') from exc


def change_stock(
    *,
    user,
    shop,
    product,
    quantity,
    direction,
    movement_type,
    reason='',
    reference='',
    require_reason=False,
):
    assert_can_adjust_inventory(user, shop)
    quantity = validate_quantity(quantity)
    reason = reason.strip()
    reference = reference.strip()

    if require_reason and not reason:
        raise MissingAdjustmentReason('A reason is required for manual stock adjustments.')

    if direction not in (MovementDirection.IN, MovementDirection.OUT):
        raise InvalidQuantity('Invalid movement direction.')

    signed_quantity = quantity if direction == MovementDirection.IN else -quantity

    with transaction.atomic():
        inventory = get_inventory_for_update(shop, product)
        previous_quantity = inventory.quantity
        new_quantity = previous_quantity + signed_quantity

        if new_quantity < 0:
            raise InsufficientStock('Stock cannot become negative.')

        inventory.quantity = new_quantity
        inventory.save(update_fields=['quantity', 'updated_at'])

        movement = InventoryMovement.objects.create(
            shop=shop,
            product=product,
            movement_type=movement_type,
            quantity=signed_quantity,
            balance_after=new_quantity,
            reference=reference,
            notes=reason,
            created_by=user,
        )

    return InventoryChangeResult(
        inventory=inventory,
        movement=movement,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
    )


def increase_stock(*, user, shop, product, quantity, movement_type=MovementType.ADJUSTMENT, reason='', reference=''):
    return change_stock(
        user=user,
        shop=shop,
        product=product,
        quantity=quantity,
        direction=MovementDirection.IN,
        movement_type=movement_type,
        reason=reason,
        reference=reference,
    )


def decrease_stock(*, user, shop, product, quantity, movement_type=MovementType.ADJUSTMENT, reason='', reference=''):
    return change_stock(
        user=user,
        shop=shop,
        product=product,
        quantity=quantity,
        direction=MovementDirection.OUT,
        movement_type=movement_type,
        reason=reason,
        reference=reference,
    )


def adjust_stock(*, user, shop, product, quantity, direction, reason, reference=''):
    movement_type = MovementType.ADJUSTMENT
    return change_stock(
        user=user,
        shop=shop,
        product=product,
        quantity=quantity,
        direction=direction,
        movement_type=movement_type,
        reason=reason,
        reference=reference,
        require_reason=True,
    )
