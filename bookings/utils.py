"""Helper functions shared by several views."""
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import Booking


def available_slots(stylist, service, day):
    """Return the free start times (a list of datetime.time) for a stylist on a day."""
    now = timezone.localtime().replace(tzinfo=None)
    if day < now.date() or day.weekday() in settings.BUSINESS_CLOSED_WEEKDAYS:
        return []

    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=settings.SLOT_MINUTES)
    opening = datetime.combine(day, settings.BUSINESS_OPEN)
    closing = datetime.combine(day, settings.BUSINESS_CLOSE)

    busy = [
        (b.start_datetime, b.end_datetime)
        for b in Booking.objects.filter(
            stylist=stylist, date=day, status__in=Booking.ACTIVE_STATUSES
        ).select_related('service')
    ]

    slots = []
    current = opening
    while current + duration <= closing:
        end = current + duration
        is_free = all(not (current < b_end and end > b_start) for b_start, b_end in busy)
        if is_free and current > now:
            slots.append(current.time())
        current += step
    return slots
