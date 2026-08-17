from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from inventory.models import StockReceive, StockReceiveItem, Supplier
from products.models import Category, Product, UnitOfMeasurement
from sales.models import Sale, SaleItem
from shops.models import Shop


FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


class CategoryModelTests(TestCase):
    """Tests for the Category model."""

    def test_str_representation(self):
        cat = Category.objects.create(name='Whisky')
        self.assertEqual(str(cat), 'Whisky')

    def test_unique_category_name(self):
        """Duplicate category names are rejected."""
        Category.objects.create(name='Wine')
        with self.assertRaises(IntegrityError):
            Category.objects.create(name='Wine')


class ProductModelTests(TestCase):
    """Tests for the Product model."""

    def setUp(self):
        self.category = Category.objects.create(name='Spirits')
        self.product = Product.objects.create(
            name='Jameson Irish Whiskey',
            brand='Jameson',
            category=self.category,
            sku='JAM-750ML',
            buying_price=Decimal('2500.00'),
            selling_price=Decimal('3500.00'),
            unit_of_measurement=UnitOfMeasurement.BOTTLE,
            minimum_stock_level=5,
            tax_rate=Decimal('16.00'),
        )

    def test_str_representation_with_brand(self):
        self.assertEqual(str(self.product), 'Jameson Irish Whiskey (Jameson)')

    def test_str_representation_without_brand(self):
        product = Product.objects.create(
            name='Generic Wine',
            category=self.category,
            sku='GEN-001',
            buying_price=Decimal('500.00'),
            selling_price=Decimal('800.00'),
        )
        self.assertEqual(str(product), 'Generic Wine')

    def test_unique_sku(self):
        """Duplicate SKUs are rejected at DB level."""
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name='Another Product',
                category=self.category,
                sku='JAM-750ML',  # duplicate
                buying_price=Decimal('1000.00'),
                selling_price=Decimal('1500.00'),
            )

    def test_monetary_fields_are_decimal(self):
        """Monetary values are stored as Decimal, not float."""
        self.assertIsInstance(self.product.buying_price, Decimal)
        self.assertIsInstance(self.product.selling_price, Decimal)
        self.assertIsInstance(self.product.tax_rate, Decimal)
        self.assertEqual(self.product.buying_price, Decimal('2500.00'))
        self.assertEqual(self.product.selling_price, Decimal('3500.00'))

    def test_default_values(self):
        product = Product.objects.create(
            name='Test',
            category=self.category,
            sku='TEST-001',
            buying_price=Decimal('100.00'),
            selling_price=Decimal('200.00'),
        )
        self.assertTrue(product.is_active)
        self.assertEqual(product.minimum_stock_level, 0)
        self.assertEqual(product.tax_rate, Decimal('0'))
        self.assertEqual(product.unit_of_measurement, UnitOfMeasurement.BOTTLE)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class ProductManagementTests(TestCase):
    password = 'test-password'

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=Role.ADMINISTRATOR,
        )
        self.manager = User.objects.create_user(
            username='manager',
            password=self.password,
            role=Role.SHOP_MANAGER,
        )
        self.cashier = User.objects.create_user(
            username='cashier',
            password=self.password,
            role=Role.CASHIER,
        )
        self.category = Category.objects.create(name='Whisky')
        self.other_category = Category.objects.create(name='Vodka')
        self.product = Product.objects.create(
            name='Jameson',
            brand='Jameson',
            category=self.category,
            sku='JAM-001',
            buying_price=Decimal('2000.00'),
            selling_price=Decimal('3000.00'),
            unit_of_measurement=UnitOfMeasurement.BOTTLE,
            minimum_stock_level=5,
            tax_rate=Decimal('16.00'),
        )

    def login_admin(self):
        self.client.login(username='admin', password=self.password)

    def product_payload(self, **overrides):
        payload = {
            'name': 'New Product',
            'brand': 'Brand',
            'category': self.category.pk,
            'sku': 'NEW-001',
            'buying_price': '1000.00',
            'selling_price': '1500.00',
            'unit_of_measurement': UnitOfMeasurement.BOTTLE,
            'minimum_stock_level': '3',
            'tax_rate': '16.00',
            'is_active': 'on',
        }
        payload.update(overrides)
        return payload

    def test_administrator_can_view_products(self):
        self.login_admin()
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jameson')

    def test_administrator_can_create_product(self):
        self.login_admin()
        response = self.client.post(reverse('products:create'), self.product_payload())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(sku='NEW-001').exists())

    def test_administrator_can_edit_product(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:edit', args=[self.product.pk]),
            self.product_payload(
                name='Jameson Updated',
                sku='JAM-001',
                selling_price='3200.00',
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Jameson Updated')
        self.assertEqual(self.product.selling_price, Decimal('3200.00'))

    def test_administrator_can_deactivate_product_without_deleting_it(self):
        self.login_admin()
        response = self.client.post(reverse('products:deactivate', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_duplicate_sku_is_rejected_on_create(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:create'),
            self.product_payload(sku='JAM-001'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'sku', 'Product with this SKU already exists.')

    def test_editing_product_without_changing_sku_is_allowed(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:edit', args=[self.product.pk]),
            self.product_payload(name='Same SKU Edit', sku='JAM-001'),
        )
        self.assertEqual(response.status_code, 302)

    def test_changing_sku_to_existing_sku_is_rejected(self):
        existing = Product.objects.create(
            name='Existing',
            category=self.other_category,
            sku='EXIST-001',
            buying_price=Decimal('800.00'),
            selling_price=Decimal('1200.00'),
        )
        self.login_admin()
        response = self.client.post(
            reverse('products:edit', args=[self.product.pk]),
            self.product_payload(name=self.product.name, sku=existing.sku),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'sku', 'Product with this SKU already exists.')

    def test_invalid_monetary_values_are_rejected(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:create'),
            self.product_payload(buying_price='-1.00', selling_price='bad-value'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'buying_price', 'Buying price cannot be negative.')
        self.assertFalse(Product.objects.filter(sku='NEW-001').exists())

    def test_invalid_tax_values_are_rejected(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:create'),
            self.product_payload(tax_rate='101.00'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'tax_rate', 'Tax/excise rate cannot exceed 100%.')

    def test_product_category_relationship_works(self):
        self.assertEqual(self.product.category, self.category)
        self.assertIn(self.product, self.category.products.all())

    def test_product_list_supports_search_category_and_status_filters(self):
        inactive = Product.objects.create(
            name='Filtered Vodka',
            category=self.other_category,
            sku='VOD-001',
            buying_price=Decimal('700.00'),
            selling_price=Decimal('1000.00'),
            is_active=False,
        )
        self.login_admin()
        response = self.client.get(
            reverse('products:list'),
            {'q': 'Filtered', 'category': self.other_category.pk, 'status': 'inactive'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, inactive.name)
        self.assertNotContains(response, self.product.name)

    def test_unauthenticated_users_cannot_access_product_management(self):
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_manager_cannot_create_or_edit_products(self):
        self.client.login(username='manager', password=self.password)
        self.assertEqual(self.client.get(reverse('products:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.product.pk])).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('products:edit', args=[self.product.pk]), self.product_payload()).status_code,
            403,
        )

    def test_cashier_cannot_create_or_edit_products(self):
        self.client.login(username='cashier', password=self.password)
        self.assertEqual(self.client.get(reverse('products:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.product.pk])).status_code, 403)
        self.assertEqual(
            self.client.post(reverse('products:create'), self.product_payload()).status_code,
            403,
        )

    def test_unauthorized_post_requests_are_rejected(self):
        self.client.login(username='manager', password=self.password)
        response = self.client.post(reverse('products:deactivate', args=[self.product.pk]))
        self.assertEqual(response.status_code, 403)

    def test_inactive_category_is_not_selectable_for_new_products(self):
        self.category.is_active = False
        self.category.save(update_fields=['is_active'])
        self.login_admin()
        response = self.client.post(reverse('products:create'), self.product_payload())
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'category',
            'Select a valid choice. That choice is not one of the available choices.',
        )


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class CategoryManagementTests(TestCase):
    password = 'test-password'

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=Role.ADMINISTRATOR,
        )
        self.manager = User.objects.create_user(
            username='manager',
            password=self.password,
            role=Role.SHOP_MANAGER,
        )
        self.cashier = User.objects.create_user(
            username='cashier',
            password=self.password,
            role=Role.CASHIER,
        )
        self.category = Category.objects.create(name='Wine', description='Still and sparkling')

    def login_admin(self):
        self.client.login(username='admin', password=self.password)

    def test_administrator_can_create_category(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:category_create'),
            {'name': 'Gin', 'description': 'Gin products', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(name='Gin').exists())

    def test_administrator_can_edit_category(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:category_edit', args=[self.category.pk]),
            {'name': 'Wine Updated', 'description': 'Updated', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Wine Updated')

    def test_administrator_can_deactivate_category_without_affecting_products(self):
        product = Product.objects.create(
            name='Merlot',
            category=self.category,
            sku='MER-001',
            buying_price=Decimal('800.00'),
            selling_price=Decimal('1200.00'),
        )
        self.login_admin()
        response = self.client.post(reverse('products:category_deactivate', args=[self.category.pk]))
        self.assertEqual(response.status_code, 302)
        self.category.refresh_from_db()
        product.refresh_from_db()
        self.assertFalse(self.category.is_active)
        self.assertEqual(product.category, self.category)

    def test_duplicate_category_handling_uses_model_constraint(self):
        self.login_admin()
        response = self.client.post(
            reverse('products:category_create'),
            {'name': 'Wine', 'description': 'Duplicate', 'is_active': 'on'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'Category with this Name already exists.')

    def test_category_list_supports_search_and_status_filters(self):
        Category.objects.create(name='Inactive Category', is_active=False)
        self.login_admin()
        response = self.client.get(
            reverse('products:category_list'),
            {'q': 'Inactive', 'status': 'inactive'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inactive Category')
        self.assertNotContains(response, self.category.description)

    def test_manager_and_cashier_cannot_manage_categories(self):
        self.client.login(username='manager', password=self.password)
        self.assertEqual(self.client.get(reverse('products:category_create')).status_code, 403)
        self.client.logout()
        self.client.login(username='cashier', password=self.password)
        self.assertEqual(self.client.post(reverse('products:category_deactivate', args=[self.category.pk])).status_code, 403)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class ProductHistoricalIntegrityTests(TestCase):
    password = 'test-password'

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=Role.ADMINISTRATOR,
        )
        self.cashier = User.objects.create_user(
            username='cashier',
            password=self.password,
            role=Role.CASHIER,
        )
        self.shop = Shop.objects.create(name='Shop A', location='A')
        self.category = Category.objects.create(name='Spirits')
        self.product = Product.objects.create(
            name='Historical Product',
            category=self.category,
            sku='HIST-001',
            buying_price=Decimal('1000.00'),
            selling_price=Decimal('1500.00'),
            tax_rate=Decimal('16.00'),
        )

    def login_admin(self):
        self.client.login(username='admin', password=self.password)

    def edit_product_prices(self):
        self.login_admin()
        return self.client.post(
            reverse('products:edit', args=[self.product.pk]),
            {
                'name': self.product.name,
                'brand': self.product.brand,
                'category': self.category.pk,
                'sku': self.product.sku,
                'buying_price': '1200.00',
                'selling_price': '1800.00',
                'unit_of_measurement': self.product.unit_of_measurement,
                'minimum_stock_level': self.product.minimum_stock_level,
                'tax_rate': self.product.tax_rate,
                'is_active': 'on',
            },
        )

    def test_changing_current_selling_price_does_not_alter_historical_sale_item_price(self):
        sale = Sale.objects.create(
            receipt_number='SALE-HIST-001',
            shop=self.shop,
            cashier=self.cashier,
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal('1400.00'),
            buying_price=Decimal('900.00'),
            tax_rate=Decimal('16.00'),
            line_total=Decimal('1400.00'),
        )
        self.assertEqual(self.edit_product_prices().status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('1400.00'))

    def test_changing_current_buying_price_does_not_alter_historical_receiving_price(self):
        supplier = Supplier.objects.create(name='Supplier')
        receive = StockReceive.objects.create(
            shop=self.shop,
            supplier=supplier,
            received_by=self.admin,
        )
        item = StockReceiveItem.objects.create(
            stock_receive=receive,
            product=self.product,
            quantity=10,
            buying_price=Decimal('950.00'),
        )
        self.assertEqual(self.edit_product_prices().status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.buying_price, Decimal('950.00'))

    def test_deactivating_product_does_not_delete_historical_records(self):
        sale = Sale.objects.create(
            receipt_number='SALE-HIST-002',
            shop=self.shop,
            cashier=self.cashier,
        )
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal('1500.00'),
            buying_price=Decimal('1000.00'),
            tax_rate=Decimal('16.00'),
            line_total=Decimal('1500.00'),
        )
        self.login_admin()
        response = self.client.post(reverse('products:deactivate', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        self.assertEqual(item.product, self.product)
