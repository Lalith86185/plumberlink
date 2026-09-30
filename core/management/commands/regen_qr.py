"""Regenerate every QR image (use after changing PUBLIC_BASE_URL)."""
from django.core.management.base import BaseCommand

from core.models import QRCode
from core.views import build_qr_image


class Command(BaseCommand):
    help = "Regenerate all QR code images with the current public base URL"

    def handle(self, *args, **options):
        for qr in QRCode.objects.all():
            build_qr_image(qr)
            self.stdout.write(f"regenerated {qr.slug}")
        self.stdout.write(self.style.SUCCESS("Done"))
