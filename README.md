# Fade & Co. - Online Salon Booking System (Django)

A Django web application where customers book salon or barbershop appointments online,
and staff manage the bookings. It replaces phone calls, WhatsApp messages and paper diaries.

## Run it

```
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # sample services and stylists
python manage.py createsuperuser    # your staff/admin login
python manage.py runserver
```

Open http://127.0.0.1:8000/ (site) and http://127.0.0.1:8000/admin/ (admin).

To give a user staff access to the "Manage bookings" page, tick **Staff status** on their
account in the admin site. A superuser already has it.

## Run the tests

```
python manage.py test
```

## Project layout

```
salon_booking/        project settings and root urls.py
bookings/
  models.py           Profile, Service, Stylist, Booking (+ booking business rules)
  forms.py            registration, booking, availability, profile, status forms
  views.py            customer and staff views
  urls.py             URL routing
  utils.py            available_slots() - shared slot calculation
  admin.py            admin site setup
  tests.py            29 automated tests
  templates/          base.html + page templates
  static/             CSS
```

## Business rules (settings.py)

- Open Monday to Saturday, 09:00 to 17:00 (`BUSINESS_OPEN`, `BUSINESS_CLOSE`, `BUSINESS_CLOSED_WEEKDAYS`)
- Start times every 30 minutes (`SLOT_MINUTES`)
- A stylist cannot be double-booked, and must offer the chosen service
- Bookings must be in the future and must finish before closing time
