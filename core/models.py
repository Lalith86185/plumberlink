"""
PlumberLink data model.

Roles are derived from the linked records, not a role column:
  - staff / superuser  -> platform admin (Django admin + /admin-panel/)
  - has ProviderProfile -> service provider
  - everyone else      -> customer (guests book with name + phone; no account needed)
"""
import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


def _ref_code(prefix: str = "PLB") -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no confusing chars
    return f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(6))}"


def _default_ref_code() -> str:
    return _ref_code()


def _default_review_token() -> str:
    return secrets.token_urlsafe(16)[:32]


class Locality(models.Model):
    """A named service area inside Bengaluru (later: other cities)."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    city = models.CharField(max_length=100, default="Bengaluru")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "localities"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"


class ServiceCategory(models.Model):
    """Top-level trade: Plumber now; Electrician etc. later (active=False = 'coming soon')."""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    tagline = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Service(models.Model):
    """A bookable job type inside a category, e.g. 'Tap / faucet repair'."""

    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = ("category", "slug")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.category.name})"


class ProviderProfile(models.Model):
    """A plumber's public profile. Only listed when approved AND available."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="provider_profile")
    display_name = models.CharField(max_length=120, help_text="Name shown to customers")
    phone = models.CharField(max_length=20, help_text="Customer-facing phone number")
    photo = models.ImageField(upload_to="providers/", blank=True, null=True)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    emergency_available = models.BooleanField(default=False)

    services = models.ManyToManyField(Service, through="ProviderService", related_name="providers")
    areas = models.ManyToManyField(Locality, related_name="providers", help_text="Localities served")

    work_start = models.TimeField(default="09:00")
    work_end = models.TimeField(default="19:00")
    work_days = models.CharField(
        max_length=60, default="Mon,Tue,Wed,Thu,Fri,Sat",
        help_text="Comma-separated, e.g. Mon,Tue,Wed,Thu,Fri,Sat",
    )

    is_available = models.BooleanField(default=True, help_text="Master on/off switch for new bookings")
    is_approved = models.BooleanField(default=False, help_text="Admin approval — unapproved profiles are hidden")
    is_featured = models.BooleanField(default=False, help_text="Pinned to the top of listings")
    is_demo = models.BooleanField(default=False, help_text="Sample data — clearly badged in the UI")

    rating_avg = models.FloatField(default=0.0)
    rating_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-rating_avg", "display_name"]

    def __str__(self):
        return self.display_name

    @property
    def is_listed(self) -> bool:
        return self.is_approved and self.is_available

    def refresh_rating(self):
        from django.db.models import Avg, Count

        agg = self.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
        self.rating_avg = round(agg["avg"] or 0.0, 1)
        self.rating_count = agg["n"] or 0
        self.save(update_fields=["rating_avg", "rating_count"])


class ProviderService(models.Model):
    """One service a provider offers, with optional 'starting at' pricing."""

    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="offered_services")
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    price_from = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True,
                                     help_text="Starting price in INR (optional)")
    price_note = models.CharField(max_length=120, blank=True,
                                  help_text="e.g. 'visiting charge adjusted in bill'")

    class Meta:
        unique_together = ("provider", "service")

    def __str__(self):
        return f"{self.provider} — {self.service}"


class Booking(models.Model):
    STATUS_REQUESTED = "requested"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_REQUESTED, "Requested"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    ref_code = models.CharField(max_length=16, unique=True, default=_default_ref_code)
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="bookings")
    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True)
    locality = models.ForeignKey(Locality, on_delete=models.SET_NULL, null=True, blank=True)
    # Area/landmark only — never store or show an exact customer address publicly.
    area_detail = models.CharField(max_length=200, blank=True,
                                   help_text="Landmark / area, not the full address")
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.CharField(max_length=40, blank=True,
                                      help_text="e.g. 'Morning', '2–4 PM'")
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    provider_notes = models.TextField(blank=True)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Amount the customer paid (filled at completion)")
    review_token = models.CharField(max_length=32, unique=True, blank=True,
                                    default=_default_review_token)
    is_demo = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.ref_code} — {self.customer_name} → {self.provider}"

    def save(self, *args, **kwargs):
        if not self.ref_code:
            self.ref_code = _ref_code()
        if not self.review_token:
            self.review_token = secrets.token_urlsafe(16)[:32]
        super().save(*args, **kwargs)


class Review(models.Model):
    """One review per booking, written via the booking's private review link."""

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review")
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="reviews")
    customer_name = models.CharField(max_length=120)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}★ for {self.provider} ({self.customer_name})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.provider.refresh_rating()


class QRCode(models.Model):
    """Printable QR codes for apartments, shops, associations, localities..."""

    VENUE_APARTMENT = "apartment"
    VENUE_HOUSE = "house"
    VENUE_ASSOCIATION = "association"
    VENUE_SHOP = "shop"
    VENUE_OFFICE = "office"
    VENUE_LOCALITY = "locality"
    VENUE_OTHER = "other"
    VENUE_CHOICES = [
        (VENUE_APARTMENT, "Apartment"),
        (VENUE_HOUSE, "House"),
        (VENUE_ASSOCIATION, "Apartment association"),
        (VENUE_SHOP, "Shop"),
        (VENUE_OFFICE, "Office"),
        (VENUE_LOCALITY, "Local area"),
        (VENUE_OTHER, "Other"),
    ]

    name = models.CharField(max_length=160, help_text="e.g. 'Sobha Apartments — notice board'")
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    venue_type = models.CharField(max_length=20, choices=VENUE_CHOICES, default=VENUE_OTHER)
    locality = models.ForeignKey(Locality, on_delete=models.SET_NULL, null=True, blank=True,
                                 help_text="Optional: QR opens the plumber list pre-filtered to this locality")
    service_category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to="qr/", blank=True, null=True, help_text="Generated QR PNG")
    scans = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:60] or "qr"
            slug = base
            i = 2
            while QRCode.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.slug})"


class PlatformSettings(models.Model):
    """Singleton row (pk=1) holding the monetisation configuration."""

    REVENUE_LEAD_FEE = "lead_fee"
    REVENUE_COMMISSION = "commission"
    REVENUE_SUBSCRIPTION = "subscription"
    REVENUE_CHOICES = [
        (REVENUE_LEAD_FEE, "Lead fee — charge provider per accepted booking lead"),
        (REVENUE_COMMISSION, "Commission — % of completed job value"),
        (REVENUE_SUBSCRIPTION, "Subscription — flat monthly fee for premium listing"),
    ]

    revenue_model = models.CharField(max_length=20, choices=REVENUE_CHOICES, default=REVENUE_LEAD_FEE)
    lead_fee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=49.00)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    subscription_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=499.00)
    currency = models.CharField(max_length=8, default="INR")
    support_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "platform settings"

    def __str__(self):
        return f"Platform settings ({self.get_revenue_model_display()})"

    @classmethod
    def get(cls) -> "PlatformSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Earning(models.Model):
    """Money the platform has earned (or is owed) — the revenue ledger."""

    KIND_LEAD_FEE = "lead_fee"
    KIND_COMMISSION = "commission"
    KIND_SUBSCRIPTION = "subscription"
    KIND_ADJUSTMENT = "adjustment"
    KIND_CHOICES = [
        (KIND_LEAD_FEE, "Lead fee"),
        (KIND_COMMISSION, "Commission"),
        (KIND_SUBSCRIPTION, "Subscription"),
        (KIND_ADJUSTMENT, "Adjustment"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="earnings")
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="charges")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"₹{self.amount} {self.get_kind_display()} — {self.provider}"
