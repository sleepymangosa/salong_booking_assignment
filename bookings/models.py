"""Database models for the salon booking system."""
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r'^\+?\d{9,15}$',
    message='Enter a valid phone number (9 to 15 digits, e.g. 0821234567).',
)


class Profile(models.Model):
    """Extra details for a customer account (one profile per user)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=16, validators=[phone_validator])

    def __str__(self):
        return f'Profile of {self.user.username}'


class Service(models.Model):
    """Something a customer can book, e.g. a haircut."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(
        validators=[MinValueValidator(15)],
        help_text='How long the service takes, in minutes.',
    )
    price = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(0)],
        help_text='Price in rand (R).',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.duration_minutes} min)'


class Stylist(models.Model):
    """A staff member who performs services."""
    name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    services = models.ManyToManyField(Service, related_name='stylists')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Booking(models.Model):
    """An appointment made by a customer with a stylist for a service."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    # Bookings in these states still take up the stylist's time.
    ACTIVE_STATUSES = (Status.PENDING, Status.CONFIRMED)

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='bookings')
    stylist = models.ForeignKey(Stylist, on_delete=models.PROTECT, related_name='bookings')
    date = models.DateField()
    start_time = models.TimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f'{self.service.name} with {self.stylist.name} on {self.date} at {self.start_time:%H:%M}'

    @property
    def start_datetime(self):
        return datetime.combine(self.date, self.start_time)

    @property
    def end_datetime(self):
        return self.start_datetime + timedelta(minutes=self.service.duration_minutes)

    @property
    def end_time(self):
        return self.end_datetime.time()

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    def clean(self):
        """Business rules. Runs for forms and the admin site."""
        # Skip until the required fields are valid (field errors are reported first).
        if not (self.service_id and self.stylist_id and self.date and self.start_time):
            return

        start, end = self.start_datetime, self.end_datetime
        errors = {}

        if self.is_active and start <= timezone.localtime().replace(tzinfo=None):
            errors['date'] = 'Choose a date and time in the future.'

        if self.date.weekday() in settings.BUSINESS_CLOSED_WEEKDAYS:
            errors['date'] = 'The salon is closed on this day. Please choose another day.'

        opening = datetime.combine(self.date, settings.BUSINESS_OPEN)
        closing = datetime.combine(self.date, settings.BUSINESS_CLOSE)
        if start < opening or end > closing:
            errors['start_time'] = (
                f'This service must start and finish between '
                f'{settings.BUSINESS_OPEN:%H:%M} and {settings.BUSINESS_CLOSE:%H:%M}.'
            )

        if not self.stylist.services.filter(pk=self.service_id).exists():
            errors['stylist'] = f'{self.stylist.name} does not offer {self.service.name}.'

        if self.is_active and 'start_time' not in errors:
            clashes = Booking.objects.filter(
                stylist=self.stylist, date=self.date, status__in=self.ACTIVE_STATUSES,
            ).exclude(pk=self.pk).select_related('service')
            for other in clashes:
                if start < other.end_datetime and end > other.start_datetime:
                    errors['start_time'] = (
                        f'{self.stylist.name} is already booked from '
                        f'{other.start_time:%H:%M} to {other.end_time:%H:%M}. Pick another time.'
                    )
                    break

        if errors:
            raise ValidationError(errors)
