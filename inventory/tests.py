from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, Role
from products.models import Category, Product
from shops.models import Shop, ShopAssignment
from inventory.models import (
    Supplier,
    ShopInventory,
    InventoryMovement,
    MovementType,
    StockReceive,
    StockReceiveItem,
)
from inventory.services import (
    InsufficientStock,
    MissingAdjustmentReason,
    MovementDirection,
    StockStatus,
    adjust_stock,
    decrease_stock,
    get_stock_status,
    increase_stock,
)


FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


class SupplierModelTests(TestCase):

    def test_str_representation(self):
        supplier = Supplier.objects.create(name='Kenya Wine Agencies')
        self.assertEqual(str(supplier), 'Kenya Wine Agencies')


class ShopInventoryTests(TestCase):
    """Tests for the ShopInventory model."""

    def setUp(self):
        self.category = Category.objects.create(name='Spirits')
        self.product = Product.objects.create(
            name='Smirnoff Vodka',
            category=self.category,
            sku='SMR-750',
            buying_price=Decimal('1200.00'),
            selling_price=Decimal('1800.00'),
            minimum_stock_level=10,
        )
        self.shop_a = Shop.objects.create(name='Shop A', location='Loc A')
        self.shop_b = Shop.objects.create(name='Shop B', location='Loc B')

    def test_product_can_exist_in_multiple_shops(self):
        """The same product can have independent inventory in multiple shops."""
        inv_a = ShopInventory.objects.create(
            shop=self.shop_a, product=self.product, quantity=50,
        )
        inv_b = ShopInventory.objects.create(
            shop=self.shop_b, product=self.product, quantity=30,
        )
        self.assertEqual(inv_a.quantity, 50)
        self.assertEqual(inv_b.quantity, 30)
        self.assertEqual(
            ShopInventory.objects.filter(product=self.product).count(), 2,
        )

    def test_unique_shop_product_constraint(self):
        """Duplicate (shop, product) inventory record is rejected."""
        ShopInventory.objects.create(
            shop=self.shop_a, product=self.product, quantity=10,
        )
        with self.assertRaises(IntegrityError):
            ShopInventory.objects.create(
                shop=self.shop_a, product=self.product, quantity=20,
            )

    def test_effective_minimum_stock_product_default(self):
        """Falls back to product's minimum_stock_level when shop override is None."""
        inv = ShopInventory.objects.create(
            shop=self.shop_a, product=self.product, quantity=5,
            minimum_stock_level=None,
        )
        self.assertEqual(inv.effective_minimum_stock, 10)  # product default

    def test_effective_minimum_stock_shop_override(self):
        """Uses shop-specific override when set."""
        inv = ShopInventory.objects.create(
            shop=self.shop_a, product=self.product, quantity=5,
            minimum_stock_level=3,
        )
        self.assertEqual(inv.effective_minimum_stock, 3)

    def test_str_representation(self):
        inv = ShopInventory.objects.create(
            shop=self.shop_a, product=self.product, quantity=25,
        )
        self.assertIn('Smirnoff Vodka', str(inv))
        self.assertIn('Shop A', str(inv))
        self.assertIn('25', str(inv))


class InventoryMovementTests(TestCase):
    """Tests for the InventoryMovement model."""

    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.category = Category.objects.create(name='Beer')
        self.product = Product.objects.create(
            name='Tusker Lager',
            category=self.category,
            sku='TUSK-500',
            buying_price=Decimal('150.00'),
            selling_price=Decimal('250.00'),
        )
        self.shop = Shop.objects.create(name='Test Shop', location='Test')

    def test_create_movement(self):
        """Can create an inventory movement record."""
        movement = InventoryMovement.objects.create(
            shop=self.shop,
            product=self.product,
            movement_type=MovementType.RECEIVED,
            quantity=100,
            balance_after=100,
            created_by=self.user,
            reference='INV-001',
        )
        self.assertEqual(movement.quantity, 100)
        self.assertEqual(movement.balance_after, 100)
        self.assertEqual(movement.movement_type, MovementType.RECEIVED)

    def test_movements_are_append_only(self):
        """Multiple movements create independent records (not overwrites)."""
        InventoryMovement.objects.create(
            shop=self.shop, product=self.product,
            movement_type=MovementType.RECEIVED,
            quantity=50, balance_after=50, created_by=self.user,
        )
        InventoryMovement.objects.create(
            shop=self.shop, product=self.product,
            movement_type=MovementType.SOLD,
            quantity=-10, balance_after=40, created_by=self.user,
        )
        self.assertEqual(
            InventoryMovement.objects.filter(
                shop=self.shop, product=self.product,
            ).count(),
            2,
        )


