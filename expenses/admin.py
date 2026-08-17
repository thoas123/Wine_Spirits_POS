from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'category', 'amount', 'shop', 'date',
        'recorded_by', 'created_at',
    )
    list_filter = ('category', 'shop')
    search_fields = ('description',)
    list_select_related = ('shop', 'recorded_by')
    date_hierarchy = 'date'
