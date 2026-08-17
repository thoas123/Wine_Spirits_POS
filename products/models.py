from django.db import models


class Category(models.Model):
    """
    Product category for wine and spirits classification.

    Categories are managed by administrators. Duplicate names
    are prevented at the database level.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Category name (e.g., Whisky, Wine, Vodka, Beer).',
    )
    description = models.TextField(
        blank=True,
        help_text='Optional description of the category.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive categories are hidden from product forms.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'category'
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class UnitOfMeasurement(models.TextChoices):
    """Standard units for wine and spirits products."""
    BOTTLE = 'bottle', 'Bottle'
    CAN = 'can', 'Can'
    CASE = 'case', 'Case'
    KEG = 'keg', 'Keg'
    PACK = 'pack', 'Pack'
    PIECE = 'piece', 'Piece'
    OTHER = 'other', 'Other'


class Product(models.Model):
    """
    A wine or spirits product in the system.

    Products are system-wide — the same product can exist in multiple
    shops with independent inventory levels (via ShopInventory).

    SKU is unique across the entire system and enforced at DB level.

    Financial fields use DecimalField to avoid floating-point errors.
    All prices are in KES (Kenyan Shillings). Multi-currency is out of scope.

    minimum_stock_level is the system-wide default threshold.
    Individual shops can override this via ShopInventory.minimum_stock_level.
    """
    name = models.CharField(
        max_length=200,
        help_text='Product display name.',
    )
    brand = models.CharField(
        max_length=100,
        blank=True,
        help_text='Brand or manufacturer name.',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        help_text='Product category.',
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name='SKU',
        help_text='Unique product code / Stock Keeping Unit.',
    )
    buying_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Default buying/cost price in KES.',
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Default selling price in KES.',
    )
    unit_of_measurement = models.CharField(
        max_length=20,
        choices=UnitOfMeasurement.choices,
        default=UnitOfMeasurement.BOTTLE,
        help_text='Unit used for stock counting.',
    )
    minimum_stock_level = models.PositiveIntegerField(
        default=0,
        help_text='System-wide minimum stock threshold. Shops can override.',
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Tax/excise rate as a percentage (e.g., 16.00 for 16%).',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive/discontinued products are hidden from POS.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'product'
        verbose_name_plural = 'products'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(buying_price__gte=0),
                name='product_buying_price_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name='product_selling_price_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0),
                name='product_tax_rate_non_negative',
            ),
        ]

    def __str__(self):
        if self.brand:
            return f'{self.name} ({self.brand})'
        return self.name