class StockReceiveTests(TestCase):
    """Tests for StockReceive and StockReceiveItem."""

    def setUp(self):
        self.user = User.objects.create_user(username='receiver', password='pass')
        self.shop = Shop.objects.create(name='Receive Shop', location='Test')
        self.supplier = Supplier.objects.create(name='Supplier Co')
        self.category = Category.objects.create(name='Wines')
        self.product_a = Product.objects.create(
            name='Merlot', category=self.category, sku='MRL-750',
            buying_price=Decimal('800.00'), selling_price=Decimal('1200.00'),
        )
        self.product_b = Product.objects.create(
            name='Chardonnay', category=self.category, sku='CHR-750',
            buying_price=Decimal('900.00'), selling_price=Decimal('1400.00'),
        )

    def test_receive_multiple_products_in_one_delivery(self):
        """A single StockReceive can have multiple items."""
        receive = StockReceive.objects.create(
            shop=self.shop,
            supplier=self.supplier,
            received_by=self.user,
            reference_number='DN-001',
        )
        StockReceiveItem.objects.create(
            stock_receive=receive, product=self.product_a,
            quantity=24, buying_price=Decimal('800.00'),
        )
        StockReceiveItem.objects.create(
            stock_receive=receive, product=self.product_b,
            quantity=12, buying_price=Decimal('950.00'),
        )
        self.assertEqual(receive.items.count(), 2)

    def test_buying_price_preserved_at_receiving(self):
        """Buying price at receiving is independent of product's current price."""
        receive = StockReceive.objects.create(
            shop=self.shop, supplier=self.supplier, received_by=self.user,
        )
        item = StockReceiveItem.objects.create(
            stock_receive=receive, product=self.product_a,
            quantity=10, buying_price=Decimal('750.00'),  # different from product's 800
        )
        self.assertEqual(item.buying_price, Decimal('750.00'))
        self.assertNotEqual(item.buying_price, self.product_a.buying_price)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class InventoryServiceTests(TestCase):
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
        self.shop = Shop.objects.create(name='Shop A', location='A')
        ShopAssignment.objects.create(user=self.manager, shop=self.shop)
        ShopAssignment.objects.create(user=self.cashier, shop=self.shop)
        self.category = Category.objects.create(name='Gin')
        self.product = Product.objects.create(
            name='London Dry Gin',
            category=self.category,
            sku='GIN-001',
            buying_price=Decimal('1000.00'),
            selling_price=Decimal('1500.00'),
            minimum_stock_level=10,
        )
        self.inventory = ShopInventory.objects.create(
            shop=self.shop,
            product=self.product,
            quantity=10,
        )

    def test_increasing_stock_updates_balance_and_creates_movement(self):
        result = increase_stock(
            user=self.admin,
            shop=self.shop,
            product=self.product,
            quantity=5,
            reason='Correction',
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 15)
        self.assertEqual(result.previous_quantity, 10)
        self.assertEqual(result.new_quantity, 15)
        self.assertEqual(result.movement.quantity, 5)
        self.assertEqual(result.movement.balance_after, 15)

    def test_decreasing_stock_updates_balance_and_creates_movement(self):
        result = decrease_stock(
            user=self.admin,
            shop=self.shop,
            product=self.product,
            quantity=4,
            reason='Damaged',
            movement_type=MovementType.DAMAGED,
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 6)
        self.assertEqual(result.movement.quantity, -4)
        self.assertEqual(result.movement.movement_type, MovementType.DAMAGED)

    def test_insufficient_stock_is_rejected_without_movement(self):
        with self.assertRaises(InsufficientStock):
            decrease_stock(user=self.admin, shop=self.shop, product=self.product, quantity=11)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)

    def test_adjustment_updates_balance_and_creates_movement(self):
        result = adjust_stock(
            user=self.manager,
            shop=self.shop,
            product=self.product,
            quantity=3,
            direction=MovementDirection.OUT,
            reason='Physical count variance',
        )
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 7)
        self.assertEqual(result.movement.movement_type, MovementType.ADJUSTMENT)
        self.assertEqual(result.movement.notes, 'Physical count variance')

    def test_adjustment_requires_reason(self):
        with self.assertRaises(MissingAdjustmentReason):
            adjust_stock(
                user=self.admin,
                shop=self.shop,
                product=self.product,
                quantity=1,
                direction=MovementDirection.IN,
                reason='',
            )

    def test_adjustment_cannot_create_negative_stock(self):
        with self.assertRaises(InsufficientStock):
            adjust_stock(
                user=self.admin,
                shop=self.shop,
                product=self.product,
                quantity=20,
                direction=MovementDirection.OUT,
                reason='Count correction',
            )

    def test_cashier_cannot_perform_manual_adjustments(self):
        response = self.client.login(username='cashier', password=self.password)
        self.assertTrue(response)
        with self.assertRaises(PermissionDenied):
            adjust_stock(
                user=self.cashier,
                shop=self.shop,
                product=self.product,
                quantity=1,
                direction=MovementDirection.IN,
                reason='Not allowed',
            )

    def test_inventory_update_uses_row_locking(self):
        with patch(
            'inventory.services.ShopInventory.objects.select_for_update',
            wraps=ShopInventory.objects.select_for_update,
        ) as select_for_update:
            increase_stock(user=self.admin, shop=self.shop, product=self.product, quantity=1)
        self.assertTrue(select_for_update.called)

    def test_failed_movement_creation_rolls_back_inventory_update(self):
        with patch('inventory.services.InventoryMovement.objects.create', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                increase_stock(user=self.admin, shop=self.shop, product=self.product, quantity=5)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 10)
        self.assertEqual(InventoryMovement.objects.count(), 0)


