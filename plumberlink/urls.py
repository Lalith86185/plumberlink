from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from core import views as v


def legacy_plumbers(request):
    """Old /plumbers/ links (and any printed QRs) -> universal listing, plumber tab."""
    qs = request.GET.copy()
    qs["category"] = "plumber"
    return redirect(f"{reverse('professional_list')}?{qs.urlencode()}")


def legacy_plumber_detail(request, pk):
    return redirect("professional_detail", pk=pk)


urlpatterns = [
    path("django-admin/", admin.site.urls),
    # Customer site
    path("", v.home, name="home"),
    path("professionals/", v.provider_list, name="professional_list"),
    path("professionals/<int:pk>/", v.provider_detail, name="professional_detail"),
    path("plumbers/", legacy_plumbers),            # backward compat
    path("plumbers/<int:pk>/", legacy_plumber_detail),  # backward compat
    path("book/<int:provider_id>/", v.booking_create, name="booking_create"),
    path("booking/<str:ref>/", v.booking_detail, name="booking_detail"),
    path("track/", v.booking_track, name="booking_track"),
    path("review/<str:token>/", v.review_create, name="review_create"),
    path("q/<slug:slug>/", v.qr_redirect, name="qr_redirect"),
    # Customer accounts
    path("account/register/", v.customer_register, name="customer_register"),
    path("account/login/", v.customer_login, name="customer_login"),
    path("account/logout/", v.customer_logout, name="customer_logout"),
    path("account/", v.customer_dashboard, name="customer_dashboard"),
    path("account/profile/", v.customer_profile, name="customer_profile"),
    # Provider area
    path("provider/register/", v.provider_register, name="provider_register"),
    path("provider/login/", v.provider_login, name="provider_login"),
    path("provider/logout/", v.provider_logout, name="provider_logout"),
    path("provider/pending/", v.provider_pending, name="provider_pending"),
    path("provider/", v.provider_dashboard, name="provider_dashboard"),
    path("provider/bookings/", v.provider_bookings, name="provider_bookings"),
    path("provider/profile/", v.provider_profile, name="provider_profile"),
    path("provider/reviews/", v.provider_reviews, name="provider_reviews"),
    path("provider/earnings/", v.provider_earnings, name="provider_earnings"),
    # Admin panel
    path("admin-panel/", v.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/providers/", v.admin_providers, name="admin_providers"),
    path("admin-panel/customers/", v.admin_customers, name="admin_customers"),
    path("admin-panel/categories/", v.admin_categories, name="admin_categories"),
    path("admin-panel/categories/new/", v.admin_category_edit, name="admin_category_new"),
    path("admin-panel/categories/<int:pk>/", v.admin_category_edit, name="admin_category_edit"),
    path("admin-panel/categories/<int:pk>/delete/", v.admin_category_delete, name="admin_category_delete"),
    path("admin-panel/bookings/", v.admin_bookings, name="admin_bookings"),
    path("admin-panel/reviews/", v.admin_reviews, name="admin_reviews"),
    path("admin-panel/qr/", v.admin_qr_list, name="admin_qr_list"),
    path("admin-panel/qr/new/", v.admin_qr_create, name="admin_qr_create"),
    path("admin-panel/qr/<slug:slug>/", v.admin_qr_detail, name="admin_qr_detail"),
    path("admin-panel/settings/", v.admin_settings, name="admin_settings"),
    # Pilot media serving (images only; use object storage/CDN at real scale)
    re_path(r"^media/(?P<path>.*\.(png|jpg|jpeg|webp|gif))$", v.media_serve, name="media_serve"),
]
