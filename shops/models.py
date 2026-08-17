from django.conf import settings
from django.db import models


class Shop(models.Model):
    """
    A physical wine and spirits retail shop.

    Each shop maintains independent inventory, sales, and expense records.
    The licence_expiry field supports future flagging of shops whose
    liquor licence expires within 30 days.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Shop display name.',
    )
    location = models.CharField(
        max_length=255,
        help_text='Physical address or location description.',
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Shop contact phone number.',
    )
    email = models.EmailField(
        blank=True,
        help_text='Shop contact email address.',
    )
    licence_number = models.CharField(
        max_length=50,
        blank=True,
        help_text='Liquor licence number.',
    )
    licence_expiry = models.DateField(
        null=True,
        blank=True,
        help_text='Liquor licence expiry date.',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive shops are hidden from operational views.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'shop'
        verbose_name_plural = 'shops'
        ordering = ['name']

    def __str__(self):
        return self.name


class ShopAssignment(models.Model):
    """
    Many-to-many relationship between Users and Shops.

    An explicit through-model is used instead of a simple ManyToManyField
    to support assignment metadata (date, active status) and to avoid
    circular imports between accounts and shops apps.

    A user can be assigned to multiple shops.
    An administrator may access all shops regardless of assignment.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='shop_assignments',
        help_text='The user assigned to the shop.',
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name='staff_assignments',
        help_text='The shop the user is assigned to.',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        default=True,
        help_text='Inactive assignments are treated as revoked.',
    )

    class Meta:
        verbose_name = 'shop assignment'
        verbose_name_plural = 'shop assignments'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'shop'],
                name='unique_user_shop_assignment',
            ),
        ]
        ordering = ['shop__name', 'user__username']

    def __str__(self):
        return f'{self.user} → {self.shop}'