class StockStatusTests(TestCase):
    def test_quantity_above_threshold_is_in_stock(self):
        self.assertEqual(get_stock_status(11, 10), StockStatus.IN_STOCK)

    def test_quantity_equal_to_threshold_is_low_stock(self):
        self.assertEqual(get_stock_status(10, 10), StockStatus.LOW_STOCK)

    def test_quantity_below_threshold_is_low_stock(self):
        self.assertEqual(get_stock_status(5, 10), StockStatus.LOW_STOCK)

    def test_quantity_zero_is_out_of_stock(self):
        self.assertEqual(get_stock_status(0, 10), StockStatus.OUT_OF_STOCK)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class InventoryAuthorizationViewTests(TestCase):
    password = 'test-password'

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password=self.password,
            role=Role.ADMINISTRATOR,
        )
        self.manager_a = User.objects.create_user(
            username='manager_a',
            password=self.password,
            role=Role.SHOP_MANAGER,
        )
        self.cashier_a = User.objects.create_user(
            username='cashier_a',
            password=self.password,
            role=Role.CASHIER,
        )
        self.shop_a = Shop.objects.create(name='Shop A', location='A')
        self.shop_b = Shop.objects.create(name='Shop B', location='B')
        ShopAssignment.objects.create(user=self.manager_a, shop=self.shop_a)
        ShopAssignment.objects.create(user=self.cashier_a, shop=self.shop_a)
        self.category = Category.objects.create(name='Vodka')
        self.product = Product.objects.create(
            name='Premium Vodka',
            category=self.category,
            sku='VOD-001',
            buying_price=Decimal('900.00'),
            selling_price=Decimal('1300.00'),
        )
        self.inventory_a = ShopInventory.objects.create(
            shop=self.shop_a,
            product=self.product,
            quantity=8,
            minimum_stock_level=5,
        )
        self.inventory_b = ShopInventory.objects.create(
            shop=self.shop_b,
            product=self.product,
            quantity=20,
            minimum_stock_level=5,
        )
        InventoryMovement.objects.create(
            shop=self.shop_a,
            product=self.product,
            movement_type=MovementType.ADJUSTMENT,
            quantity=8,
            balance_after=8,
            created_by=self.admin,
            notes='Initial',
        )
        InventoryMovement.objects.create(
            shop=self.shop_b,
            product=self.product,
            movement_type=MovementType.ADJUSTMENT,
            quantity=20,
            balance_after=20,
            created_by=self.admin,
            notes='Initial',
        )

    def test_unauthenticated_users_cannot_access_inventory(self):
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_administrator_can_see_all_inventory(self):
        self.client.login(username='admin', password=self.password)
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shop A')
        self.assertContains(response, 'Shop B')

    def test_manager_can_see_assigned_shop_inventory_only(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shop A')
        self.assertNotContains(response, 'Shop B')

    def test_manager_cannot_retrieve_unassigned_inventory_by_url(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('inventory:detail', args=[self.inventory_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_manager_can_adjust_assigned_shop_inventory(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.post(
            reverse('inventory:adjust_inventory', args=[self.inventory_a.pk]),
            {
                'shop': self.shop_a.pk,
                'product': self.product.pk,
                'direction': MovementDirection.IN,
                'quantity': 2,
                'reason': 'Count correction',
                'reference': 'COUNT-1',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.inventory_a.refresh_from_db()
        self.assertEqual(self.inventory_a.quantity, 10)

    def test_manager_cannot_adjust_unassigned_shop_inventory_by_url(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.post(
            reverse('inventory:adjust_inventory', args=[self.inventory_b.pk]),
            {
                'shop': self.shop_b.pk,
                'product': self.product.pk,
                'direction': MovementDirection.IN,
                'quantity': 2,
                'reason': 'Count correction',
            },
        )
        self.assertEqual(response.status_code, 404)
        self.inventory_b.refresh_from_db()
        self.assertEqual(self.inventory_b.quantity, 20)

    def test_manager_cannot_adjust_unassigned_shop_by_posted_shop_id(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.post(
            reverse('inventory:adjust'),
            {
                'shop': self.shop_b.pk,
                'product': self.product.pk,
                'direction': MovementDirection.IN,
                'quantity': 2,
                'reason': 'Count correction',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.inventory_b.refresh_from_db()
        self.assertEqual(self.inventory_b.quantity, 20)

    def test_cashier_can_view_limited_inventory_but_cannot_adjust(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shop A')
        response = self.client.get(reverse('inventory:adjust_inventory', args=[self.inventory_a.pk]))
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_view_unrestricted_movement_history(self):
        self.client.login(username='cashier_a', password=self.password)
        response = self.client.get(reverse('inventory:movement_list'))
        self.assertEqual(response.status_code, 403)

    def test_manager_movement_history_is_limited_to_assigned_shops(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('inventory:movement_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shop A')
        self.assertNotContains(response, 'Shop B')

    def test_shop_filter_cannot_bypass_authorization(self):
        self.client.login(username='manager_a', password=self.password)
        response = self.client.get(reverse('inventory:list'), {'shop': self.shop_b.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Shop B')

    def test_search_and_filters_are_server_side(self):
        self.client.login(username='admin', password=self.password)
        response = self.client.get(
            reverse('inventory:list'),
            {
                'q': 'Premium',
                'shop': self.shop_a.pk,
                'category': self.category.pk,
                'status': StockStatus.IN_STOCK,
                'product_status': 'active',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Shop A')
        self.assertNotContains(response, '<td>20</td>', html=True)
