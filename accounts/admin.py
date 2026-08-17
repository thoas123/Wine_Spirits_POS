from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for the custom User model.

    Inherits all functionality from Django's built-in UserAdmin.
    Custom fieldsets can be extended here when additional fields
    (e.g., role, shop) are added to the User model.
    """
    pass
