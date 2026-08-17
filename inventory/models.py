from django.conf import settings
from django.db import models
from django.utils import timezone


class Supplier(models.Model):
    """
    A supplier/vendor who provides stock to the business.

    Basic contact information for stock receiving traceability.
    No purchase order automation or supplier portal is in scope.
    """
    name = models.CharField(
        max_length=200,
        help_text='Supplier / vendor name.',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Supplier contact phone number.',
    )
    email = models.EmailField(
        blank=True,
        help_text='Supplier contact email.',
    )
    address = models.TextField(
        blank=True,
        help_text='Supplier physical address.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive suppliers are hidden from receiving forms.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'supplier'
        verbose_name_plural = 'suppliers'
        ordering = ['name']

    def __str__(self):
        return self.name


class ShopInventory(models.Model):
    """
    Per-shop stock level for a product.

    Each (shop, product) pair has exactly one inventory record,
    enforced by a unique constraint. The same product can exist
    in multiple shops with independent quantities.

    minimum_stock_level:
        If set (not None), overrides the product's system-wide
        minimum_stock_level for this specific shop. If None,
        the product-level default applies.
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='inventory_records',
        help_text='The shop holding this inventory.',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='shop_inventory_records',
        help_text='The product being tracked.',
    )
    quantity = models.IntegerField(
        default=0,
        help_text='Current stock quantity. May be negative in edge cases.',
    )
    minimum_stock_level = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            'Shop-specific minimum stock threshold. '
            'If null, the product-level default is used.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'shop inventory'
        verbose_name_plural = 'shop inventories'
        constraints = [
            models.UniqueConstraint(
                fields=['shop', 'product'],
                name='unique_shop_product_inventory',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name='shop_inventory_quantity_non_negative',
            ),
        ]
        ordering = ['shop__name', 'product__name']

    def __str__(self):
        return f'{self.product} @ {self.shop} — qty: {self.quantity}'

    @property
    def effective_minimum_stock(self):
        """Return shop-specific minimum or fall back to product default."""
        if self.minimum_stock_level is not None:
            return self.minimum_stock_level
        return self.product.minimum_stock_level

    @property
    def stock_status(self):
        from .services import get_stock_status

        return get_stock_status(self.quantity, self.effective_minimum_stock)


class MovementType(models.TextChoices):
    """Types of inventory movements."""
    RECEIVED = 'received', 'Stock Received'
    SOLD = 'sold', 'Sold'
    DAMAGED = 'damaged', 'Damaged'
    WRITTEN_OFF = 'written_off', 'Written Off'
    ADJUSTMENT = 'adjustment', 'Adjustment'
    TRANSFER_IN = 'transfer_in', 'Transfer In'
    TRANSFER_OUT = 'transfer_out', 'Transfer Out'


class InventoryMovement(models.Model):
    """
    Append-only record of inventory movements.

    Every change to a shop's stock level should create an
    InventoryMovement record. This provides a full audit trail
    of how inventory levels changed over time.

    Movements are immutable — once created, they are never
    updated or deleted. There is no updated_at field.

    quantity is signed:
        Positive = stock in (received, adjustment up, transfer in)
        Negative = stock out (sold, damaged, written off, transfer out)

    balance_after captures the inventory balance immediately after
    this movement, enabling point-in-time balance reconstruction.
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='inventory_movements',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='inventory_movements',
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.IntegerField(
        help_text='Signed quantity: positive for in, negative for out.',
    )
    balance_after = models.IntegerField(
        help_text='Stock balance after this movement.',
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text='Reference number (receipt, invoice, delivery note).',
    )
    notes = models.TextField(
        blank=True,
        help_text='Additional notes or reason for the movement.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='inventory_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'inventory movement'
        verbose_name_plural = 'inventory movements'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_after__gte=0),
                name='inventory_movement_balance_after_non_negative',
            ),
        ]
        indexes = [
            models.Index(
                fields=['shop', 'product', '-created_at'],
                name='idx_movement_shop_product_date',
            ),
        ]

    def __str__(self):
        return (
            f'{self.get_movement_type_display()} — '
            f'{self.product} @ {self.shop} — '
            f'qty: {self.quantity:+d}'
        )


class StockReceive(models.Model):
    """
    Header for a stock receiving transaction.

    Represents a single delivery/receiving event at a shop.
    A StockReceive can contain multiple StockReceiveItems,
    supporting receiving of multiple products in one delivery.
    """
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='stock_receives',
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_receives',
        help_text='Supplier for this delivery. Optional.',
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_receives',
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Delivery note or invoice reference number.',
    )
    notes = models.TextField(
        blank=True,
    )
    received_at = models.DateTimeField(
        default=timezone.now,
        help_text='Date and time the stock was received.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'stock receive'
        verbose_name_plural = 'stock receives'
        ordering = ['-received_at']

    def __str__(self):
        supplier_name = self.supplier.name if self.supplier else 'No supplier'
        return f'Receive #{self.pk} — {self.shop} from {supplier_name}'


class StockReceiveItem(models.Model):
    """
    An individual product line within a stock receiving transaction.

    buying_price is captured at the time of receiving to support
    future costing methodologies (FIFO, weighted average, etc.).

    NOTE: The costing methodology has NOT been selected.
    It must be confirmed with the client's accountant.
    This field preserves the data needed for either approach.
    """
    stock_receive = models.ForeignKey(
        StockReceive,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='stock_receive_items',
    )
    quantity = models.PositiveIntegerField(
        help_text='Quantity received.',
    )
    buying_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Buying price per unit at time of receiving (KES).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'stock receive item'
        verbose_name_plural = 'stock receive items'

    def __str__(self):
        return f'{self.product} × {self.quantity} @ KES {self.buying_price}'
