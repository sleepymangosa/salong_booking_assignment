"""Views for the salon booking system."""
from datetime import date
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AvailabilityForm, BookingForm, BookingStatusForm,
    ProfileForm, RegistrationForm, UserUpdateForm,
)
from .models import Booking, Profile, Service, Stylist
from .utils import available_slots


def staff_required(view_func):
    """Only logged-in staff may use the view; everyone else gets a 403 page."""
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def bookings_visible_to(user):
    """Staff can see every booking; customers can only see their own."""
    queryset = Booking.objects.select_related('customer', 'service', 'stylist')
    return queryset if user.is_staff else queryset.filter(customer=user)


# ------------------------------------------------------------------ public pages
def home(request):
    context = {
        'services': Service.objects.filter(is_active=True),
        'stylists': Stylist.objects.filter(is_active=True).prefetch_related('services'),
    }
    return render(request, 'bookings/home.html', context)


def register(request):
    if request.user.is_authenticated:
        return redirect('bookings:dashboard')
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Your account has been created. You can book now.')
            return redirect('bookings:dashboard')
    else:
        form = RegistrationForm()
    return render(request, 'bookings/register.html', {'form': form})


def availability(request):
    form = AvailabilityForm(request.GET or None)
    slots, chosen = [], None
    if form.is_valid():
        chosen = form.cleaned_data
        for slot in available_slots(chosen['stylist'], chosen['service'], chosen['date']):
            query = urlencode({
                'service': chosen['service'].pk, 'stylist': chosen['stylist'].pk,
                'date': chosen['date'].isoformat(), 'start_time': slot.strftime('%H:%M'),
            })
            slots.append({'label': slot.strftime('%H:%M'),
                          'url': f"{reverse('bookings:booking_create')}?{query}"})
    return render(request, 'bookings/availability.html',
                  {'form': form, 'slots': slots, 'chosen': chosen})


# ------------------------------------------------------------------ customer pages
@login_required
def dashboard(request):
    today = timezone.localdate()
    mine = bookings_visible_to(request.user).filter(customer=request.user)
    upcoming = mine.filter(date__gte=today, status__in=Booking.ACTIVE_STATUSES)
    history = mine.exclude(pk__in=upcoming.values('pk')).order_by('-date', '-start_time')
    return render(request, 'bookings/dashboard.html',
                  {'upcoming': upcoming, 'history': history})


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user, defaults={'phone': ''})
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, instance=profile_obj)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('bookings:profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=profile_obj)
    return render(request, 'bookings/profile.html',
                  {'user_form': user_form, 'profile_form': profile_form})


@login_required
def booking_create(request):
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.save()
            messages.success(request, 'Booking created. We will confirm it shortly.')
            return redirect('bookings:booking_detail', pk=booking.pk)
    else:
        prefill = {k: v for k, v in request.GET.items()
                   if k in ('service', 'stylist', 'date', 'start_time')}
        form = BookingForm(initial=prefill)
    return render(request, 'bookings/booking_form.html',
                  {'form': form, 'heading': 'Book an appointment', 'button': 'Book appointment'})


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(bookings_visible_to(request.user), pk=pk)
    status_form = BookingStatusForm(instance=booking) if request.user.is_staff else None
    return render(request, 'bookings/booking_detail.html',
                  {'booking': booking, 'status_form': status_form})


@login_required
def booking_update(request, pk):
    booking = get_object_or_404(bookings_visible_to(request.user), pk=pk)
    if not booking.is_active:
        messages.error(request, 'Only pending or confirmed bookings can be changed.')
        return redirect('bookings:booking_detail', pk=booking.pk)
    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, 'Booking updated.')
            return redirect('bookings:booking_detail', pk=booking.pk)
    else:
        form = BookingForm(instance=booking)
    return render(request, 'bookings/booking_form.html',
                  {'form': form, 'heading': 'Change your booking', 'button': 'Save changes'})


@login_required
def booking_cancel(request, pk):
    booking = get_object_or_404(bookings_visible_to(request.user), pk=pk)
    if not booking.is_active:
        messages.error(request, 'This booking can no longer be cancelled.')
        return redirect('bookings:booking_detail', pk=booking.pk)
    if request.method == 'POST':
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status'])
        messages.success(request, 'Your booking has been cancelled.')
        return redirect('bookings:dashboard')
    return render(request, 'bookings/booking_confirm_cancel.html', {'booking': booking})


# ------------------------------------------------------------------ staff pages
@staff_required
def manage_bookings(request):
    bookings = Booking.objects.select_related('customer', 'service', 'stylist')

    search = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    day = request.GET.get('date', '')

    if search:
        bookings = bookings.filter(
            Q(customer__username__icontains=search)
            | Q(customer__first_name__icontains=search)
            | Q(customer__last_name__icontains=search)
            | Q(service__name__icontains=search)
            | Q(stylist__name__icontains=search)
        )
    if status in Booking.Status.values:
        bookings = bookings.filter(status=status)
    if day:
        try:
            bookings = bookings.filter(date=date.fromisoformat(day))
        except ValueError:
            messages.error(request, 'That date is not valid, so the date filter was ignored.')

    page = Paginator(bookings, 10).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'bookings/manage_bookings.html', {
        'page': page, 'statuses': Booking.Status.choices, 'q': search,
        'status': status, 'day': day, 'querystring': params.urlencode(),
    })


@staff_required
@require_POST
def booking_set_status(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    form = BookingStatusForm(request.POST, instance=booking)
    if form.is_valid():
        form.save()
        messages.success(request, f'Booking marked as {booking.get_status_display().lower()}.')
    else:
        messages.error(request, 'Choose a valid status.')
    return redirect('bookings:booking_detail', pk=booking.pk)
