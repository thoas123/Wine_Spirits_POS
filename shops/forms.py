from django import forms

from accounts.models import Role, User

from .models import Shop, ShopAssignment


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = (
            'name',
            'location',
            'phone',
            'email',
            'licence_number',
            'licence_expiry',
            'is_active',
        )
        widgets = {
            'licence_expiry': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_location(self):
        return self.cleaned_data['location'].strip()

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        allowed = set('0123456789+ -()')
        if phone and any(char not in allowed for char in phone):
            raise forms.ValidationError('Enter a valid phone number.')
        return phone

    def clean_licence_number(self):
        return self.cleaned_data.get('licence_number', '').strip()


class StaffAssignmentForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        help_text='Only Managers and Cashiers can be assigned to shops.',
    )
    shops = forms.ModelMultipleChoiceField(
        queryset=Shop.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, shop=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(
            role__in=(Role.SHOP_MANAGER, Role.CASHIER),
            is_active=True,
        ).order_by('username')
        self.fields['shops'].queryset = Shop.objects.filter(is_active=True).order_by('name')

        if shop is not None:
            self.fields['shops'].initial = [shop]
            self.fields['shops'].widget = forms.HiddenInput()
            self.fields['shops'].required = False
            self.shop = shop
        else:
            self.shop = None

    def clean_user(self):
        user = self.cleaned_data['user']
        if user.role not in (Role.SHOP_MANAGER, Role.CASHIER):
            raise forms.ValidationError('Only Managers and Cashiers can be assigned to shops.')
        return user

    def clean_shops(self):
        if self.shop is not None:
            return [self.shop]
        shops = self.cleaned_data['shops']
        if not shops:
            raise forms.ValidationError('Select at least one shop.')
        return shops


class ShopAssignmentRemoveForm(forms.Form):
    assignment_id = forms.IntegerField(widget=forms.HiddenInput)

    def clean_assignment_id(self):
        assignment_id = self.cleaned_data['assignment_id']
        if not ShopAssignment.objects.filter(pk=assignment_id, is_active=True).exists():
            raise forms.ValidationError('Assignment does not exist or has already been removed.')
        return assignment_id
