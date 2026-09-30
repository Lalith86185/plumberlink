"""Remove all rows flagged as demo data (providers, bookings, reviews, QR codes)."""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Booking, ProviderProfile, QRCode, Review


class Command(BaseCommand):
    help = "Delete all demo-flagged data"

    def handle(self, *args, **options):
        n_users = 0
        for profile in ProviderProfile.objects.filter(is_demo=True):
            profile.user.delete()
            n_users += 1
        n_b, _ = Booking.objects.filter(is_demo=True).delete()
        n_r, _ = Review.objects.filter(is_demo=True).delete()
        n_q, _ = QRCode.objects.filter(is_demo=True).delete()
        self.stdout.write(self.style.SUCCESS(
            f"Purged demo data: {n_users} providers, {n_b} bookings, {n_r} reviews, {n_q} QR codes"))
