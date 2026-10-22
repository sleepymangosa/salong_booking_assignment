"""Forms for registration, bookings, availability and profile editing."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Booking, Profile, Service, Stylist, phone_validator


class RegistrationForm(UserCreationForm):
    """Create a customer account together with their phone number."""
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=16, validators=[phone_validator])

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.create(user=user, phone=self.cleaned_data['phone'])
        return user


class BookingForm(forms.ModelForm):
    """Used by customers to make or reschedule a booking."""

    class Meta:
        model = Booking
        fields = ['service', 'stylist', 'date', 'start_time', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'step': 1800}, format='%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {'start_time': 'Pick a time on the hour or half hour.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['stylist'].queryset = Stylist.objects.filter(is_active=True)
        self.fields['date'].widget.attrs['min'] = timezone.localdate().isoformat()


class AvailabilityForm(forms.Form):
    """Lets a customer see which times are free before booking."""
    service = forms.ModelChoiceField(queryset=Service.objects.none())
    stylist = forms.ModelChoiceField(queryset=Stylist.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['stylist'].queryset = Stylist.objects.filter(is_active=True)
        self.fields['date'].widget.attrs['min'] = timezone.localdate().isoformat()

    def clean(self):
        cleaned = super().clean()
        service, stylist = cleaned.get('service'), cleaned.get('stylist')
        if service and stylist and not stylist.services.filter(pk=service.pk).exists():
            raise forms.ValidationError(f'{stylist.name} does not offer {service.name}.')
        return cleaned


class BookingStatusForm(forms.ModelForm):
    """Used by staff to confirm, complete or cancel a booking."""

    class Meta:
        model = Booking
        fields = ['status']


class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Another account already uses this email.')
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone']
