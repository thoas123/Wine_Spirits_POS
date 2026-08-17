from decimal import Decimal

from django.test import TestCase

from accounts.models import User, Role


class UserModelTests(TestCase):
    """Tests for the custom User model."""

    def test_create_user_with_default_role(self):
        """New users default to Cashier role."""
        user = User.objects.create_user(username='testuser', password='testpass')
        self.assertEqual(user.role, Role.CASHIER)

    def test_role_properties(self):
        """Role convenience properties return correct values."""
        admin_user = User.objects.create_user(
            username='admin_user', password='pass', role=Role.ADMINISTRATOR,
        )
        manager = User.objects.create_user(
            username='manager', password='pass', role=Role.SHOP_MANAGER,
        )
        cashier = User.objects.create_user(
            username='cashier', password='pass', role=Role.CASHIER,
        )
        self.assertTrue(admin_user.is_administrator)
        self.assertFalse(admin_user.is_cashier)
        self.assertTrue(manager.is_shop_manager)
        self.assertTrue(cashier.is_cashier)

    def test_str_representation(self):
        """__str__ returns full name or username."""
        user = User.objects.create_user(
            username='jdoe', password='pass',
            first_name='John', last_name='Doe',
        )
        self.assertEqual(str(user), 'John Doe')

        user2 = User.objects.create_user(username='noname', password='pass')
        self.assertEqual(str(user2), 'noname')
