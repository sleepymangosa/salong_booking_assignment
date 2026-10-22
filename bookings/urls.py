from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.home, name='home'),
    path('availability/', views.availability, name='availability'),

    # Accounts
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),

    # Customer bookings
    path('dashboard/', views.dashboard, name='dashboard'),
    path('bookings/new/', views.booking_create, name='booking_create'),
    path('bookings/<int:pk>/', views.booking_detail, name='booking_detail'),
    path('bookings/<int:pk>/edit/', views.booking_update, name='booking_update'),
    path('bookings/<int:pk>/cancel/', views.booking_cancel, name='booking_cancel'),

    # Staff
    path('manage/', views.manage_bookings, name='manage_bookings'),
    path('manage/<int:pk>/status/', views.booking_set_status, name='booking_set_status'),
]
