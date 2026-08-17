from django.conf import settings
from django.db import models


class ExpenseCategory(models.TextChoices):
    """Expense categories as defined in the BRD."""
    RENT = 'rent', 'Rent'
    ELECTRICITY = 'electricity', 'Electricity'
    TRANSPORT = 'transport', 'Transport'
    SALARIES = 'salaries', 'Salaries'
    REPAIRS = 'repairs', 'Repairs'
    LICENCES = 'licences', 'Licences'
    OTHER = 'other', 'Other'


class Expense(models.Model):
    """
    An operational expense record.

    Expenses can belong to:
    - A specific shop (shop FK is set)
    - The business as a whole (shop FK is null)

    This distinction is important for per-shop P&L calculations.
    """
    category = models.CharField(
        max_length=20,
        choices=ExpenseCategory.choices,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Expense amount in KES.',
    )
    shop = models.ForeignKey(
        'shops.Shop',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
        help_text='Shop this expense belongs to. Null = business-wide.',
    )
    description = models.TextField(
        blank=True,
        help_text='Description or details of the expense.',
    )
    date = models.DateField(
        help_text='Date the expense was incurred.',
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_expenses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'expense'
        verbose_name_plural = 'expenses'
        ordering = ['-date', '-created_at']

    def __str__(self):
        scope = self.shop.name if self.shop else 'Business-wide'
        return f'{self.get_category_display()} — KES {self.amount} ({scope})'
