from .models import PlatformSettings, ServiceCategory


def site(request):
    """Global template context: brand, active categories, platform settings."""
    return {
        "brand_name": "NammaWork",
        "brand_tagline": "Trusted local services, right when you need them.",
        "service_categories": ServiceCategory.objects.all().prefetch_related("services"),
        "platform": PlatformSettings.get(),
    }
