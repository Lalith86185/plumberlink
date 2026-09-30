import re
from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import (
    Booking, CustomerProfile, Locality, PlatformSettings, ProviderProfile, QRCode,
    Review, Service, ServiceCategory,
)

TIME_SLOTS = ["Morning (8–11 AM)", "Midday (11 AM–2 PM)", "Afternoon (2–5 PM)", "Evening (5–8 PM)"]


def clean_indian_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise forms.ValidationError("Enter a valid 10-digit Indian mobile number.")
    return digits


class ProviderRegistrationForm(UserCreationForm):
    display_name = forms.CharField(max_length=120, label="Your name")
    business_name = forms.CharField(max_length=120, required=False,
                                    label="Business / shop name (optional)")
    phone = forms.CharField(max_length=20, label="Mobile number (shown to customers)")
    areas = forms.ModelMultipleChoiceField(
        queryset=Locality.objects.filter(active=True),
        widget=forms.CheckboxSelectMultiple, label="Areas you serve")
    categories = forms.ModelMultipleChoiceField(
        queryset=ServiceCategory.objects.filter(active=True).order_by("sort_order", "name"),
        widget=forms.CheckboxSelectMultiple,
        label="What trades do you work in? (choose one or more)")
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(active=True).select_related("category")
                               .order_by("category__sort_order", "sort_order"),
        widget=forms.CheckboxSelectMultiple, label="Services you offer")
    experience_years = forms.IntegerField(min_value=0, max_value=60, initial=1, label="Years of experience")
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False,
                          label="About you (optional)")
    emergency_available = forms.BooleanField(required=False, label="Available for emergency calls")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)

    def clean_phone(self):
        return clean_indian_phone(self.cleaned_data["phone"])

    def clean(self):
        cleaned = super().clean()
        categories = cleaned.get("categories")
        services = cleaned.get("services")
        if not categories:
            self.add_error("categories", "Choose at least one trade.")
        if not services:
            self.add_error("services", "Choose at least one service you offer.")
        if categories and services:
            allowed = {c.id for c in categories}
            bad = [s.name for s in services if s.category_id not in allowed]
            if bad:
                self.add_error(
                    "services",
                    f"These services are not in your chosen trades: {', '.join(bad)}. "
                    "Tick their trade above or untick them.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile = ProviderProfile(
                user=user,
                display_name=self.cleaned_data["display_name"],
                business_name=self.cleaned_data["business_name"],
                phone=self.cleaned_data["phone"],
                experience_years=self.cleaned_data["experience_years"],
                bio=self.cleaned_data["bio"],
                emergency_available=self.cleaned_data["emergency_available"],
                is_approved=False,  # admin must approve before listing
            )
            profile.save()
            profile.areas.set(self.cleaned_data["areas"])
            for svc in self.cleaned_data["services"]:
                profile.offered_services.create(service=svc)
        return user


