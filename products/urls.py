from django.urls import path

from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('create/', views.product_create, name='create'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('categories/<int:pk>/activate/', views.category_activate, name='category_activate'),
    path('categories/<int:pk>/deactivate/', views.category_deactivate, name='category_deactivate'),
    path('<int:pk>/', views.product_detail, name='detail'),
    path('<int:pk>/edit/', views.product_edit, name='edit'),
    path('<int:pk>/activate/', views.product_activate, name='activate'),
    path('<int:pk>/deactivate/', views.product_deactivate, name='deactivate'),
]
