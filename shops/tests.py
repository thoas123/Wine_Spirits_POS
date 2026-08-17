from django.db import IntegrityError
from django.test import TestCase

from accounts.models import User, Role
from shops.models import Shop, ShopAssignment


class ShopModelTests(TestCase):
    """Tests for the Shop model."""

    def setUp(self):
        self.shop = Shop.objects.create(
            name='Downtown Branch',
            location='123 Main St, Nairobi',
        )

    def test_str_representation(self):
        self.assertEqual(str(self.shop), 'Downtown Branch')

    def test_unique_shop_name(self):
        """Duplicate shop names are rejected at DB level."""
        with self.assertRaises(IntegrityError):
            Shop.objects.create(name='Downtown Branch', location='Other place')

    def test_default_is_active(self):
        self.assertTrue(self.shop.is_active)


class ShopAssignmentTests(TestCase):
    """Tests for the User ↔ Shop assignment relationship."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='cashier1', password='pass', role=Role.CASHIER,
        )
        self.shop_a = Shop.objects.create(name='Shop A', location='Location A')
        self.shop_b = Shop.objects.create(name='Shop B', location='Location B')

    def test_user_can_be_assigned_to_multiple_shops(self):
        """A user can be assigned to more than one shop."""
        ShopAssignment.objects.create(user=self.user, shop=self.shop_a)
        ShopAssignment.objects.create(user=self.user, shop=self.shop_b)
        self.assertEqual(self.user.shop_assignments.count(), 2)

    def test_unique_user_shop_constraint(self):
        """Duplicate (user, shop) assignment is rejected."""
        ShopAssignment.objects.create(user=self.user, shop=self.shop_a)
        with self.assertRaises(IntegrityError):
            ShopAssignment.objects.create(user=self.user, shop=self.shop_a)

    def test_str_representation(self):
        assignment = ShopAssignment.objects.create(
            user=self.user, shop=self.shop_a,
        )
        self.assertIn('cashier1', str(assignment))
        self.assertIn('Shop A', str(assignment))
