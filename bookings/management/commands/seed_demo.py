"""Create sample services and stylists so the app has something to book."""
from decimal import Decimal

from django.core.management.base import BaseCommand

from bookings.models import Service, Stylist


class Command(BaseCommand):
    help = 'Adds sample services and stylists (safe to run more than once).'

    def handle(self, *args, **options):
        services = {}
        for name, minutes, price, text in [
            ('Haircut', 30, '120.00', 'Wash, cut and style.'),
            ('Beard trim', 30, '80.00', 'Shape-up and line-up.'),
            ('Haircut and beard', 60, '190.00', 'A full cut with beard trim.'),
            ('Braids', 120, '450.00', 'Cornrows or box braids.'),
            ('Colour', 90, '380.00', 'Single-process colour.'),
        ]:
            services[name], _ = Service.objects.get_or_create(
                name=name,
                defaults={'duration_minutes': minutes, 'price': Decimal(price), 'description': text},
            )

        for name, bio, offered in [
            ('Thabo', 'Fades and classic cuts.', ['Haircut', 'Beard trim', 'Haircut and beard']),
            ('Naledi', 'Braids and colour specialist.', ['Haircut', 'Braids', 'Colour']),
        ]:
            stylist, _ = Stylist.objects.get_or_create(name=name, defaults={'bio': bio})
            stylist.services.set([services[s] for s in offered])

        self.stdout.write(self.style.SUCCESS('Demo services and stylists are ready.'))
