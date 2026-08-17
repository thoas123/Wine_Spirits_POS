from decimal import Decimal

from django import forms

from .models import Category, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description', 'is_active')

    def clean_name(self):
        return self.cleaned_data['name'].strip()


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            'name',
            'brand',
            'category',
            'sku',
            'buying_price',
            'selling_price',
            'unit_of_measurement',
            'minimum_stock_level',
            'tax_rate',
            'is_active',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        category_queryset = Category.objects.filter(is_active=True).order_by('name')
        if self.instance and self.instance.pk and self.instance.category_id:
            category_queryset = Category.objects.filter(
                pk=self.instance.category_id
            ) | category_queryset
        self.fields['category'].queryset = category_queryset.distinct().order_by('name')

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_brand(self):
        return self.cleaned_data.get('brand', '').strip()

    def clean_sku(self):
        return self.cleaned_data['sku'].strip()

    def clean_buying_price(self):
        return self.clean_non_negative_decimal('buying_price', 'Buying price')

    def clean_selling_price(self):
        return self.clean_non_negative_decimal('selling_price', 'Selling price')

    def clean_tax_rate(self):
        tax_rate = self.clean_non_negative_decimal('tax_rate', 'Tax/excise rate')
        if tax_rate > Decimal('100.00'):
            raise forms.ValidationError('Tax/excise rate cannot exceed 100%.')
        return tax_rate

    def clean_non_negative_decimal(self, field_name, label):
        value = self.cleaned_data[field_name]
        if value < Decimal('0'):
            raise forms.ValidationError(f'{label} cannot be negative.')
        return value
