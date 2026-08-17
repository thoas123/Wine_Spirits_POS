from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase

from products.models import Category, Product, UnitOfMeasurement


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
