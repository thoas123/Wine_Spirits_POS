from django import forms

from core.authorization import get_accessible_shops
from products.models import Product
from shops.models import Shop

from .models import ShopInventory
from .services import MovementDirection


class InventoryAdjustmentForm(forms.Form):
    shop = forms.ModelChoiceField(queryset=Shop.objects.none())
    product = forms.ModelChoiceField(queryset=Product.objects.none())
    direction = forms.ChoiceField(
        choices=(
            (MovementDirection.IN, 'Increase stock'),
            (MovementDirection.OUT, 'Decrease stock'),
        )
    )
    quantity = forms.IntegerField(min_value=1)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), min_length=3)
    reference = forms.CharField(required=False)

    def __init__(self, *args, user=None, inventory=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.inventory = inventory
        shops = get_accessible_shops(user).filter(is_active=True)
        products = Product.objects.filter(is_active=True).order_by('name')
        self.fields['shop'].queryset = shops
        self.fields['product'].queryset = products

        if inventory is not None:
            self.fields['shop'].initial = inventory.shop
            self.fields['product'].initial = inventory.product
            self.fields['shop'].widget = forms.HiddenInput()
            self.fields['product'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        shop = cleaned_data.get('shop')
        product = cleaned_data.get('product')

        if shop and product and not ShopInventory.objects.filter(shop=shop, product=product).exists():
            raise forms.ValidationError('Inventory record does not exist for the selected shop and product.')

        return cleaned_data
