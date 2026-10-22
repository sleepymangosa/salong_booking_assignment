"""Automated tests for the salon booking system."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Profile, Service, Stylist
from .utils import available_slots


def next_weekday(weekday):
    """Return the next date (at least 2 days ahead) that falls on the given weekday."""
    day = timezone.localdate() + timedelta(days=2)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


class BaseTestCase(TestCase):
    def setUp(self):
        self.haircut = Service.objects.create(name='Haircut', duration_minutes=30, price=Decimal('120'))
        self.braids = Service.objects.create(name='Braids', duration_minutes=120, price=Decimal('450'))
        self.thabo = Stylist.objects.create(name='Thabo')
        self.thabo.services.set([self.haircut])
        self.customer = User.objects.create_user('sam', password='pass12345!', first_name='Sam')
        self.other = User.objects.create_user('lee', password='pass12345!')
        self.staff = User.objects.create_user('boss', password='pass12345!', is_staff=True)
        self.monday = next_weekday(0)

    def make_booking(self, start=time(10, 0), customer=None, service=None, **extra):
        booking = Booking(customer=customer or self.customer, service=service or self.haircut,
                          stylist=self.thabo, date=self.monday, start_time=start, **extra)
        booking.full_clean(exclude=['customer'])
        booking.save()
        return booking


class BookingRuleTests(BaseTestCase):
    def test_valid_booking_is_saved_with_pending_status(self):
        booking = self.make_booking()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.end_time, time(10, 30))

    def test_overlapping_booking_is_rejected(self):
        self.make_booking(start=time(10, 0))
        with self.assertRaises(ValidationError):
            self.make_booking(start=time(10, 0), customer=self.other)

    def test_back_to_back_bookings_are_allowed(self):
        self.make_booking(start=time(10, 0))
        self.make_booking(start=time(10, 30), customer=self.other)
        self.assertEqual(Booking.objects.count(), 2)

    def test_cancelled_booking_frees_the_time(self):
        first = self.make_booking(start=time(10, 0))
        first.status = Booking.Status.CANCELLED
        first.save()
        self.make_booking(start=time(10, 0), customer=self.other)
        self.assertEqual(Booking.objects.filter(status='pending').count(), 1)

    def test_booking_outside_opening_hours_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_booking(start=time(8, 0))
        with self.assertRaises(ValidationError):
            self.make_booking(start=time(16, 45))   # would finish after 17:00

    def test_booking_in_the_past_is_rejected(self):
        booking = Booking(customer=self.customer, service=self.haircut, stylist=self.thabo,
                          date=timezone.localdate() - timedelta(days=1), start_time=time(10, 0))
        with self.assertRaises(ValidationError):
            booking.full_clean(exclude=['customer'])

    def test_booking_on_closed_day_is_rejected(self):
        booking = Booking(customer=self.customer, service=self.haircut, stylist=self.thabo,
                          date=next_weekday(6), start_time=time(10, 0))
        with self.assertRaises(ValidationError):
            booking.full_clean(exclude=['customer'])

    def test_stylist_must_offer_the_service(self):
        booking = Booking(customer=self.customer, service=self.braids, stylist=self.thabo,
                          date=self.monday, start_time=time(10, 0))
        with self.assertRaises(ValidationError):
            booking.full_clean(exclude=['customer'])


class AvailabilityTests(BaseTestCase):
    def test_booked_time_is_not_offered(self):
        self.make_booking(start=time(10, 0))
        slots = available_slots(self.thabo, self.haircut, self.monday)
        self.assertNotIn(time(10, 0), slots)
        self.assertIn(time(9, 30), slots)
        self.assertIn(time(10, 30), slots)

    def test_last_slot_finishes_by_closing_time(self):
        slots = available_slots(self.thabo, self.haircut, self.monday)
        self.assertEqual(slots[-1], time(16, 30))

    def test_closed_day_has_no_slots(self):
        self.assertEqual(available_slots(self.thabo, self.haircut, next_weekday(6)), [])

    def test_availability_page_lists_slots(self):
        response = self.client.get(reverse('bookings:availability'), {
            'service': self.haircut.pk, 'stylist': self.thabo.pk, 'date': self.monday.isoformat()})
        self.assertContains(response, '09:00')


class AccountTests(BaseTestCase):
    def test_registration_creates_user_and_profile_and_logs_in(self):
        response = self.client.post(reverse('bookings:register'), {
            'username': 'newuser', 'first_name': 'New', 'last_name': 'User',
            'email': 'new@example.com', 'phone': '0821234567',
            'password1': 'S3cure-pass-word', 'password2': 'S3cure-pass-word'})
        self.assertRedirects(response, reverse('bookings:dashboard'))
        self.assertTrue(Profile.objects.filter(user__username='newuser', phone='0821234567').exists())

    def test_registration_rejects_bad_phone_number(self):
        response = self.client.post(reverse('bookings:register'), {
            'username': 'newuser', 'first_name': 'New', 'last_name': 'User',
            'email': 'new@example.com', 'phone': 'abc',
            'password1': 'S3cure-pass-word', 'password2': 'S3cure-pass-word'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(reverse('bookings:login'), {'username': 'sam', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_with_correct_details_works(self):
        response = self.client.post(reverse('bookings:login'), {'username': 'sam', 'password': 'pass12345!'})
        self.assertRedirects(response, reverse('bookings:dashboard'))


class AccessControlTests(BaseTestCase):
    def test_pages_require_login(self):
        for name in ('dashboard', 'booking_create', 'profile', 'manage_bookings'):
            response = self.client.get(reverse(f'bookings:{name}'))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse('bookings:login'), response['Location'])

    def test_customer_cannot_open_staff_page(self):
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse('bookings:manage_bookings')).status_code, 403)

    def test_customer_cannot_see_someone_elses_booking(self):
        booking = self.make_booking(customer=self.other)
        self.client.force_login(self.customer)
        for name in ('booking_detail', 'booking_update', 'booking_cancel'):
            response = self.client.get(reverse(f'bookings:{name}', args=[booking.pk]))
            self.assertEqual(response.status_code, 404, name)

    def test_customer_cannot_change_status(self):
        booking = self.make_booking()
        self.client.force_login(self.customer)
        response = self.client.post(reverse('bookings:booking_set_status', args=[booking.pk]),
                                    {'status': 'confirmed'})
        self.assertEqual(response.status_code, 403)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'pending')

    def test_staff_can_confirm_a_booking(self):
        booking = self.make_booking()
        self.client.force_login(self.staff)
        self.client.post(reverse('bookings:booking_set_status', args=[booking.pk]), {'status': 'confirmed'})
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')


class BookingFlowTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.customer)
        self.data = {'service': self.haircut.pk, 'stylist': self.thabo.pk,
                     'date': self.monday.isoformat(), 'start_time': '11:00', 'notes': ''}

    def test_customer_can_create_booking(self):
        response = self.client.post(reverse('bookings:booking_create'), self.data)
        booking = Booking.objects.get()
        self.assertRedirects(response, reverse('bookings:booking_detail', args=[booking.pk]))
        self.assertEqual(booking.customer, self.customer)

    def test_double_booking_shows_error_and_saves_nothing(self):
        self.make_booking(start=time(11, 0), customer=self.other)
        response = self.client.post(reverse('bookings:booking_create'), self.data)
        self.assertContains(response, 'already booked')
        self.assertEqual(Booking.objects.count(), 1)

    def test_customer_can_reschedule_own_booking(self):
        booking = self.make_booking()
        self.data['start_time'] = '14:00'
        self.client.post(reverse('bookings:booking_update', args=[booking.pk]), self.data)
        booking.refresh_from_db()
        self.assertEqual(booking.start_time, time(14, 0))

    def test_rescheduling_to_own_current_slot_is_allowed(self):
        booking = self.make_booking(start=time(11, 0))
        response = self.client.post(reverse('bookings:booking_update', args=[booking.pk]), self.data)
        self.assertRedirects(response, reverse('bookings:booking_detail', args=[booking.pk]))

    def test_customer_can_cancel_booking(self):
        booking = self.make_booking()
        self.client.post(reverse('bookings:booking_cancel', args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

    def test_dashboard_lists_upcoming_booking(self):
        self.make_booking()
        self.assertContains(self.client.get(reverse('bookings:dashboard')), 'Haircut')

    def test_staff_search_and_filter(self):
        self.make_booking()
        self.client.force_login(self.staff)
        url = reverse('bookings:manage_bookings')
        self.assertContains(self.client.get(url, {'q': 'sam'}), 'Haircut')
        self.assertNotContains(self.client.get(url, {'q': 'nobody-here'}), 'Haircut')
        self.assertNotContains(self.client.get(url, {'status': 'cancelled'}), 'Haircut')


class PublicPageTests(BaseTestCase):
    def test_home_page_lists_services_and_stylists(self):
        response = self.client.get(reverse('bookings:home'))
        self.assertContains(response, 'Haircut')
        self.assertContains(response, 'Thabo')
