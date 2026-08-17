from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """User roles for the Wine & Spirits POS system."""
    ADMINISTRATOR = 'administrator', 'Administrator'
    SHOP_MANAGER = 'shop_manager', 'Shop Manager'
    CASHIER = 'cashier', 'Cashier'


class User(AbstractUser):
    """
    Custom user model for the Wine & Spirits POS system.

    Extends Django's AbstractUser with:
    - Role field for role-based access control
    - Phone number for contact information

    Shop assignments are managed via the ShopAssignment model
    in the shops app (many-to-many through-model).
    """
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        help_text='Determines the user\'s access level in the system.',
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Contact phone number.',
    )

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['username']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_administrator(self):
        return self.role == Role.ADMINISTRATOR

    @property
    def is_shop_manager(self):
        return self.role == Role.SHOP_MANAGER

    @property
    def is_cashier(self):
        return self.role == Role.CASHIER
