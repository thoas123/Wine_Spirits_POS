from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.models import Role
from core.authorization import Capability, assert_capability

from .forms import ShopForm, StaffAssignmentForm, ShopAssignmentRemoveForm
from .models import Shop, ShopAssignment
from .services import (
    LICENCE_EXPIRED,
    LICENCE_EXPIRING_SOON,
    LICENCE_MISSING,
    LICENCE_VALID,
    get_licence_status,
)


def require_shop_admin(user):
    assert_capability(user, Capability.MANAGE_SHOPS)


def require_staff_assignment_admin(user):
    assert_capability(user, Capability.ASSIGN_STAFF_TO_SHOPS)


def paginate(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page'))


def apply_shop_filters(queryset, request):
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    licence = request.GET.get('licence', '').strip()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(location__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    if status == 'active':
        queryset = queryset.filter(is_active=True)
    elif status == 'inactive':
        queryset = queryset.filter(is_active=False)

    if licence:
        matching_ids = [
            shop.pk for shop in queryset
            if get_licence_status(shop.licence_expiry).code == licence
        ]
        queryset = queryset.filter(pk__in=matching_ids)

    return queryset, {'q': search, 'status': status, 'licence': licence}


def active_staff_assignments(shop):
    return shop.staff_assignments.select_related('user').filter(is_active=True).order_by(
        'user__role',
        'user__username',
    )


@login_required
def shop_list(request):
    require_shop_admin(request.user)
    shops = Shop.objects.annotate(
        assigned_staff_count=Count(
            'staff_assignments',
            filter=Q(staff_assignments__is_active=True),
        )
    )
    shops, filters = apply_shop_filters(shops, request)
    page_obj = paginate(request, shops.order_by('name'))

    for shop in page_obj.object_list:
        shop.licence_status = get_licence_status(shop.licence_expiry)

    return render(
        request,
        'shops/shop_list.html',
        {
            'page_obj': page_obj,
            'filters': filters,
            'licence_filter_options': (
                (LICENCE_EXPIRED, 'Expired'),
                (LICENCE_EXPIRING_SOON, 'Expiring soon'),
                (LICENCE_VALID, 'Valid'),
                (LICENCE_MISSING, 'Missing expiry date'),
            ),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def shop_create(request):
    require_shop_admin(request.user)
    form = ShopForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        shop = form.save()
        messages.success(request, f'Shop "{shop.name}" was created.')
        return redirect('shops:detail', pk=shop.pk)
    return render(request, 'shops/shop_form.html', {'form': form, 'title': 'Create shop'})


@login_required
def shop_detail(request, pk):
    require_shop_admin(request.user)
    shop = get_object_or_404(Shop, pk=pk)
    assignments = active_staff_assignments(shop)
    managers = assignments.filter(user__role=Role.SHOP_MANAGER)
    cashiers = assignments.filter(user__role=Role.CASHIER)

    return render(
        request,
        'shops/shop_detail.html',
        {
            'shop': shop,
            'licence_status': get_licence_status(shop.licence_expiry),
            'assignments': assignments,
            'manager_count': managers.count(),
            'cashier_count': cashiers.count(),
            'assignment_form': StaffAssignmentForm(shop=shop),
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def shop_edit(request, pk):
    require_shop_admin(request.user)
    shop = get_object_or_404(Shop, pk=pk)
    form = ShopForm(request.POST or None, instance=shop)
    if request.method == 'POST' and form.is_valid():
        shop = form.save()
        messages.success(request, f'Shop "{shop.name}" was updated.')
        return redirect('shops:detail', pk=shop.pk)
    return render(request, 'shops/shop_form.html', {'form': form, 'shop': shop, 'title': 'Edit shop'})


def change_shop_active_state(request, pk, *, is_active):
    require_shop_admin(request.user)
    shop = get_object_or_404(Shop, pk=pk)
    action = 'activate' if is_active else 'deactivate'

    if request.method == 'POST':
        shop.is_active = is_active
        shop.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, f'Shop "{shop.name}" was {action}d.')
        return redirect('shops:detail', pk=shop.pk)

    return render(
        request,
        'shops/shop_confirm_status.html',
        {'shop': shop, 'action': action, 'target_status': is_active},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def shop_deactivate(request, pk):
    return change_shop_active_state(request, pk, is_active=False)


@login_required
@require_http_methods(['GET', 'POST'])
def shop_activate(request, pk):
    return change_shop_active_state(request, pk, is_active=True)


@login_required
@require_http_methods(['GET', 'POST'])
def shop_staff(request, pk):
    require_staff_assignment_admin(request.user)
    shop = get_object_or_404(Shop, pk=pk)
    form = StaffAssignmentForm(request.POST or None, shop=shop)

    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']
        assignment, created = ShopAssignment.objects.get_or_create(user=user, shop=shop)
        if not assignment.is_active:
            assignment.is_active = True
            assignment.save(update_fields=['is_active'])
            created = True

        if created:
            messages.success(request, f'{user} was assigned to {shop.name}.')
        else:
            messages.info(request, f'{user} is already assigned to {shop.name}.')
        return redirect('shops:staff', pk=shop.pk)

    assignments = paginate(request, active_staff_assignments(shop), per_page=10)
    return render(
        request,
        'shops/shop_staff.html',
        {'shop': shop, 'form': form, 'page_obj': assignments},
    )


@login_required
@require_POST
def shop_staff_remove(request, pk):
    require_staff_assignment_admin(request.user)
    shop = get_object_or_404(Shop, pk=pk)
    form = ShopAssignmentRemoveForm(request.POST)
    if form.is_valid():
        assignment = get_object_or_404(
            ShopAssignment,
            pk=form.cleaned_data['assignment_id'],
            shop=shop,
            is_active=True,
        )
        assignment.is_active = False
        assignment.save(update_fields=['is_active'])
        messages.success(request, f'{assignment.user} was removed from {shop.name}.')
    else:
        messages.error(request, 'Unable to remove that staff assignment.')
    return redirect('shops:staff', pk=shop.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def staff_assignment_list(request):
    require_staff_assignment_admin(request.user)
    form = StaffAssignmentForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']
        created_count = 0
        for shop in form.cleaned_data['shops']:
            assignment, created = ShopAssignment.objects.get_or_create(user=user, shop=shop)
            if not assignment.is_active:
                assignment.is_active = True
                assignment.save(update_fields=['is_active'])
                created = True
            if created:
                created_count += 1
        messages.success(request, f'{created_count} new assignment(s) saved for {user}.')
        return redirect('shops:staff_assignments')

    assignments = ShopAssignment.objects.select_related('user', 'shop').filter(is_active=True).order_by(
        'user__username',
        'shop__name',
    )
    page_obj = paginate(request, assignments, per_page=10)
    return render(
        request,
        'shops/staff_assignment_list.html',
        {'form': form, 'page_obj': page_obj},
    )
