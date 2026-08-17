from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, Role
from sales.models import Sale
from shops.models import Shop, ShopAssignment
from shops.services import (
    LICENCE_EXPIRED,
    LICENCE_EXPIRING_SOON,
    LICENCE_MISSING,
    LICENCE_VALID,
    get_licence_status,
)


FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


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


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class ShopManagementTests(TestCase):
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
        self.shop = Shop.objects.create(
            name='Central',
            location='Nairobi CBD',
            phone='+254 700 000 000',
            email='central@example.com',
            licence_number='LIC-001',
            licence_expiry=timezone.localdate() + timedelta(days=60),
        )
        ShopAssignment.objects.create(user=self.manager, shop=self.shop)
        ShopAssignment.objects.create(user=self.cashier, shop=self.shop)

    def login_admin(self):
        self.client.login(username='admin', password=self.password)

    def test_administrator_can_view_shops(self):
        self.login_admin()
        response = self.client.get(reverse('shops:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Central')

    def test_administrator_can_create_shop(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:create'),
            {
                'name': 'Westlands',
                'location': 'Westlands',
                'phone': '+254 711 111 111',
                'email': 'westlands@example.com',
                'licence_number': 'LIC-002',
                'licence_expiry': timezone.localdate().isoformat(),
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Shop.objects.filter(name='Westlands').exists())

    def test_invalid_shop_data_is_rejected(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:create'),
            {
                'name': '',
                'location': '',
                'phone': 'bad-phone#',
                'email': 'not-email',
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'name', 'This field is required.')
        self.assertFormError(response.context['form'], 'location', 'This field is required.')
        self.assertFalse(Shop.objects.filter(email='not-email').exists())

    def test_administrator_can_edit_shop(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:edit', args=[self.shop.pk]),
            {
                'name': 'Central Updated',
                'location': self.shop.location,
                'phone': self.shop.phone,
                'email': self.shop.email,
                'licence_number': self.shop.licence_number,
                'licence_expiry': self.shop.licence_expiry.isoformat(),
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, 'Central Updated')

    def test_administrator_can_deactivate_shop_without_deleting_it(self):
        self.login_admin()
        response = self.client.post(reverse('shops:deactivate', args=[self.shop.pk]))
        self.assertEqual(response.status_code, 302)
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_active)
        self.assertTrue(Shop.objects.filter(pk=self.shop.pk).exists())

    def test_historical_relationships_are_preserved_after_deactivation(self):
        sale = Sale.objects.create(
            receipt_number='HIST-001',
            shop=self.shop,
            cashier=self.cashier,
        )
        self.login_admin()
        self.client.post(reverse('shops:deactivate', args=[self.shop.pk]))
        sale.refresh_from_db()
        self.assertEqual(sale.shop, self.shop)

    def test_administrator_can_reactivate_shop(self):
        self.shop.is_active = False
        self.shop.save(update_fields=['is_active'])
        self.login_admin()
        response = self.client.post(reverse('shops:activate', args=[self.shop.pk]))
        self.assertEqual(response.status_code, 302)
        self.shop.refresh_from_db()
        self.assertTrue(self.shop.is_active)

    def test_unauthenticated_users_cannot_access_shop_management(self):
        response = self.client.get(reverse('shops:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])

    def test_manager_cannot_create_edit_or_deactivate_shop(self):
        self.client.login(username='manager', password=self.password)
        self.assertEqual(self.client.get(reverse('shops:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('shops:edit', args=[self.shop.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('shops:deactivate', args=[self.shop.pk])).status_code, 403)

    def test_cashier_cannot_create_edit_or_deactivate_shop(self):
        self.client.login(username='cashier', password=self.password)
        self.assertEqual(self.client.get(reverse('shops:create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('shops:edit', args=[self.shop.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('shops:deactivate', args=[self.shop.pk])).status_code, 403)

    def test_shop_list_supports_search_and_status_filter(self):
        Shop.objects.create(name='Inactive Shop', location='Mombasa', is_active=False)
        self.login_admin()
        response = self.client.get(reverse('shops:list'), {'q': 'Mombasa', 'status': 'inactive'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inactive Shop')
        self.assertNotContains(response, 'Central')


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class StaffAssignmentManagementTests(TestCase):
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
        self.other_cashier = User.objects.create_user(
            username='other_cashier',
            password=self.password,
            role=Role.CASHIER,
        )
        self.shop_a = Shop.objects.create(name='Shop A', location='A')
        self.shop_b = Shop.objects.create(name='Shop B', location='B')

    def login_admin(self):
        self.client.login(username='admin', password=self.password)

    def test_administrator_can_assign_manager_to_shop(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.manager.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ShopAssignment.objects.filter(user=self.manager, shop=self.shop_a, is_active=True).exists()
        )

    def test_administrator_can_assign_cashier_to_shop(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.cashier.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ShopAssignment.objects.filter(user=self.cashier, shop=self.shop_a, is_active=True).exists()
        )

    def test_user_can_be_assigned_to_multiple_shops_through_staff_page(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff_assignments'),
            {'user': self.cashier.pk, 'shops': [self.shop_a.pk, self.shop_b.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ShopAssignment.objects.filter(user=self.cashier, is_active=True).count(),
            2,
        )

    def test_duplicate_assignments_are_prevented(self):
        ShopAssignment.objects.create(user=self.cashier, shop=self.shop_a)
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.cashier.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ShopAssignment.objects.filter(user=self.cashier, shop=self.shop_a).count(), 1)

    def test_administrator_can_remove_assignment(self):
        assignment = ShopAssignment.objects.create(user=self.cashier, shop=self.shop_a)
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff_remove', args=[self.shop_a.pk]),
            {'assignment_id': assignment.pk},
        )
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_manager_cannot_assign_staff(self):
        self.client.login(username='manager', password=self.password)
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.other_cashier.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_assign_staff(self):
        self.client.login(username='cashier', password=self.password)
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.other_cashier.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_administrator_access_does_not_depend_on_shop_assignment(self):
        self.login_admin()
        self.assertFalse(ShopAssignment.objects.filter(user=self.admin).exists())
        response = self.client.get(reverse('shops:list'))
        self.assertEqual(response.status_code, 200)

    def test_administrator_user_is_not_eligible_for_shop_assignment(self):
        self.login_admin()
        response = self.client.post(
            reverse('shops:staff', args=[self.shop_a.pk]),
            {'user': self.admin.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShopAssignment.objects.filter(user=self.admin, shop=self.shop_a).exists())


class LicenceStatusTests(TestCase):
    def test_expired_licence_is_identified(self):
        status = get_licence_status(timezone.localdate() - timedelta(days=1))
        self.assertEqual(status.code, LICENCE_EXPIRED)

    def test_licence_expiring_today_is_expiring_soon(self):
        status = get_licence_status(timezone.localdate())
        self.assertEqual(status.code, LICENCE_EXPIRING_SOON)

    def test_licence_expiring_within_30_days_is_expiring_soon(self):
        status = get_licence_status(timezone.localdate() + timedelta(days=15))
        self.assertEqual(status.code, LICENCE_EXPIRING_SOON)

    def test_licence_expiring_exactly_30_days_out_is_expiring_soon(self):
        status = get_licence_status(timezone.localdate() + timedelta(days=30))
        self.assertEqual(status.code, LICENCE_EXPIRING_SOON)

    def test_licence_expiring_beyond_30_days_is_valid(self):
        status = get_licence_status(timezone.localdate() + timedelta(days=31))
        self.assertEqual(status.code, LICENCE_VALID)

    def test_missing_licence_expiry_is_identified(self):
        status = get_licence_status(None)
        self.assertEqual(status.code, LICENCE_MISSING)
