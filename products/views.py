from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from core.authorization import Capability, assert_capability

from .forms import CategoryForm, ProductForm
from .models import Category, Product


def require_product_admin(user):
    assert_capability(user, Capability.MANAGE_PRODUCTS)


def require_category_admin(user):
    assert_capability(user, Capability.MANAGE_CATEGORIES)


def paginate(request, queryset, per_page=10):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get('page'))


@login_required
def product_list(request):
    require_product_admin(request.user)
    products = Product.objects.select_related('category')
    search = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        products = products.filter(
            Q(name__icontains=search)
            | Q(brand__icontains=search)
            | Q(sku__icontains=search)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)

    return render(
        request,
        'products/product_list.html',
        {
            'page_obj': paginate(request, products.order_by('name')),
            'categories': Category.objects.order_by('name'),
            'filters': {'q': search, 'category': category_id, 'status': status},
        },
    )


@login_required
@require_http_methods(['GET', 'POST'])
def product_create(request):
    require_product_admin(request.user)
    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" was created.')
        return redirect('products:detail', pk=product.pk)
    return render(request, 'products/product_form.html', {'form': form, 'title': 'Create product'})


@login_required
def product_detail(request, pk):
    require_product_admin(request.user)
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    return render(request, 'products/product_detail.html', {'product': product})


@login_required
@require_http_methods(['GET', 'POST'])
def product_edit(request, pk):
    require_product_admin(request.user)
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Product "{product.name}" was updated.')
        return redirect('products:detail', pk=product.pk)
    return render(
        request,
        'products/product_form.html',
        {'form': form, 'product': product, 'title': 'Edit product'},
    )


def change_product_active_state(request, pk, *, is_active):
    require_product_admin(request.user)
    product = get_object_or_404(Product, pk=pk)
    action = 'activate' if is_active else 'deactivate'
    if request.method == 'POST':
        product.is_active = is_active
        product.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, f'Product "{product.name}" was {action}d.')
        return redirect('products:detail', pk=product.pk)
    return render(
        request,
        'products/product_confirm_status.html',
        {'product': product, 'action': action, 'target_status': is_active},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def product_deactivate(request, pk):
    return change_product_active_state(request, pk, is_active=False)


@login_required
@require_http_methods(['GET', 'POST'])
def product_activate(request, pk):
    return change_product_active_state(request, pk, is_active=True)


@login_required
def category_list(request):
    require_category_admin(request.user)
    categories = Category.objects.annotate(product_count=Count('products'))
    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    if status == 'active':
        categories = categories.filter(is_active=True)
    elif status == 'inactive':
        categories = categories.filter(is_active=False)

    return render(
        request,
        'products/category_list.html',
        {'page_obj': paginate(request, categories.order_by('name')), 'filters': {'q': search, 'status': status}},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def category_create(request):
    require_category_admin(request.user)
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        messages.success(request, f'Category "{category.name}" was created.')
        return redirect('products:category_list')
    return render(request, 'products/category_form.html', {'form': form, 'title': 'Create category'})


@login_required
@require_http_methods(['GET', 'POST'])
def category_edit(request, pk):
    require_category_admin(request.user)
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        category = form.save()
        messages.success(request, f'Category "{category.name}" was updated.')
        return redirect('products:category_list')
    return render(
        request,
        'products/category_form.html',
        {'form': form, 'category': category, 'title': 'Edit category'},
    )


def change_category_active_state(request, pk, *, is_active):
    require_category_admin(request.user)
    category = get_object_or_404(Category, pk=pk)
    action = 'activate' if is_active else 'deactivate'
    if request.method == 'POST':
        category.is_active = is_active
        category.save(update_fields=['is_active', 'updated_at'])
        messages.success(request, f'Category "{category.name}" was {action}d.')
        return redirect('products:category_list')
    return render(
        request,
        'products/category_confirm_status.html',
        {'category': category, 'action': action, 'target_status': is_active},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def category_deactivate(request, pk):
    return change_category_active_state(request, pk, is_active=False)


@login_required
@require_http_methods(['GET', 'POST'])
def category_activate(request, pk):
    return change_category_active_state(request, pk, is_active=True)
