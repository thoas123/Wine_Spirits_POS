from django.contrib import admin

from .models import (
    Supplier,
    ShopInventory,
    InventoryMovement,
    StockReceive,
    StockReceiveItem,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'phone', 'email')


@admin.register(ShopInventory)
class ShopInventoryAdmin(admin.ModelAdmin):
    list_display = (
        'shop', 'product', 'quantity',
        'minimum_stock_level', 'updated_at',
    )
    list_filter = ('shop',)
    search_fields = ('product__name', 'product__sku', 'shop__name')
    list_select_related = ('shop', 'product')
    readonly_fields = ('shop', 'product', 'quantity', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'shop', 'movement_type',
        'quantity', 'balance_after', 'created_by', 'created_at',
    )
    list_filter = ('movement_type', 'shop')
    search_fields = ('product__name', 'product__sku', 'reference')
    list_select_related = ('shop', 'product', 'created_by')
    date_hierarchy = 'created_at'
    readonly_fields = (
        'shop', 'product', 'movement_type', 'quantity',
        'balance_after', 'reference', 'notes', 'created_by', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ('GET', 'HEAD') and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


class StockReceiveItemInline(admin.TabularInline):
    model = StockReceiveItem
    extra = 1
    raw_id_fields = ('product',)


@admin.register(StockReceive)
class StockReceiveAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'shop', 'supplier', 'received_by',
        'reference_number', 'received_at',
    )
    list_filter = ('shop', 'supplier')
    search_fields = ('reference_number', 'supplier__name')
    list_select_related = ('shop', 'supplier', 'received_by')
    date_hierarchy = 'received_at'
    inlines = [StockReceiveItemInline]
