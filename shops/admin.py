from django.contrib import admin

from .models import Shop, ShopAssignment


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'location', 'phone', 'licence_number',
        'licence_expiry', 'is_active',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'location', 'licence_number')


@admin.register(ShopAssignment)
class ShopAssignmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'shop', 'assigned_at', 'is_active')
    list_filter = ('is_active', 'shop')
    search_fields = ('user__username', 'user__first_name', 'shop__name')
    autocomplete_fields = ('user', 'shop')
