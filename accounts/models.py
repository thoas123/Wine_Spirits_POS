from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model for the Wine & Spirits POS system.

    Extends Django's AbstractUser to allow future additions such as:
    - Role field (Administrator, Shop Manager, Cashier)
    - Shop assignment (ForeignKey to Shop)
    - Phone number
    - Other profile fields

    Using a custom user model from the start avoids the complexity
    of migrating away from Django's default User model later.
    """

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['username']

    def __str__(self):
        return self.get_full_name() or self.username
