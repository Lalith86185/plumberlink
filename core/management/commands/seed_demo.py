"""
Seed clearly-marked DEMO data for testing NammaWork.
Everything created here has is_demo=True and is badged "DEMO" in the UI.
Covers three trades (plumber, electrician, carpenter) to prove the
multi-service architecture. Remove it any time with: python manage.py purge_demo

Requires the catalog: run `python manage.py seed_catalog` first
(or it runs automatically below).
"""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import (
    Booking, Locality, PlatformSettings, ProviderProfile, QRCode, Review, Service,
)
from core.views import build_qr_image

# username, display name, phone, areas, bio, emergency, {category_slug: [service names]}
DEMO_PROS = [
    ("demo_plumber1", "Ravi Kumar (DEMO)", "9876500001", ["Koramangala", "BTM Layout"],
     "10 yrs fixing taps, leaks and bathroom fittings across Koramangala.", True,
     {"plumber": ["Tap repair", "Pipe leakage", "Bathroom plumbing", "Emergency plumbing"]}),
    ("demo_electrician1", "Ravi Electrical Services (DEMO)", "9876500011", ["Yelahanka", "Hebbal", "Jakkur"],
     "Wiring, fan and light installation. 8 yrs experience, quick response.", False,
     {"electrician": ["Switch/socket repair", "Fan installation", "Light installation", "Wiring"]}),
    ("demo_carpenter1", "Suresh Woodworks (DEMO)", "9876500021", ["HSR Layout", "Koramangala"],
     "Furniture and door repair specialist. Same-day visits.", False,
     {"carpenter": ["Furniture repair", "Door repair", "Cabinet work", "Bed repair"]}),
    # Multi-trade professional: proves one profile spans categories.
    ("demo_multitrade1", "Imran HomeFix (DEMO)", "9876500031", ["Whitefield", "Marathahalli"],
     "Plumbing + electrical handyman. One call for both trades.", True,
     {"plumber": ["Tap repair", "Drain blockage"],
      "electrician": ["Switch/socket repair", "Fan installation"]}),
]

PRICES = {"plumber": 199, "electrician": 249, "carpenter": 299}


class Command(BaseCommand):
    help = "Seed demo providers (plumber/electrician/carpenter), a booking, review and QR (all DEMO)"

    def handle(self, *args, **options):
        PlatformSettings.get()
        call_command("seed_catalog", verbosity=0)

        for username, display, phone, areas, bio, emergency, trades in DEMO_PROS:
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
            profile.areas.set(Locality.objects.filter(name__in=areas))
            for cat_slug, svc_names in trades.items():
                for sname in svc_names:
                    svc = Service.objects.filter(category__slug=cat_slug, name=sname).first()
                    if svc:
                        profile.offered_services.get_or_create(
                            service=svc, defaults={"price_from": PRICES[cat_slug]})
            profile.refresh_rating()

        # One completed demo booking + review, clearly marked
        p1 = ProviderProfile.objects.get(user__username="demo_electrician1")
        svc = Service.objects.filter(category__slug="electrician", name="Fan installation").first()
        booking, _ = Booking.objects.get_or_create(
            ref_code="NMW-DEMO01",
            defaults={"provider": p1, "customer_name": "Demo Customer", "customer_phone": "9876598765",
                      "service": svc, "locality": Locality.objects.get(name="Yelahanka"),
                      "area_detail": "Near park", "status": Booking.STATUS_COMPLETED,
                      "final_amount": 450, "is_demo": True})
        if not hasattr(booking, "review"):
            Review.objects.create(booking=booking, provider=p1, customer_name="Demo Customer",
                                  rating=5, comment="Fixed the fan neatly and on time. (Sample review)",
                                  is_demo=True)
            p1.refresh_rating()

        qr, created = QRCode.objects.get_or_create(
            slug="koramangala-demo",
            defaults={"name": "Koramangala notice-board (DEMO)", "venue_type": QRCode.VENUE_LOCALITY,
                      "locality": Locality.objects.get(name="Koramangala"), "is_demo": True})
        if created or not qr.image:
            build_qr_image(qr)

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded (all marked DEMO). Provider logins: "
            "demo_plumber1 / demo_electrician1 / demo_carpenter1 / demo_multitrade1, password: demo1234"))
