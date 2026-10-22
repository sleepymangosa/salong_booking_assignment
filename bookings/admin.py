from django.contrib import admin

from .models import Booking, Profile, Service, Stylist


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_minutes', 'price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Stylist)
class StylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    filter_horizontal = ('services',)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('customer', 'service', 'stylist', 'date', 'start_time', 'status')
    list_filter = ('status', 'stylist', 'date')
    search_fields = ('customer__username', 'customer__first_name', 'customer__last_name')


admin.site.register(Profile)
