from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role
from core.authorization import Capability, has_capability
from expenses.models import Expense, ExpenseCategory
from inventory.models import ShopInventory, StockReceive, Supplier
from products.models import Category, Product
from sales.models import Sale
from shops.models import Shop, ShopAssignment


User = get_user_model()


class AuthorizationTestDataMixin:
    password = 'correct-horse-battery-staple'

    def setUp(self):
        self.shop_a = Shop.objects.create(name='Shop A', location='Nairobi A')
        self.shop_b = Shop.objects.create(name='Shop B', location='Nairobi B')

        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=Role.ADMINISTRATOR,
            is_staff=True,
        )
        self.manager_a = User.objects.create_user(
            username='manager_a',
            password=self.password,
            role=Role.SHOP_MANAGER,
        )
        self.manager_b = User.objects.create_user(
            username='manager_b',
            password=self.password,
            role=Role.SHOP_MANAGER,
        )
        self.cashier_a = User.objects.create_user(
            username='cashier_a',
            password=self.password,
            role=Role.CASHIER,
        )
        self.cashier_b = User.objects.create_user(
            username='cashier_b',
            password=self.password,
            role=Role.CASHIER,
        )
        self.multi_shop_cashier = User.objects.create_user(
            username='multi_cashier',
            password=self.password,
            role=Role.CASHIER,
        )
        self.inactive_user = User.objects.create_user(
            username='inactive',
            password=self.password,
            role=Role.CASHIER,
            is_active=False,
        )

        ShopAssignment.objects.create(user=self.manager_a, shop=self.shop_a)
        ShopAssignment.objects.create(user=self.manager_b, shop=self.shop_b)
        ShopAssignment.objects.create(user=self.cashier_a, shop=self.shop_a)
        ShopAssignment.objects.create(user=self.cashier_b, shop=self.shop_b)
        ShopAssignment.objects.create(user=self.multi_shop_cashier, shop=self.shop_a)
        ShopAssignment.objects.create(user=self.multi_shop_cashier, shop=self.shop_b)

        self.category = Category.objects.create(name='Whisky')
        self.product = Product.objects.create(
            name='Test Whisky',
            category=self.category,
            sku='TW-001',
            buying_price=Decimal('1000.00'),
            selling_price=Decimal('1500.00'),
        )
        self.inventory_a = ShopInventory.objects.create(
            shop=self.shop_a,
            product=self.product,
            quantity=10,
        )
        self.inventory_b = ShopInventory.objects.create(
            shop=self.shop_b,
            product=self.product,
            quantity=20,
        )
        self.sale_a = Sale.objects.create(
            receipt_number='A-001',
            shop=self.shop_a,
            cashier=self.cashier_a,
            total_amount=Decimal('1500.00'),
        )
        self.sale_b = Sale.objects.create(
            receipt_number='B-001',
            shop=self.shop_b,
            cashier=self.cashier_b,
            total_amount=Decimal('1500.00'),
        )
        self.expense_a = Expense.objects.create(
            category=ExpenseCategory.RENT,
            amount=Decimal('5000.00'),
            shop=self.shop_a,
            date=date(2026, 8, 1),
            recorded_by=self.manager_a,
        )
        self.expense_b = Expense.objects.create(
            category=ExpenseCategory.RENT,
            amount=Decimal('6000.00'),
            shop=self.shop_b,
            date=date(2026, 8, 1),
            recorded_by=self.manager_b,
        )
        self.business_expense = Expense.objects.create(
            category=ExpenseCategory.SALARIES,
            amount=Decimal('20000.00'),
            shop=None,
            date=date(2026, 8, 1),
            recorded_by=self.admin,
        )
        self.supplier = Supplier.objects.create(name='Supplier')
        self.receive_a = StockReceive.objects.create(
            shop=self.shop_a,
            supplier=self.supplier,
            received_by=self.manager_a,
        )
        self.receive_b = StockReceive.objects.create(
            shop=self.shop_b,
            supplier=self.supplier,
            received_by=self.manager_b,
        )


FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class AuthenticationTests(AuthorizationTestDataMixin, TestCase):
    def test_unauthenticated_users_cannot_access_protected_pages(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_valid_credentials_authenticate_successfully(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'cashier_a', 'password': self.password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/')

    def test_invalid_credentials_fail(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'cashier_a', 'password': 'wrong'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_inactive_users_cannot_authenticate(self):
        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'inactive', 'password': self.password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid username or password')

    def test_logout_ends_authenticated_session(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 302)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class RoleAndShopAccessTests(AuthorizationTestDataMixin, TestCase):
    def test_roles_are_recognized_correctly(self):
        self.assertTrue(self.admin.is_admin_role)
        self.assertTrue(self.manager_a.is_manager_role)
        self.assertTrue(self.cashier_a.is_cashier_role)

    def test_administrator_can_access_any_shop(self):
        self.assertTrue(self.admin.has_shop_access(self.shop_a))
        self.assertTrue(self.admin.has_shop_access(self.shop_b))
        self.assertCountEqual(
            list(self.admin.get_accessible_shops().values_list('pk', flat=True)),
            [self.shop_a.pk, self.shop_b.pk],
        )

    def test_manager_can_access_assigned_shop_only(self):
        self.assertTrue(self.manager_a.has_shop_access(self.shop_a))
        self.assertFalse(self.manager_a.has_shop_access(self.shop_b))

    def test_cashier_can_access_assigned_shop_only(self):
        self.assertTrue(self.cashier_a.has_shop_access(self.shop_a))
        self.assertFalse(self.cashier_a.has_shop_access(self.shop_b))

    def test_user_assigned_to_multiple_shops_can_access_all_assigned_shops(self):
        self.assertTrue(self.multi_shop_cashier.has_shop_access(self.shop_a))
        self.assertTrue(self.multi_shop_cashier.has_shop_access(self.shop_b))
        self.assertCountEqual(
            list(self.multi_shop_cashier.get_accessible_shops().values_list('pk', flat=True)),
            [self.shop_a.pk, self.shop_b.pk],
        )


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class BusinessPermissionTests(AuthorizationTestDataMixin, TestCase):
    def test_cashier_cannot_access_user_management(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('core:staff'))
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_modify_product_master_data(self):
        self.assertFalse(has_capability(self.cashier_a, Capability.MANAGE_PRODUCTS))
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.post(reverse('core:products'), {})
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_modify_inventory_directly(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.post(reverse('core:inventory_detail', args=[self.inventory_a.pk]), {})
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_manage_expenses(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('core:expense_detail', args=[self.expense_a.pk]))
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_manage_users(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('core:staff'))
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_manage_unrelated_shops(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('core:shop_detail', args=[self.shop_b.pk]))
        self.assertEqual(response.status_code, 403)

    def test_administrator_can_access_business_wide_functionality(self):
        self.client.login(username='admin', password=self.password)
        response = self.client.get(reverse('core:staff'))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('core:products'))
        self.assertEqual(response.status_code, 200)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class CrossShopAccessTests(AuthorizationTestDataMixin, TestCase):
    def test_changing_shop_url_id_cannot_bypass_shop_authorization(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('core:shop_detail', args=[self.shop_b.pk]))
        self.assertEqual(response.status_code, 403)

    def test_inventory_idor_access_is_blocked(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('core:inventory_detail', args=[self.inventory_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_sale_idor_access_is_blocked(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('core:sale_detail', args=[self.sale_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_expense_idor_access_is_blocked(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('core:expense_detail', args=[self.expense_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_business_wide_expense_is_admin_only(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('core:expense_detail', args=[self.business_expense.pk]))
        self.assertEqual(response.status_code, 404)

    def test_stock_receiving_idor_access_is_blocked(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('core:stock_receive_detail', args=[self.receive_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_assigned_shop_objects_are_accessible_where_permitted(self):
        self.client.login(username='manager_a', password=self.password)
        self.assertEqual(
            self.client.get(reverse('core:inventory_detail', args=[self.inventory_a.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('core:sale_detail', args=[self.sale_a.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('core:expense_detail', args=[self.expense_a.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('core:stock_receive_detail', args=[self.receive_a.pk])).status_code,
            200,
        )
