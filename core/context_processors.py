from .models import PlatformSettings, ServiceCategory


def site(request):
    """Global template context: brand, active categories, platform settings."""
    return {
        "brand_name": "PlumberLink",
        "brand_tagline": "Trusted plumbers in Bengaluru",
        "service_categories": ServiceCategory.objects.all().prefetch_related("services"),
        "platform": PlatformSettings.get(),
    }
