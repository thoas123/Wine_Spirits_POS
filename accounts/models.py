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

    @property
    def is_admin_role(self):
        """Business administrator role; separate from Django is_superuser."""
        return self.is_administrator

    @property
    def is_manager_role(self):
        """Business shop-manager role."""
        return self.is_shop_manager

    @property
    def is_cashier_role(self):
        """Business cashier role."""
        return self.is_cashier

    @property
    def role_label(self):
        return self.get_role_display()

    def get_accessible_shops(self):
        """Return shops this user may access under business authorization."""
        from core.authorization import get_accessible_shops

        return get_accessible_shops(self)

    def has_shop_access(self, shop):
        """Return whether this user may access a specific shop."""
        from core.authorization import has_shop_access

        return has_shop_access(self, shop)
