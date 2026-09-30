"""
Seed clearly-marked DEMO data for testing the pilot.
Everything created here has is_demo=True and is badged "DEMO" in the UI.
Remove it any time with: python manage.py purge_demo
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Booking, Locality, PlatformSettings, ProviderProfile, QRCode, Review, Service, ServiceCategory,
)
from core.views import build_qr_image

LOCALITIES = [
    "Koramangala", "HSR Layout", "BTM Layout", "JP Nagar", "Whitefield",
    "Marathahalli", "Bellandur", "Indiranagar", "Electronic City", "Hebbal",
    "Yelahanka", "Banashankari", "Jayanagar", "Malleshwaram", "Peenya",
]

PLUMBING_SERVICES = [
    ("Tap / faucet repair", "Leaking or broken taps fixed or replaced", 149),
    ("Pipe leakage repair", "Find and fix leaking pipes", 299),
    ("Bathroom plumbing", "Fittings, flush tanks, sanitary work", 349),
    ("Drain blockage clearing", "Kitchen / bathroom drain unclogging", 399),
    ("Water tank & overhead plumbing", "Tank cleaning, inlet/outlet plumbing", 499),
    ("Emergency plumbing", "Urgent leaks and bursts, fast response", 499),
    ("General plumbing repair", "Any other plumbing work", 199),
]


class Command(BaseCommand):
    help = "Seed demo localities, services, providers, reviews and a QR code (all marked DEMO)"

    def handle(self, *args, **options):
        PlatformSettings.get()

        plumber, _ = ServiceCategory.objects.get_or_create(
            slug="plumber", defaults={"name": "Plumber", "tagline": "All plumbing work", "active": True, "sort_order": 1})
        for slug, name in [("electrician", "Electrician"), ("carpenter", "Carpenter"),
                           ("ac-technician", "AC Technician"), ("appliance-repair", "Appliance Repair")]:
            ServiceCategory.objects.get_or_create(
                slug=slug, defaults={"name": name, "active": False, "sort_order": 9})

        for i, (name, desc, price) in enumerate(PLUMBING_SERVICES):
            Service.objects.get_or_create(
                category=plumber, slug=name.lower().replace(" / ", "-").replace(" ", "-").replace("&", "and"),
                defaults={"name": name, "short_description": desc, "sort_order": i})

        for name in LOCALITIES:
            Locality.objects.get_or_create(name=name, defaults={"city": "Bengaluru"})

        demo_providers = [
            ("demo_plumber1", "Ravi Kumar (DEMO)", "9876500001", "Koramangala",
             "10 yrs fixing taps, leaks and bathroom fittings across Koramangala.", True),
            ("demo_plumber2", "Suresh (DEMO)", "9876500002", "HSR Layout",
             "Drain blockage and water-tank specialist. Same-day visits.", False),
            ("demo_plumber3", "Imran (DEMO)", "9876500003", "Whitefield",
             "Emergency plumbing available. Pipe leakage expert.", True),
        ]
        services = list(Service.objects.filter(category=plumber, active=True))
        for username, display, phone, area, bio, emergency in demo_providers:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": display})
            if created:
                user.set_password("demo1234")
                user.save()
            profile, _ = ProviderProfile.objects.get_or_create(
                user=user,
                defaults={"display_name": display, "phone": phone, "bio": bio,
                          "experience_years": 8, "emergency_available": emergency,
                          "is_approved": True, "is_available": True, "is_demo": True})
            profile.areas.set(Locality.objects.filter(name__in=[area, "BTM Layout"]))
            for j, svc in enumerate(services):
                _, _, price = PLUMBING_SERVICES[j]
                profile.offered_services.get_or_create(
                    service=svc, defaults={"price_from": price})
            profile.refresh_rating()

        # One completed demo booking + review, clearly marked
        p1 = ProviderProfile.objects.get(user__username="demo_plumber1")
        booking, _ = Booking.objects.get_or_create(
            ref_code="PLB-DEMO01",
            defaults={"provider": p1, "customer_name": "Demo Customer", "customer_phone": "9876598765",
                      "service": services[0], "locality": Locality.objects.get(name="Koramangala"),
                      "area_detail": "Near park", "status": Booking.STATUS_COMPLETED,
                      "final_amount": 350, "is_demo": True})
        if not hasattr(booking, "review"):
            Review.objects.create(booking=booking, provider=p1, customer_name="Demo Customer",
                                  rating=5, comment="Arrived on time and fixed the tap neatly. (Sample review)",
                                  is_demo=True)
            p1.refresh_rating()

        qr, created = QRCode.objects.get_or_create(
            slug="koramangala-demo",
            defaults={"name": "Koramangala notice-board (DEMO)", "venue_type": QRCode.VENUE_LOCALITY,
                      "locality": Locality.objects.get(name="Koramangala"), "is_demo": True})
        if created or not qr.image:
            build_qr_image(qr)

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded (all marked DEMO). Provider logins: demo_plumber1/2/3, password: demo1234"))
