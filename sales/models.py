from django.conf import settings
from django.db import models


class SaleStatus(models.TextChoices):
    """Sale transaction statuses."""
    COMPLETED = 'completed', 'Completed'
    VOIDED = 'voided', 'Voided'
    REFUNDED = 'refunded', 'Refunded'


class Sale(models.Model):
    """
    A POS sale transaction header.

    Sales are never hard-deleted. Cancelled transactions are
    marked as VOIDED or REFUNDED to preserve the audit trail.

    receipt_number is unique and indexed for fast lookup.
    """
    receipt_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique sale/receipt number.',
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        related_name='sales',
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales',
    )
    status = models.CharField(
        max_length=20,
        choices=SaleStatus.choices,
        default=SaleStatus.COMPLETED,
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Pre-tax total in KES.',
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text='Total tax amount in KES.',
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Final total including tax in KES.',
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional notes (e.g., reason for void).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'sale'
        verbose_name_plural = 'sales'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['shop', '-created_at'],
                name='idx_sale_shop_date',
            ),
        ]

    def __str__(self):
        return f'Sale {self.receipt_number} — KES {self.total_amount}'


class SaleItem(models.Model):
    """
    An individual product line within a sale.

    Price and cost snapshots are captured at sale time to ensure
    historical accuracy. If product prices change later, past
    sales remain correct.

    Fields preserved at sale time:
    - product_name: product name snapshot (in case product is renamed)
    - unit_price: the selling price at the time of sale
    - buying_price: the cost price at the time of sale (for profit calc)
    - tax_rate: the tax rate at the time of sale

    NOTE: buying_price is populated from the product's current buying
    price when the sale is created. Future costing methodology (FIFO,
    weighted average) may refine how this value is determined. The
    costing methodology has NOT been selected — it must be confirmed
    with the client's accountant.
    """
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='sale_items',
    )
    product_name = models.CharField(
        max_length=200,
        help_text='Product name at the time of sale.',
    )
    quantity = models.PositiveIntegerField(
        help_text='Quantity sold.',
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Selling price per unit at time of sale (KES).',
    )
    buying_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Cost price per unit at time of sale (KES).',
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Tax rate at time of sale (percentage).',
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='quantity × unit_price (KES).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'sale item'
        verbose_name_plural = 'sale items'

    def __str__(self):
        return f'{self.product_name} × {self.quantity} @ KES {self.unit_price}'


class PaymentMethod(models.TextChoices):
    """Supported payment methods."""
    CASH = 'cash', 'Cash'
    MPESA = 'mpesa', 'M-Pesa'
    CARD = 'card', 'Card'
    OTHER = 'other', 'Other'


class Payment(models.Model):
    """
    A payment record against a sale.

    Multiple payments per sale are supported to enable split payments.
    For example, a KES 5,000 sale could be paid with:
        Payment 1: Cash KES 2,000
        Payment 2: M-Pesa KES 3,000

    amount_received is used for cash payments to calculate change.
    It is null for non-cash payment methods.

    M-Pesa/Daraja integration is NOT implemented yet.
    The reference_number field stores transaction codes when available.
    """
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Payment amount in KES.',
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Transaction reference (M-Pesa code, card ref, etc.).',
    )
    amount_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Amount tendered (for cash change calculation).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'payment'
        verbose_name_plural = 'payments'

    def __str__(self):
        return (
            f'{self.get_payment_method_display()} — '
            f'KES {self.amount}'
        )
