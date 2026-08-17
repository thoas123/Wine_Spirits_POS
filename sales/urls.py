from django.urls import path

from . import views

app_name = 'sales'

urlpatterns = [
    path('pos/', views.pos, name='pos'),
    path('receipts/<int:pk>/', views.receipt, name='receipt'),
]
