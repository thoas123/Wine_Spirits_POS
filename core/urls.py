from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('staff/', views.staff_placeholder, name='staff'),
    path('shops/', views.shops_placeholder, name='shops'),
    path('shops/<int:pk>/', views.shop_detail, name='shop_detail'),
    path('products/', views.products_placeholder, name='products'),
    path('inventory/<int:pk>/', views.inventory_detail, name='inventory_detail'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('stock-receiving/<int:pk>/', views.stock_receive_detail, name='stock_receive_detail'),
    path('expenses/<int:pk>/', views.expense_detail, name='expense_detail'),
]
