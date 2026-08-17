from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User
from products.models import Category, Product
from shops.models import Shop
from inventory.models import (
    Supplier,
    ShopInventory,
    InventoryMovement,
    MovementType,
    StockReceive,
    StockReceiveItem,
)


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
