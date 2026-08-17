from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User
from shops.models import ShopAssignment


class ShopAssignmentInline(admin.TabularInline):
    model = ShopAssignment
    extra = 0
    fields = ('shop', 'is_active', 'assigned_at')
    readonly_fields = ('assigned_at',)
    autocomplete_fields = ('shop',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for the custom User model.

    Extends Django's built-in UserAdmin with role and phone_number fields.
    """
    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'phone_number', 'is_active', 'is_staff',
    )
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    inlines = (ShopAssignmentInline,)

    # Add role and phone_number to the user edit form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('POS Profile', {
            'fields': ('role', 'phone_number'),
        }),
    )
    # Add role and phone_number to the user creation form
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('POS Profile', {
            'fields': ('role', 'phone_number'),
        }),
    )
