from django.urls import path

from . import views

app_name = 'shops'

urlpatterns = [
    path('', views.shop_list, name='list'),
    path('create/', views.shop_create, name='create'),
    path('staff/', views.staff_assignment_list, name='staff_assignments'),
    path('<int:pk>/', views.shop_detail, name='detail'),
    path('<int:pk>/edit/', views.shop_edit, name='edit'),
    path('<int:pk>/activate/', views.shop_activate, name='activate'),
    path('<int:pk>/deactivate/', views.shop_deactivate, name='deactivate'),
    path('<int:pk>/staff/', views.shop_staff, name='staff'),
    path('<int:pk>/staff/remove/', views.shop_staff_remove, name='staff_remove'),
]
