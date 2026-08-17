from decimal import Decimal
from datetime import date

from django.test import TestCase

from accounts.models import User
from shops.models import Shop
from expenses.models import Expense, ExpenseCategory


class ExpenseModelTests(TestCase):
    """Tests for the Expense model."""

    def setUp(self):
        self.user = User.objects.create_user(username='recorder', password='pass')
        self.shop = Shop.objects.create(name='Expense Shop', location='Test')

    def test_shop_specific_expense(self):
        """An expense can belong to a specific shop."""
        expense = Expense.objects.create(
            category=ExpenseCategory.RENT,
            amount=Decimal('50000.00'),
            shop=self.shop,
            description='Monthly rent',
            date=date(2026, 8, 1),
            recorded_by=self.user,
        )
        self.assertEqual(expense.shop, self.shop)

    def test_business_wide_expense(self):
        """An expense can be business-wide (shop = null)."""
        expense = Expense.objects.create(
            category=ExpenseCategory.SALARIES,
            amount=Decimal('150000.00'),
            shop=None,
            description='Monthly salaries',
            date=date(2026, 8, 1),
            recorded_by=self.user,
        )
        self.assertIsNone(expense.shop)

    def test_monetary_field_is_decimal(self):
        expense = Expense.objects.create(
            category=ExpenseCategory.ELECTRICITY,
            amount=Decimal('5500.50'),
            date=date(2026, 8, 15),
            recorded_by=self.user,
        )
        self.assertIsInstance(expense.amount, Decimal)
        self.assertEqual(expense.amount, Decimal('5500.50'))

    def test_str_representation(self):
        expense = Expense.objects.create(
            category=ExpenseCategory.RENT,
            amount=Decimal('50000.00'),
            shop=self.shop,
            date=date(2026, 8, 1),
            recorded_by=self.user,
        )
        result = str(expense)
        self.assertIn('Rent', result)
        self.assertIn('50000', result)
        self.assertIn('Expense Shop', result)

    def test_str_business_wide(self):
        expense = Expense.objects.create(
            category=ExpenseCategory.OTHER,
            amount=Decimal('1000.00'),
            shop=None,
            date=date(2026, 8, 1),
            recorded_by=self.user,
        )
        self.assertIn('Business-wide', str(expense))
