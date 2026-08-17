from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from products.models import Category, Product
from shops.models import Shop
from sales.models import Sale, SaleItem, SaleStatus, Payment, PaymentMethod


class SaleModelTests(TestCase):
    """Tests for the Sale and SaleItem models."""

    def setUp(self):
        self.user = User.objects.create_user(username='cashier1', password='pass')
        self.shop = Shop.objects.create(name='Sale Shop', location='Test')
        self.category = Category.objects.create(name='Spirits')
        self.product_a = Product.objects.create(
            name='Johnnie Walker', brand='JW', category=self.category,
            sku='JW-750', buying_price=Decimal('2000.00'),
            selling_price=Decimal('3000.00'), tax_rate=Decimal('16.00'),
        )
        self.product_b = Product.objects.create(
            name='Jack Daniels', brand='JD', category=self.category,
            sku='JD-750', buying_price=Decimal('2500.00'),
            selling_price=Decimal('3500.00'), tax_rate=Decimal('16.00'),
        )

    def test_sale_with_multiple_items(self):
        """A sale can contain multiple sale items."""
        sale = Sale.objects.create(
            receipt_number='RCP-001',
            shop=self.shop,
            cashier=self.user,
            subtotal=Decimal('6500.00'),
            tax_amount=Decimal('1040.00'),
            total_amount=Decimal('7540.00'),
        )
        SaleItem.objects.create(
            sale=sale, product=self.product_a,
            product_name='Johnnie Walker',
            quantity=1, unit_price=Decimal('3000.00'),
            buying_price=Decimal('2000.00'),
            tax_rate=Decimal('16.00'),
            line_total=Decimal('3000.00'),
        )
        SaleItem.objects.create(
            sale=sale, product=self.product_b,
            product_name='Jack Daniels',
            quantity=1, unit_price=Decimal('3500.00'),
            buying_price=Decimal('2500.00'),
            tax_rate=Decimal('16.00'),
            line_total=Decimal('3500.00'),
        )
        self.assertEqual(sale.items.count(), 2)

    def test_sale_item_preserves_prices_at_sale_time(self):
        """SaleItem stores price snapshots independent of current product price."""
        sale = Sale.objects.create(
            receipt_number='RCP-002',
            shop=self.shop, cashier=self.user,
            total_amount=Decimal('2800.00'),
        )
        item = SaleItem.objects.create(
            sale=sale, product=self.product_a,
            product_name='Johnnie Walker',
            quantity=1,
            unit_price=Decimal('2800.00'),  # discounted from current 3000
            buying_price=Decimal('2000.00'),
            tax_rate=Decimal('16.00'),
            line_total=Decimal('2800.00'),
        )
        # Price on item differs from current product price
        self.assertEqual(item.unit_price, Decimal('2800.00'))
        self.assertNotEqual(item.unit_price, self.product_a.selling_price)

    def test_sale_monetary_fields_are_decimal(self):
        """All monetary fields on Sale are Decimal."""
        sale = Sale.objects.create(
            receipt_number='RCP-003',
            shop=self.shop, cashier=self.user,
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('160.00'),
            total_amount=Decimal('1160.00'),
        )
        self.assertIsInstance(sale.subtotal, Decimal)
        self.assertIsInstance(sale.tax_amount, Decimal)
        self.assertIsInstance(sale.total_amount, Decimal)

    def test_sale_default_status(self):
        """New sales default to COMPLETED status."""
        sale = Sale.objects.create(
            receipt_number='RCP-004',
            shop=self.shop, cashier=self.user,
            total_amount=Decimal('500.00'),
        )
        self.assertEqual(sale.status, SaleStatus.COMPLETED)

    def test_sale_can_be_voided(self):
        """Sale status can be changed to VOIDED."""
        sale = Sale.objects.create(
            receipt_number='RCP-005',
            shop=self.shop, cashier=self.user,
            total_amount=Decimal('500.00'),
        )
        sale.status = SaleStatus.VOIDED
        sale.notes = 'Customer changed their mind'
        sale.save()
        sale.refresh_from_db()
        self.assertEqual(sale.status, SaleStatus.VOIDED)

    def test_str_representation(self):
        sale = Sale.objects.create(
            receipt_number='RCP-006',
            shop=self.shop, cashier=self.user,
            total_amount=Decimal('5000.00'),
        )
        self.assertIn('RCP-006', str(sale))
        self.assertIn('5000', str(sale))


class PaymentModelTests(TestCase):
    """Tests for the Payment model — split payment support."""

    def setUp(self):
        self.user = User.objects.create_user(username='cashier2', password='pass')
        self.shop = Shop.objects.create(name='Payment Shop', location='Test')
        self.sale = Sale.objects.create(
            receipt_number='RCP-SPLIT-001',
            shop=self.shop, cashier=self.user,
            total_amount=Decimal('5000.00'),
        )

    def test_multiple_payments_per_sale(self):
        """A sale can have multiple payment records (split payment)."""
        Payment.objects.create(
            sale=self.sale,
            payment_method=PaymentMethod.CASH,
            amount=Decimal('2000.00'),
            amount_received=Decimal('2000.00'),
        )
        Payment.objects.create(
            sale=self.sale,
            payment_method=PaymentMethod.MPESA,
            amount=Decimal('3000.00'),
            reference_number='QBH123ABC',
        )
        self.assertEqual(self.sale.payments.count(), 2)
        total_paid = sum(p.amount for p in self.sale.payments.all())
        self.assertEqual(total_paid, Decimal('5000.00'))

    def test_payment_monetary_fields_are_decimal(self):
        """Payment amounts are Decimal."""
        payment = Payment.objects.create(
            sale=self.sale,
            payment_method=PaymentMethod.CASH,
            amount=Decimal('1500.50'),
        )
        self.assertIsInstance(payment.amount, Decimal)
        self.assertEqual(payment.amount, Decimal('1500.50'))

    def test_str_representation(self):
        payment = Payment.objects.create(
            sale=self.sale,
            payment_method=PaymentMethod.MPESA,
            amount=Decimal('3000.00'),
        )
        self.assertIn('M-Pesa', str(payment))
        self.assertIn('3000', str(payment))
