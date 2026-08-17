from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    list_editable = ('is_active',)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'brand', 'category', 'sku',
        'buying_price', 'selling_price', 'unit_of_measurement',
        'minimum_stock_level', 'tax_rate', 'is_active',
    )
    list_filter = ('is_active', 'category', 'unit_of_measurement')
    search_fields = ('name', 'brand', 'sku')
    list_select_related = ('category',)
    list_editable = ('is_active',)

    def has_delete_permission(self, request, obj=None):
        return False
