from django.contrib import admin

from .models import Sale, SaleItem, Payment


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = (
        'product', 'product_name', 'quantity',
        'unit_price', 'buying_price', 'tax_rate', 'line_total',
    )


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = (
        'payment_method', 'amount', 'reference_number', 'amount_received',
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'receipt_number', 'shop', 'cashier', 'status',
        'total_amount', 'created_at',
    )
    list_filter = ('status', 'shop')
    search_fields = ('receipt_number',)
    list_select_related = ('shop', 'cashier')
    date_hierarchy = 'created_at'
    inlines = [SaleItemInline, PaymentInline]