class ProviderProfileForm(forms.ModelForm):
    class Meta:
        model = ProviderProfile
        fields = ["display_name", "business_name", "phone", "photo", "bio", "experience_years",
                  "emergency_available", "areas", "work_start", "work_end",
                  "work_days", "is_available"]
        widgets = {
            "areas": forms.CheckboxSelectMultiple,
            "bio": forms.Textarea(attrs={"rows": 3}),
            "work_start": forms.TimeInput(attrs={"type": "time"}),
            "work_end": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean_phone(self):
        return clean_indian_phone(self.cleaned_data["phone"])


class ProviderServicesForm(forms.Form):
    """Checkbox + optional starting price for every active service, grouped by
    category in the template. Works for every trade — no per-category code."""

    def __init__(self, *args, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.provider = provider
        existing = {ps.service_id: ps for ps in provider.offered_services.select_related("service")}
        for svc in Service.objects.filter(active=True).select_related("category").order_by(
                "category__sort_order", "sort_order"):
            self.fields[f"svc_{svc.id}"] = forms.BooleanField(
                required=False, label=svc.name, initial=svc.id in existing)
            ps = existing.get(svc.id)
            self.fields[f"price_{svc.id}"] = forms.DecimalField(
                required=False, min_value=0, max_digits=8, decimal_places=2,
                label="Starting price ₹ (optional)",
                initial=ps.price_from if ps else None)

    def save(self):
        provider = self.provider
        for svc in Service.objects.filter(active=True):
            checked = self.cleaned_data.get(f"svc_{svc.id}")
            price = self.cleaned_data.get(f"price_{svc.id}")
            if checked:
                provider.offered_services.update_or_create(
                    service=svc, defaults={"price_from": price})
            else:
                provider.offered_services.filter(service=svc).delete()


class BookingForm(forms.ModelForm):
    preferred_time = forms.ChoiceField(choices=[("", "No preference")] + [(s, s) for s in TIME_SLOTS],
                                       required=False, label="Preferred time slot")

    class Meta:
        model = Booking
        fields = ["customer_name", "customer_phone", "service", "locality",
                  "area_detail", "preferred_date", "preferred_time", "notes"]
        widgets = {
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "area_detail": forms.TextInput(attrs={"placeholder": "e.g. near Forum Mall — landmark only, not full address"}),
        }

    def __init__(self, *args, provider=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(active=True).order_by(
            "category__sort_order", "sort_order")
        self.fields["service"].empty_label = "General work / not sure"
        self.fields["service"].required = False
        self.fields["locality"].queryset = Locality.objects.filter(active=True)
        self.fields["locality"].empty_label = "Select your locality"
        if provider is not None:
            # Only services this professional actually offers (any trade).
            offered = provider.offered_services.values_list("service_id", flat=True)
            self.fields["service"].queryset = Service.objects.filter(
                pk__in=offered, active=True).order_by("category__sort_order", "sort_order")
            self.fields["locality"].queryset = provider.areas.filter(active=True)
            if self.fields["locality"].queryset.count() == 1:
                self.fields["locality"].initial = self.fields["locality"].queryset.first()

    def clean_customer_phone(self):
        return clean_indian_phone(self.cleaned_data["customer_phone"])

    def clean_preferred_date(self):
        d = self.cleaned_data.get("preferred_date")
        if d and d < date.today():
            raise forms.ValidationError("Please pick today or a future date.")
        return d


class BookingTrackForm(forms.Form):
    ref_code = forms.CharField(max_length=16, label="Booking reference (e.g. NMW-AB12CD)")
    phone = forms.CharField(max_length=20, label="Mobile number used for the booking")

    def clean_phone(self):
        return clean_indian_phone(self.cleaned_data["phone"])


class ProviderBookingActionForm(forms.Form):
    """Advance a booking along its flow from the provider dashboard."""
    action = forms.ChoiceField(choices=[
        ("accept", "Accept"),
        ("reject", "Reject"),
        ("on_the_way", "On the way"),
        ("start", "Start service"),
        ("complete", "Mark completed"),
        ("cancel", "Cancel"),
    ])
    provider_notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    final_amount = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2,
                                     label="Amount collected from customer ₹ (for completed jobs)")


# Allowed status transitions: (from_status, action) -> to_status
BOOKING_TRANSITIONS = {
    (Booking.STATUS_REQUESTED, "accept"): Booking.STATUS_ACCEPTED,
    (Booking.STATUS_REQUESTED, "reject"): Booking.STATUS_REJECTED,
    (Booking.STATUS_ACCEPTED, "on_the_way"): Booking.STATUS_ON_THE_WAY,
    (Booking.STATUS_ON_THE_WAY, "start"): Booking.STATUS_IN_PROGRESS,
    (Booking.STATUS_IN_PROGRESS, "complete"): Booking.STATUS_COMPLETED,
    (Booking.STATUS_REQUESTED, "cancel"): Booking.STATUS_CANCELLED,
    (Booking.STATUS_ACCEPTED, "cancel"): Booking.STATUS_CANCELLED,
    (Booking.STATUS_ON_THE_WAY, "cancel"): Booking.STATUS_CANCELLED,
}


class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(5, "★★★★★ Excellent"), (4, "★★★★ Good"), (3, "★★★ Average"),
                 (2, "★★ Poor"), (1, "★ Very poor")],
        widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 4, "placeholder": "How was the work? Punctual? Fair price?"})}

    def clean_rating(self):
        return int(self.cleaned_data["rating"])


class QRCodeForm(forms.ModelForm):
    class Meta:
        model = QRCode
        fields = ["name", "venue_type", "locality", "service_category", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["locality"].queryset = Locality.objects.filter(active=True)
        self.fields["locality"].required = False
        self.fields["locality"].help_text = (
            "Optional — the QR landing page pre-selects this locality.")
        self.fields["service_category"].queryset = ServiceCategory.objects.filter(active=True)
        self.fields["service_category"].required = False
        self.fields["service_category"].help_text = (
            "Optional — the QR landing page pre-selects this service.")


class PlatformSettingsForm(forms.ModelForm):
    class Meta:
        model = PlatformSettings
        fields = ["revenue_model", "lead_fee_amount", "commission_percent",
                  "subscription_monthly", "currency", "support_phone"]


class CustomerRegistrationForm(UserCreationForm):
    """Customer sign-up: mobile number doubles as the username."""

    full_name = forms.CharField(max_length=120, label="Your name")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)
        labels = {"username": "Mobile number"}

    def clean_username(self):
        return clean_indian_phone(self.cleaned_data["username"])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["full_name"][:30]
        if commit:
            user.save()
            CustomerProfile.objects.create(user=user, phone=user.username)
        return user


class CustomerProfileForm(forms.Form):
    full_name = forms.CharField(max_length=120, label="Your name")
    phone = forms.CharField(max_length=20, label="Mobile number")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["full_name"].initial = user.get_full_name() or user.first_name
            try:
                self.fields["phone"].initial = user.customer_profile.phone
            except CustomerProfile.DoesNotExist:
                self.fields["phone"].initial = user.username

    def clean_phone(self):
        return clean_indian_phone(self.cleaned_data["phone"])

    def save(self):
        user = self.user
        user.first_name = self.cleaned_data["full_name"][:30]
        user.username = self.cleaned_data["phone"]
        user.save()
        CustomerProfile.objects.update_or_create(
            user=user, defaults={"phone": self.cleaned_data["phone"]})
        # Keep guest bookings made with this number linked to the account.
        Booking.objects.filter(
            customer__isnull=True,
            customer_phone=self.cleaned_data["phone"]).update(customer=user)


class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ["name", "icon", "tagline", "description", "sort_order", "active"]
        help_texts = {
            "icon": "Single emoji, e.g. 🔧 ⚡ 🪚 ❄️ 🧹 🎨 📹",
        }
