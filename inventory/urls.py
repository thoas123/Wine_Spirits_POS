from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('movements/', views.movement_list, name='movement_list'),
    path('adjust/', views.inventory_adjust, name='adjust'),
    path('<int:pk>/', views.inventory_detail, name='detail'),
    path('<int:pk>/adjust/', views.inventory_adjust, name='adjust_inventory'),
]
